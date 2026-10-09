"""Small common run protocol for built-in processors.

The jobs service owns durable Run and Artifact registration. This module returns a
JSON-compatible artifact body and never mutates source records or downloads models.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib import metadata, util
from typing import Any

from dataset_atlas.models import Record


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


DESCRIPTIONS: dict[str, dict[str, Any]] = {
    "quality.basic": {"name": "Image quality and fingerprints", "unit": "example", "input_units": ["example", "asset"], "dependencies": ["Pillow"], "output_schema": "quality.v1", "batching": "records", "device": "cpu"},
    "detect.nudenet": {"name": "NudeNet detector", "unit": "example", "input_units": ["example", "asset"], "dependencies": ["nudenet"], "output_schema": "detections.v1", "batching": "assets", "device": "cpu"},
    "detect.coco_v1": {"name": "Faster R-CNN MobileNet V3 COCO_V1", "unit": "example", "input_units": ["example", "asset"], "dependencies": ["torch", "torchvision"], "output_schema": "detections.v1", "batching": "assets", "device": "cpu"},
    "detect.view": {"name": "Adjust retained detector threshold", "unit": "example", "input_units": ["example", "asset"], "dependencies": [], "output_schema": "detections.v1", "batching": "selection", "device": "cpu"},
    "embed.minilm": {"name": "MiniLM text embeddings", "unit": "example", "input_units": ["example"], "dependencies": ["sentence_transformers"], "output_schema": "embedding.v1", "batching": "records", "device": "cpu"},
    "embed.siglip2": {"name": "SigLIP 2 image/text embeddings", "unit": "example", "input_units": ["example", "asset"], "dependencies": ["torch", "transformers"], "output_schema": "embedding.v1", "batching": "assets", "device": "cpu"},
    "project.pca": {"name": "PCA projection", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": ["numpy"], "output_schema": "projection.v1", "batching": "selection", "device": "cpu"},
    "project.umap": {"name": "UMAP projection", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": ["umap-learn"], "output_schema": "projection.v1", "batching": "selection", "device": "cpu"},
    "cluster.kmeans": {"name": "K-means clustering", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": ["numpy"], "output_schema": "cluster.v1", "batching": "selection", "device": "cpu"},
    "outlier.knn": {"name": "Original-space neighbour distance", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": ["numpy"], "output_schema": "outlier.v1", "batching": "selection", "device": "cpu"},
    "compare.fields": {"name": "Field comparison", "unit": "example", "input_units": ["example"], "dependencies": [], "output_schema": "comparison.v1", "batching": "selection", "device": "cpu"},
    "import.research": {"name": "Import research outputs", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": [], "output_schema": "import.v1", "batching": "selection", "device": "cpu"},
}

DEPENDENCY_MODULES = {"Pillow": "PIL", "umap-learn": "umap", "sentence_transformers": "sentence_transformers"}


def describe_processors() -> list[dict[str, Any]]:
    descriptions = []
    for processor_id, base in DESCRIPTIONS.items():
        missing = [name for name in base["dependencies"] if util.find_spec(DEPENDENCY_MODULES.get(name, name)) is None]
        descriptions.append({"id": processor_id, **base, "available": not missing, "missing_dependencies": missing,
                             "requires_local_model": processor_id != 'detect.view' and processor_id.startswith(("detect.", "embed."))})
        if processor_id in {'detect.coco_v1','embed.siglip2','embed.minilm'}:
            descriptions[-1]['supported_devices']=['auto','cpu','cuda','mps']
    return descriptions


class Processor:
    def __init__(self, processor_id: str):
        if processor_id not in DESCRIPTIONS:
            raise ValueError(f"Unknown trusted processor: {processor_id}")
        self.id = processor_id

    def describe(self) -> dict[str, Any]:
        return next(row for row in describe_processors() if row["id"] == self.id)

    def validate_inputs(self, selection: Sequence[Record | dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        records = [r if isinstance(r, Record) else Record.model_validate(r) for r in selection]
        maximum = int((config or {}).get("max_records", 1000))
        if maximum < 1 or maximum > 100_000:
            raise ValueError("max_records must be within 1..100000")
        if len(records) > maximum:
            raise ValueError("Selection exceeds processor max_records")
        if len({r.id for r in records}) != len(records):
            raise ValueError("Selection has duplicate record IDs")
        if len({r.unit for r in records}) > 1:
            raise ValueError("Processor selection must have one sample unit")
        supported = self.describe()["input_units"]
        if any(r.unit not in supported for r in records):
            raise ValueError(f"Processor {self.id} does not support this sample unit")
        return {"valid": True, "record_count": len(records), "unit": records[0].unit if records else "example"}

    def estimate(self, selection: Sequence[Record | dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        description=self.describe()
        return {"records": len(selection), "device": (config or {}).get('device','auto' if description.get('supported_devices') else description['device']), "remote_calls": 0,
                "model_download_bytes": 0}

    def run_batch(self, inputs: Sequence[Record | dict[str, Any]], config: dict[str, Any] | None = None,
                  *, should_cancel: Callable[[], bool] | None = None) -> dict[str, Any]:
        return run_processor(self.id, inputs, config, should_cancel=should_cancel)


def get_processor(processor_id: str) -> Processor:
    return Processor(processor_id)


def run_processor(processor_id: str, records: Sequence[Record | dict[str, Any]], config: dict[str, Any] | None = None,
                  *, should_cancel: Callable[[], bool] | None = None) -> dict[str, Any]:
    processor = get_processor(processor_id)
    config = dict(config or {})
    report = processor.validate_inputs(records, config)
    parsed = [r if isinstance(r, Record) else Record.model_validate(r) for r in records]
    if processor_id in {"quality.basic", "detect.nudenet", "detect.coco_v1"}:
        from .vision import run_vision
        items, provenance = run_vision(processor_id, parsed, config, should_cancel)
    elif processor_id == 'detect.view':
        from .detector_view import run_detector_view
        items, provenance = run_detector_view(parsed, config)
    elif processor_id.startswith("embed."):
        from .embeddings import run_embeddings
        items, provenance = run_embeddings(processor_id, parsed, config, should_cancel)
    elif processor_id == "import.research":
        from .research_import import run_import
        items, provenance = run_import(parsed, config)
    else:
        from .analysis import run_analysis
        items, provenance = run_analysis(processor_id, parsed, config)
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"processor_id": processor_id, "schema_version": "1.0", "unit": report["unit"], "items": items,
            "provenance": {"processor_version": "1.0", **provenance},
            "coverage": {"selected": len(parsed), "statuses": counts}}
