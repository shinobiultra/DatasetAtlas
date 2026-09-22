"""Read-only local image quality and detector adapters."""
from __future__ import annotations

import hashlib
import importlib
import io
import math
from pathlib import Path
import tempfile
from typing import Any
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from dataset_atlas.models import Asset, Record
from dataset_atlas.storage.local import read_rooted_file
from .core import package_version


def _load(asset: Asset, roots: list[str], max_pixels: int) -> tuple[Image.Image, bytes]:
    if not asset.uri or "://" in asset.uri:
        raise ValueError("Image asset has no permitted local URI")
    data = read_rooted_file(asset.uri, roots, max_bytes=100_000_000)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as source:
            if source.width * source.height > max_pixels:
                raise ValueError("Image exceeds max_pixels")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.load()
    return image, data


def _dhash(image: Image.Image) -> str:
    sample = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(sample.get_flattened_data())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return f"{bits:016x}"


def _box_xyxy(values: list[float], width: int, height: int) -> list[float]:
    x1, y1, x2, y2 = map(float, values)
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
        raise ValueError("Non-finite detection box")
    return [max(0.0, min(float(width), x1)), max(0.0, min(float(height), y1)),
            max(0.0, min(float(width), x2)), max(0.0, min(float(height), y2))]


def _normalize_nudenet(raw: list[dict[str, Any]], width: int, height: int, threshold: float) -> list[dict[str, Any]]:
    result = []
    for row in raw:
        score = float(row["score"])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Non-finite or invalid detection score")
        if score < threshold:
            continue
        x, y, w, h = map(float, row["box"])
        box = _box_xyxy([x, y, x + w, y + h], width, height)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        result.append({"class": str(row["class"]), "score": score, "box": box})
    return result


def _normalize_coco(raw: dict[str, Any], categories: list[str], width: int, height: int,
                    threshold: float) -> list[dict[str, Any]]:
    result = []
    for label, score, coords in zip(raw["labels"], raw["scores"], raw["boxes"]):
        value = float(score)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Non-finite or invalid detection score")
        if value < threshold:
            continue
        index = int(label)
        if index < 0 or index >= len(categories):
            raise ValueError("Detector returned unknown COCO class")
        box = _box_xyxy(list(coords), width, height)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        result.append({"class": categories[index], "class_id": index, "score": value, "box": box})
    return result


def _model(processor_id: str, config: dict[str, Any]):
    model_roots = list(config.get("model_roots", []))

    def read_weights(path: Path) -> bytes:
        if model_roots:
            return read_rooted_file(path, model_roots, max_bytes=2_000_000_000)
        if not path.is_file() or path.stat().st_size > 2_000_000_000:
            raise ValueError("Local model file missing or exceeds 2 GB bound")
        return path.read_bytes()

    if processor_id == "detect.nudenet":
        module = importlib.import_module("nudenet")
        weights_path = Path(str(config.get("model_path", ""))).expanduser()
        weights_data = read_weights(weights_path)
        digest = hashlib.sha256(weights_data).hexdigest()
        if digest != config.get("model_sha256"):
            raise ValueError("NudeNet model_sha256 mismatch")
        with tempfile.TemporaryDirectory(prefix="atlas-nudenet-model-") as temporary:
            staged = Path(temporary) / "model.onnx"
            staged.write_bytes(weights_data)
            detector = module.NudeDetector(model_path=str(staged))
        return detector, {"model_id": "nudenet", "model_sha256": digest, "package_version": package_version("nudenet")}
    torch = importlib.import_module("torch")
    detection = importlib.import_module("torchvision.models.detection")
    weights = detection.FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.COCO_V1
    path = Path(str(config.get("weights_path", ""))).expanduser()
    weights_data = read_weights(path)
    digest = hashlib.sha256(weights_data).hexdigest()
    if digest != config.get("weights_sha256") or not digest.startswith("907ea3f9"):
        raise ValueError("COCO_V1 weights_sha256 mismatch or wrong weight revision")
    model = detection.fasterrcnn_mobilenet_v3_large_320_fpn(weights=None, weights_backbone=None)
    model.load_state_dict(torch.load(io.BytesIO(weights_data), map_location="cpu", weights_only=True))
    model.eval()
    return (model, weights), {"model_id": "torchvision/fasterrcnn_mobilenet_v3_large_320_fpn", "weight_revision": "COCO_V1",
                              "weights_sha256": digest, "package_version": package_version("torchvision")}


