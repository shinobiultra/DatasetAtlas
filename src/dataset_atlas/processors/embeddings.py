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
