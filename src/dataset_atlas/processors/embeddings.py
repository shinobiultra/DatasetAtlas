"""Pinned, local-only embedding recipes; no Hub resolution or implicit downloads."""
from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import tempfile
from typing import Any
from contextlib import contextmanager

import numpy as np
from dataset_atlas.models import Record, content_id
from dataset_atlas.storage.local import read_rooted_file
from .core import package_version
from .vision import _load
from .device import torch_device

RECIPES = {
    "embed.minilm": {"model_id": "sentence-transformers/all-MiniLM-L6-v2", "revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41", "dimension": 384, "pooling": "sentence-transformers mean pooling", "max_tokens": 256, "metric": "cosine"},
    "embed.siglip2": {"model_id": "google/siglip2-base-patch16-224", "revision": "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2", "dimension": 768, "pooling": "SigLIP2 projected image/text features", "max_tokens": 64, "metric": "cosine"},
}


def compatible_siglip2_spaces(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Check a pinned image/text encoder pairing without relying on dimensions alone."""
    if left.get("model_id") != RECIPES["embed.siglip2"]["model_id"] or right.get("model_id") != left.get("model_id"):
        return False
    first, second = left.get("recipe", {}), right.get("recipe", {})
    modes = {first.get("representation"), second.get("representation")}
    if "image" not in modes or not modes.intersection({"text", "question"}):
        return False
    if not isinstance(left.get("model_sha256"), str) or len(left["model_sha256"]) != 64:
        return False
    return (left.get("model_revision") == right.get("model_revision") == RECIPES["embed.siglip2"]["revision"]
            and left.get("model_sha256") == right.get("model_sha256")
            and all(first.get(key) == second.get(key) for key in ("model_id", "revision", "dimension", "pooling", "normalization", "distance_metric")))


def _snapshot(processor_id: str, config: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    recipe = RECIPES[processor_id]
    path_value = config.get("model_path")
    if not path_value:
        raise ValueError("Embedding requires explicit local model_path")
    path = Path(str(path_value)).expanduser().resolve()
    if not path.is_dir() or config.get("model_revision") != recipe["revision"]:
        raise ValueError("Local model path missing or model_revision differs from pinned recipe")
    weights = path / "model.safetensors"
    if not weights.is_file() or weights.stat().st_size > 2_000_000_000:
        raise ValueError("Local safetensors weights missing or exceed 2 GB bound")
    expected = config.get("model_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("Explicit model_sha256 is required")
    roots = list(config.get("model_roots", []))
    data = read_rooted_file(weights, roots, max_bytes=2_000_000_000) if roots else weights.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise ValueError("Local model_sha256 mismatch")
    return path, {"model_id": recipe["model_id"], "model_revision": recipe["revision"], "model_sha256": digest}


@contextmanager
def _staged_snapshot(source: Path, model_roots: list[str], expected_sha256: str):
    """Materialize a bounded snapshot from no-follow reads before HF sees paths."""
    permitted = {".json", ".txt", ".model", ".safetensors", ".md", ".yaml", ".yml", ".spm", ".vocab", ".merges"}
    count = 0
    total = 0
    with tempfile.TemporaryDirectory(prefix="atlas-model-snapshot-") as temporary:
        staged = Path(temporary)
        for directory, directories, files in os.walk(source, followlinks=False):
            relative_dir = Path(directory).relative_to(source)
            if len(relative_dir.parts) > 3:
                raise ValueError("Model snapshot nesting exceeds three directories")
            directories[:] = [name for name in directories if not name.startswith(".")]
            if any((Path(directory) / name).is_symlink() for name in directories):
                raise ValueError("Model snapshot contains a symlinked directory")
            for filename in files:
                relative = relative_dir / filename
                path = Path(directory) / filename
                if filename.startswith("."):
                    continue  # Hub metadata is not needed by a local loader.
                if path.is_symlink():
                    raise ValueError("Model snapshot contains a symlinked file")
                if path.suffix.lower() == ".bin":
                    continue  # Never stage pickle weights; safetensors are required.
                if path.suffix.lower() not in permitted:
                    raise ValueError(f"Unsupported model snapshot file type: {path.suffix}")
                count += 1
                if count > 128:
                    raise ValueError("Model snapshot exceeds 128 files")
                data = read_rooted_file(source / relative, model_roots or [source],
                                        max_bytes=min(2_000_000_000, 2_200_000_000 - total))
                total += len(data)
                if total > 2_200_000_000:
                    raise ValueError("Model snapshot exceeds 2.2 GB")
                destination = staged / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
        if hashlib.sha256((staged / "model.safetensors").read_bytes()).hexdigest() != expected_sha256:
            raise ValueError("Staged model weights differ from verified source")
        yield staged


def _vector(value: Any, expected: int) -> list[float]:
    array = np.asarray(value, dtype=np.float64).reshape(-1)
    if array.size != expected or not np.isfinite(array).all():
        raise ValueError(f"Embedding dimension must be {expected} and finite")
    norm = float(np.linalg.norm(array))
    if norm == 0:
        raise ValueError("Embedding has zero norm")
    return (array / norm).astype(np.float32).tolist()


def _pooled_features(output):
    """Transformers 5 returns the backbone output; older versions returned its pooler."""
    value=getattr(output,'pooler_output',output)
    if value is None or not hasattr(value,'detach'):
        raise ValueError('SigLIP2 did not return pooled image/text features')
    return value


def run_embeddings(processor_id: str, records: list[Record], config: dict[str, Any], should_cancel=None):
    recipe = RECIPES[processor_id]
    path, model_provenance = _snapshot(processor_id, config)
    mode = str(config.get("representation", "text" if processor_id == "embed.minilm" else "image"))
    if mode not in ({"text", "question"} if processor_id == "embed.minilm" else {"image", "text", "question"}):
        raise ValueError("Invalid embedding representation")
    provenance = {**model_provenance, "recipe": {**recipe, "representation": mode, "normalization": "L2", "distance_metric": "cosine", "truncation": "model tokenizer default", "text_instruction": "none"}}
    provenance["embedding_space_id"] = content_id(provenance["recipe"], "space:")
    if processor_id == "embed.siglip2":
        provenance["shared_encoder_id"] = content_id({key: provenance["recipe"][key] for key in
                                                       ("model_id", "revision", "dimension", "pooling", "normalization", "distance_metric")}, "encoder:")
    if processor_id == "embed.minilm":
        torch=importlib.import_module('torch')
        device,device_provenance=torch_device(torch,config);provenance.update(device_provenance)
        module = importlib.import_module("sentence_transformers")
        with _staged_snapshot(path, list(config.get("model_roots", [])), model_provenance["model_sha256"]) as staged:
            model = module.SentenceTransformer(str(staged), device=device, local_files_only=True, trust_remote_code=False)
        provenance["package_version"] = package_version("sentence-transformers")
    else:
        torch = importlib.import_module("torch")
        device,device_provenance=torch_device(torch,config);provenance.update(device_provenance)
        transformers = importlib.import_module("transformers")
        with _staged_snapshot(path, list(config.get("model_roots", [])), model_provenance["model_sha256"]) as staged:
            processor = transformers.AutoProcessor.from_pretrained(str(staged), local_files_only=True, trust_remote_code=False, use_fast=False)
            model = transformers.AutoModel.from_pretrained(str(staged), local_files_only=True, trust_remote_code=False, use_safetensors=True).to(device).eval()
        provenance["package_version"] = package_version("transformers")
    items = []
    asset_cache: dict[str, list[float]] = {}
    for record in records:
        if should_cancel and should_cancel():
            items.append({"id": record.id, "status": "not_scheduled", "output": None, "error": "cancelled"})
            continue
        try:
            if mode == "image":
                assets = [a for a in record.assets if a.modality.lower() in {"image", "photo"}]
                if not assets:
                    if record.asset_ids and not record.assets:
                        items.append({"id": record.id, "status": "skipped", "output": None, "error": "Asset metadata was not loaded"})
                    else:
                        items.append({"id": record.id, "status": "not_applicable", "output": None})
                    continue
                vectors = []
                errors = []
                for asset in assets:
                    try:
                        image, data = _load(asset, list(config.get("asset_roots", [])), int(config.get("max_pixels", 50_000_000)))
                        cache_key = hashlib.sha256(data).hexdigest()
                        if asset.sha256 and asset.sha256 != cache_key:
                            raise ValueError("Asset sha256 mismatch")
                        if cache_key not in asset_cache:
                            inputs = processor(images=image, return_tensors="pt")
                            inputs={key:value.to(device) for key,value in inputs.items()}
                            with torch.inference_mode():
                                raw = model.get_image_features(**inputs)
                            asset_cache[cache_key] = _vector(_pooled_features(raw).detach().cpu().numpy(), recipe["dimension"])
                        vectors.append({"asset_id": asset.id, "vector": asset_cache[cache_key]})
                    except (OSError, ValueError, RuntimeError, TypeError) as exc:
                        errors.append({"asset_id": asset.id, "error": f"{type(exc).__name__}: {exc}"})
                if not vectors:
                    items.append({"id": record.id, "status": "failed", "output": {"assets": [], "errors": errors}})
                else:
                    output = {"assets": vectors, "errors": errors}
                    if len(vectors) == 1:
                        output["vector"] = vectors[0]["vector"]
                    items.append({"id": record.id, "status": "completed", "output": output})
            else:
                value = getattr(record, mode)
                if not isinstance(value, str) or not value.strip():
                    items.append({"id": record.id, "status": "not_applicable", "output": None})
                    continue
                if processor_id == "embed.minilm":
                    raw = model.encode([value], convert_to_numpy=True, normalize_embeddings=False, show_progress_bar=False)[0]
                else:
                    inputs = processor(text=[value], return_tensors="pt", padding="max_length", truncation=True, max_length=64)
                    inputs={key:value.to(device) for key,value in inputs.items()}
                    with torch.inference_mode():
                        raw = _pooled_features(model.get_text_features(**inputs)).detach().cpu().numpy()[0]
                items.append({"id": record.id, "status": "completed", "output": {"vector": _vector(raw, recipe["dimension"])}})
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            items.append({"id": record.id, "status": "failed", "output": None, "error": f"{type(exc).__name__}: {exc}"})
    return items, provenance


# --- columnar (storage: arrays) path ---------------------------------------
#
# The path above loads and re-verifies the model for every group of records and embeds one item at a
# time in fp32. This one loads and verifies a model once per worker process, runs reduced precision on
# the GPU, decodes and resizes images on a thread pool while the GPU works, normalises on the GPU, and
# embeds each distinct image once however many records point at it. Its vectors go straight into arrays.

_BULK_MODELS: dict[tuple, Any] = {}
_BULK_MODEL_LIMIT = 2


def _precision(torch, device: str, requested: str):
    if requested not in {"auto", "fp32", "bf16", "fp16"}:
        raise ValueError("precision must be auto, fp32, bf16 or fp16")
    cuda = device.startswith("cuda")
    if requested == "auto":
        requested = "bf16" if cuda and torch.cuda.is_bf16_supported() else "fp32"
    if requested != "fp32" and not cuda:
        raise ValueError(f"precision {requested} needs a CUDA device")
    return requested, {"fp32": torch.float32, "bf16": torch.bfloat16, "fp16": torch.float16}[requested]


def _bulk_model(processor_id: str, config: dict[str, Any]):
    """The model, verified and placed once per process. Returns (loaded, provenance additions)."""
    torch = importlib.import_module("torch")
    device, device_provenance = torch_device(torch, config)
    precision, dtype = _precision(torch, device, str(config.get("precision", "auto")))
    key = (processor_id, str(config.get("model_path")), config.get("model_sha256"), config.get("model_revision"), device, precision)
    if key in _BULK_MODELS:
        return _BULK_MODELS[key]
    path, model_provenance = _snapshot(processor_id, config)
    with _staged_snapshot(path, list(config.get("model_roots", [])), model_provenance["model_sha256"]) as staged:
        if processor_id == "embed.minilm":
            module = importlib.import_module("sentence_transformers")
            model = module.SentenceTransformer(str(staged), device=device, local_files_only=True, trust_remote_code=False)
            model.to(dtype=dtype)
            loaded = {"model": model, "torch": torch, "device": device, "dtype": dtype}
            version = package_version("sentence-transformers")
        else:
            transformers = importlib.import_module("transformers")
            processor = transformers.AutoProcessor.from_pretrained(str(staged), local_files_only=True, trust_remote_code=False, use_fast=False)
            model = transformers.AutoModel.from_pretrained(str(staged), local_files_only=True, trust_remote_code=False, use_safetensors=True,
                                                          dtype=dtype, attn_implementation="sdpa").to(device).eval()
            loaded = {"model": model, "processor": processor, "torch": torch, "device": device, "dtype": dtype}
            version = package_version("transformers")
    entry = (loaded, {**model_provenance, **device_provenance, "package_version": version, "precision": precision})
    while len(_BULK_MODELS) >= _BULK_MODEL_LIMIT:
        _BULK_MODELS.pop(next(iter(_BULK_MODELS)))
    _BULK_MODELS[key] = entry
    return entry


def _decode_image(asset, roots: list[str], max_pixels: int, size: tuple[int, int], resample: int):
    """Read, verify and resize one image to the model's input size (uint8 HxWx3) plus its content digest."""
    image, data = _load(asset, roots, max_pixels)
    digest = hashlib.sha256(data).hexdigest()
    if asset.sha256 and asset.sha256 != digest:
        raise ValueError("Asset sha256 mismatch")
    return np.asarray(image.resize(size, resample)), digest


def _unit_rows(array: np.ndarray, expected: int) -> np.ndarray:
    array = np.asarray(array, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != expected or not np.isfinite(array).all():
        raise ValueError(f"Embedding dimension must be {expected} and finite")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if (norms == 0).any():
        raise ValueError("Embedding has zero norm")
    return array / norms


def run_embeddings_bulk(processor_id: str, records: list, config: dict[str, Any], should_cancel=None):
    from concurrent.futures import ThreadPoolExecutor
    from .bulk import BulkResult
    recipe = RECIPES[processor_id]
    mode = str(config.get("representation", "text" if processor_id == "embed.minilm" else "image"))
    if mode not in ({"text", "question"} if processor_id == "embed.minilm" else {"image", "text", "question"}):
        raise ValueError("Invalid embedding representation")
    storage_dtype = str(config.get("storage_dtype", "float32"))
    if storage_dtype not in {"float32", "float16"}:
        raise ValueError("storage_dtype must be float32 or float16")
    loaded, extra = _bulk_model(processor_id, config)
    torch, model, device, dtype = loaded["torch"], loaded["model"], loaded["device"], loaded["dtype"]
    provenance = {**extra, "recipe": {**recipe, "representation": mode, "normalization": "L2", "distance_metric": "cosine",
                                      "truncation": "model tokenizer default", "text_instruction": "none"}}
    provenance["embedding_space_id"] = content_id(provenance["recipe"], "space:")
    if processor_id == "embed.siglip2":
        provenance["shared_encoder_id"] = content_id({key: provenance["recipe"][key] for key in
                                                       ("model_id", "revision", "dimension", "pooling", "normalization", "distance_metric")}, "encoder:")
    provenance.update({"storage_dtype": storage_dtype, "path": "columnar", "unique_inputs_only": True})
    ids: list[str] = []
    skipped: dict[str, dict[str, Any]] = {}
    chunks: list[np.ndarray] = []

    def skip(record, status: str, error: str | None = None):
        skipped[record.id] = {"status": status, **({"error": error} if error else {})}

    if mode == "image":
        batch = int(config.get("batch_size", 256))
        roots = list(config.get("asset_roots", []))
        max_pixels = int(config.get("max_pixels", 50_000_000))
        extractor = loaded["processor"].image_processor
        size = (int(extractor.size["width"]), int(extractor.size["height"]))
        mean = torch.tensor(extractor.image_mean, device=device, dtype=torch.float32).view(1, 3, 1, 1)
        std = torch.tensor(extractor.image_std, device=device, dtype=torch.float32).view(1, 3, 1, 1)
        scale = float(extractor.rescale_factor)
        provenance["preprocessing"] = {"resize": list(size), "resample": int(extractor.resample), "mean": list(extractor.image_mean),
                                       "std": list(extractor.image_std), "rescale": scale, "implementation": "PIL resize, GPU normalise (parity-tested against the model processor)"}
        wanted: dict[str, Any] = {}  # asset id -> asset, for records with exactly one image
        for record in records:
            images = [asset for asset in record.assets if asset.modality.lower() in {"image", "photo"}]
            if not images:
                skip(record, "skipped" if record.asset_ids and not record.assets else "not_applicable",
                     "Asset metadata was not loaded" if record.asset_ids and not record.assets else None)
            elif len(images) > 1:
                skip(record, "skipped", "Record has several images; columnar runs embed one image per record (use the asset unit)")
            else:
                wanted.setdefault(images[0].id, images[0])
        workers = min(int(config.get("decode_threads", 8)), os.cpu_count() or 1)  # more threads fight over the GIL and are slower
        results: dict[str, Any] = {}
        digest_row: dict[str, int] = {}
        vectors: list[np.ndarray] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            order = list(wanted.values())
            futures = {}
            window = max(batch * 2, workers * 4)
            def submit_upto(position: int):
                while len(futures) < window and submit_upto.next < len(order):
                    asset = order[submit_upto.next]
                    futures[asset.id] = pool.submit(_decode_image, asset, roots, max_pixels, size, int(extractor.resample))
                    submit_upto.next += 1
            submit_upto.next = 0
            pending_arrays: list[np.ndarray] = []
            pending_digests: list[str] = []
            def flush():
                if not pending_arrays:
                    return
                pixels = torch.from_numpy(np.stack(pending_arrays)).to(device, non_blocking=True).permute(0, 3, 1, 2).float()
                pixels = ((pixels * scale - mean) / std).to(dtype)
                with torch.inference_mode():
                    features = _pooled_features(model.get_image_features(pixel_values=pixels)).float()
                rows = _unit_rows(features.cpu().numpy(), recipe["dimension"])
                for digest, row in zip(pending_digests, rows):
                    digest_row[digest] = len(vectors)
                    vectors.append(row)
                pending_arrays.clear()
                pending_digests.clear()
            for position, asset in enumerate(order):
                submit_upto(position)
                try:
                    array, digest = futures.pop(asset.id).result()
                except (OSError, ValueError, RuntimeError, TypeError) as exc:
                    results[asset.id] = ("failed", f"{type(exc).__name__}: {exc}")
                    continue
                if digest not in digest_row and digest not in pending_digests:
                    pending_arrays.append(array)
                    pending_digests.append(digest)
                results[asset.id] = ("ok", digest)
                if len(pending_arrays) >= batch:
                    flush()
            flush()
        by_asset = {asset_id: value for asset_id, value in results.items()}
        rows: list[int] = []
        for record in records:
            if record.id in skipped:
                continue
            asset = next(a for a in record.assets if a.modality.lower() in {"image", "photo"})
            state, value = by_asset[asset.id]
            if state == "failed":
                skip(record, "failed", value)
            else:
                ids.append(record.id)
                rows.append(digest_row[value])
        matrix = np.stack(vectors)[rows] if rows else np.zeros((0, recipe["dimension"]), dtype=np.float32)
    else:
        texts, owners = [], []
        for record in records:
            value = getattr(record, mode)
            if isinstance(value, str) and value.strip():
                texts.append(value)
                owners.append(record)
            else:
                skip(record, "not_applicable")
        batch = int(config.get("batch_size", 1024))
        pieces = []
        for start in range(0, len(texts), batch):
            part = texts[start:start + batch]
            if processor_id == "embed.minilm":
                raw = model.encode(part, batch_size=batch, convert_to_numpy=True, normalize_embeddings=False, show_progress_bar=False)
            else:
                inputs = loaded["processor"](text=part, return_tensors="pt", padding="max_length", truncation=True, max_length=64)
                inputs = {key: value.to(device) for key, value in inputs.items()}
                with torch.inference_mode():
                    raw = _pooled_features(model.get_text_features(**inputs)).float().cpu().numpy()
            pieces.append(_unit_rows(raw, recipe["dimension"]))
        matrix = np.concatenate(pieces) if pieces else np.zeros((0, recipe["dimension"]), dtype=np.float32)
        ids = [record.id for record in owners]
    out = BulkResult(ids=ids, arrays={"vector": matrix.astype(storage_dtype)}, provenance=provenance, skipped=skipped)
    return out, provenance