def run_vision(processor_id: str, records: list[Record], config: dict[str, Any], should_cancel=None):
    roots = list(config.get("asset_roots", []))
    max_pixels = int(config.get("max_pixels", 50_000_000))
    if max_pixels < 1 or max_pixels > 100_000_000:
        raise ValueError("max_pixels must be within 1..100000000")
    threshold = float(config.get("extraction_threshold", 0.25 if processor_id == "detect.nudenet" else 0.05))
    if not 0 <= threshold <= 1:
        raise ValueError("extraction_threshold must be within 0..1")
    if processor_id == "detect.nudenet" and threshold < 0.25:
        raise ValueError("NudeNet's internal NMS threshold is 0.25; extraction_threshold cannot be lower")
    model = None
    provenance: dict[str, Any] = {"input_representation": "local original image, EXIF-transposed RGB", "max_pixels": max_pixels}
    if processor_id != "quality.basic":
        model, model_provenance = _model(processor_id, config)
        provenance.update(model_provenance)
        provenance["extraction_threshold"] = threshold
        if processor_id == "detect.nudenet":
            provenance["model_internal_threshold"] = 0.25
        provenance["box_coordinates"] = "xyxy pixels in EXIF-transposed image"
    cache: dict[str, dict[str, Any]] = {}
    items = []
    for record in records:
        if should_cancel and should_cancel():
            items.append({"id": record.id, "status": "not_scheduled", "output": None, "error": "cancelled"})
            continue
        image_assets = [a for a in record.assets if a.modality.lower() in {"image", "photo"}]
        if not image_assets:
            if record.asset_ids and not record.assets:
                items.append({"id": record.id, "status": "skipped", "output": None, "error": "Asset metadata was not loaded"})
            else:
                items.append({"id": record.id, "status": "not_applicable", "output": None})
            continue
        asset_results = []
        for asset in image_assets:
            try:
                image, data = _load(asset, roots, max_pixels)
                digest = hashlib.sha256(data).hexdigest()
                if asset.sha256 and asset.sha256 != digest:
                    raise ValueError("Asset sha256 mismatch")
                if digest in cache:
                    result = dict(cache[digest])
                    result["asset_id"] = asset.id
                    asset_results.append(result)
                    continue
                width, height = image.size
                if processor_id == "quality.basic":
                    output = {"width": width, "height": height, "aspect_ratio": width / height,
                              "file_sha256": digest,
                              "pixel_sha256": hashlib.sha256(f"RGB:{width}x{height}:".encode() + image.tobytes()).hexdigest(), "dhash64": _dhash(image)}
                elif processor_id == "detect.nudenet":
                    with tempfile.TemporaryDirectory(prefix="atlas-nudenet-") as temporary:
                        target = Path(temporary) / "input.png"
                        image.save(target)
                        raw = model.detect(str(target))
                    detections = _normalize_nudenet(raw, width, height, threshold)
                    output = {"width": width, "height": height, "file_sha256": digest, "detections": detections}
                else:
                    torch = importlib.import_module("torch")
                    detector, weights = model
                    with torch.inference_mode():
                        predicted = detector([weights.transforms()(image)])[0]
                    raw = {key: predicted[key].detach().cpu().tolist() for key in ("labels", "scores", "boxes")}
                    detections = _normalize_coco(raw, weights.meta["categories"], width, height, threshold)
                    output = {"width": width, "height": height, "file_sha256": digest, "detections": detections}
                result = {"asset_id": asset.id, "status": "completed", **output}
                cache[digest] = result
            except (OSError, ValueError, UnidentifiedImageError, KeyError, TypeError, RuntimeError) as exc:
                result = {"asset_id": asset.id, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            asset_results.append(result)
        completed = [a for a in asset_results if a["status"] == "completed"]
        if completed:
            status = "completed"
        else:
            status = "failed"
        output: dict[str, Any] = {"assets": asset_results}
        if processor_id.startswith("detect."):
            unique = {asset["file_sha256"]: asset for asset in completed}
            detections = [d for asset in unique.values() for d in asset["detections"]]
            output["derived"] = {"detection_count_v1": len(detections),
                                 "max_score_v1": max((d["score"] for d in detections), default=None),
                                 "detection_coverage_complete_v1": len(completed) == len(asset_results)}
            if processor_id == "detect.coco_v1":
                output["derived"]["person_count_v1"] = sum(1 for d in detections if d["class"] == "person")
        items.append({"id": record.id, "status": status, "output": output})
    return items, provenance
