"""Small common run protocol for built-in processors.

The jobs service owns durable Run and Artifact registration. This module returns a
JSON-compatible artifact body and never mutates source records or downloads models.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from importlib import metadata, util
from typing import Any, NamedTuple

from dataset_atlas.models import Record
from .bulk import BulkResult


class IdentityRecord(NamedTuple):
    """The five identity fields. Columnar analysis reads vectors by id and never touches record content,
    and building a pydantic Record per row is what dominates at hundreds of thousands of rows."""
    id: str
    dataset_id: str
    release_id: str
    snapshot_id: str
    unit: str = "example"


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
    "cluster.hdbscan": {"name": "HDBSCAN density clustering", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": ["scikit-learn"], "output_schema": "cluster.v1", "batching": "selection", "device": "cpu"},
    "cluster.agglomerative": {"name": "Agglomerative (hierarchical) clustering", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": ["scikit-learn"], "output_schema": "cluster.v1", "batching": "selection", "device": "cpu"},
    "outlier.knn": {"name": "Original-space neighbour distance", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": ["numpy"], "output_schema": "outlier.v1", "batching": "selection", "device": "cpu"},
    "vlm.answer": {"name": "Answer questions with a model server", "unit": "example", "input_units": ["example"], "dependencies": ["httpx"], "output_schema": "text.v1", "batching": "records", "device": "cpu"},
    "vlm.tag": {"name": "Tag or classify with a model server", "unit": "example", "input_units": ["example"], "dependencies": ["httpx"], "output_schema": "text.v1", "batching": "records", "device": "cpu"},
    "vlm.judge": {"name": "Judge saved answers with a model server", "unit": "example", "input_units": ["example"], "dependencies": ["httpx"], "output_schema": "text.v1", "batching": "records", "device": "cpu"},
    "embed.api": {"name": "Embeddings from a model server", "unit": "example", "input_units": ["example"], "dependencies": ["httpx"], "output_schema": "embedding.v1", "batching": "records", "device": "cpu"},
    "score.vqa_accuracy": {"name": "VQA accuracy of saved answers", "unit": "example", "input_units": ["example"], "dependencies": ["numpy"], "output_schema": "score.v1", "batching": "selection", "device": "cpu"},
    "compare.fields": {"name": "Field comparison", "unit": "example", "input_units": ["example"], "dependencies": [], "output_schema": "comparison.v1", "batching": "selection", "device": "cpu"},
    "import.research": {"name": "Import research outputs", "unit": "example", "input_units": ["example", "asset", "entity", "conversation"], "dependencies": [], "output_schema": "import.v1", "batching": "selection", "device": "cpu"},
}

DEPENDENCY_MODULES = {"Pillow": "PIL", "umap-learn": "umap", "scikit-learn": "sklearn", "sentence_transformers": "sentence_transformers"}

# Which optional extra of pyproject.toml provides each import, so an unavailable processor can say how to get it.
DEPENDENCY_EXTRAS = {"nudenet": "vision", "torch": "vision", "torchvision": "vision", "sentence_transformers": "embeddings",
                     "transformers": "embeddings", "umap-learn": "projection", "scikit-learn": "projection"}


# Analysis processors and the engines method that does their numeric work.
ANALYSIS_METHODS = {"project.pca": "pca", "project.umap": "umap", "cluster.kmeans": "kmeans", "cluster.hdbscan": "hdbscan",
                    "cluster.agglomerative": "agglomerative", "outlier.knn": "knn"}


def backend_choices(method: str) -> list[dict[str, Any]]:
    """Which backends exist for a method and whether each is installed (import-free, so the API never loads CUDA)."""
    from . import engines
    installed = {"cpu": True, "torch": engines._have("torch"), "cuml": engines._have("cuml")}
    return [{"id": name, "installed": installed[name], "needs_device": name != "cpu"} for name in engines.BACKENDS[method]]


def unavailable_reason(missing: Sequence[str]) -> str:
    """Name the missing packages and the command that restores them.

    A bare `uv sync` is exact and removes every extra that is not named, so the advice
    installs all of them rather than the one that is missing.
    """
    extras = sorted({DEPENDENCY_EXTRAS[name] for name in missing if name in DEPENDENCY_EXTRAS})
    needs = f"the {' and '.join(extras)} extra{'s' if len(extras) > 1 else ''}" if extras else "an optional package"
    return (f"Not installed: {', '.join(missing)}. It comes with {needs}. From a checkout run `uv sync --all-extras` "
            f"(a plain `uv sync` removes the extras; without an NVIDIA GPU you can skip the large gpu extra by naming the others), "
            f"or `pip install \"dataset-atlas[{','.join(extras)}]\"`, then restart `atlas serve`.")


def describe_processors() -> list[dict[str, Any]]:
    descriptions = []
    for processor_id, base in DESCRIPTIONS.items():
        missing = [name for name in base["dependencies"] if util.find_spec(DEPENDENCY_MODULES.get(name, name)) is None]
        descriptions.append({"id": processor_id, **base, "available": not missing, "missing_dependencies": missing,
                             **({"reason": unavailable_reason(missing)} if missing else {}),
                             "requires_local_model": processor_id != 'detect.view' and processor_id != 'embed.api' and processor_id.startswith(("detect.", "embed."))})
        if processor_id in {'detect.coco_v1','embed.siglip2','embed.minilm'}:
            descriptions[-1]['supported_devices']=['auto','cpu','cuda','mps']
        method = ANALYSIS_METHODS.get(processor_id)
        if method:
            descriptions[-1]['backends'] = backend_choices(method)
    return descriptions


class Processor:
    def __init__(self, processor_id: str):
        if processor_id not in DESCRIPTIONS:
            raise ValueError(f"Unknown trusted processor: {processor_id}")
        self.id = processor_id

    def describe(self) -> dict[str, Any]:
        return next(row for row in describe_processors() if row["id"] == self.id)

    def validate_inputs(self, selection: Sequence[Record | dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        records = [r if isinstance(r, (Record, IdentityRecord)) else Record.model_validate(r) for r in selection]
        ceiling = 2_000_000 if (config or {}).get("storage") == "arrays" else 100_000
        maximum = int((config or {}).get("max_records", ceiling if (config or {}).get("storage") == "arrays" else 1000))
        if maximum < 1 or maximum > ceiling:
            raise ValueError(f"max_records must be within 1..{ceiling}")
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
        base = {"records": len(selection), "device": (config or {}).get('device','auto' if description.get('supported_devices') else description['device']), "remote_calls": 0,
                "model_download_bytes": 0}
        if self.id.startswith("vlm.") or self.id == "embed.api":
            from .vlm import estimate_model_run
            return {**base, **estimate_model_run(self.id, list(selection), config or {})}
        return base

    def run_batch(self, inputs: Sequence[Record | dict[str, Any]], config: dict[str, Any] | None = None,
                  *, should_cancel: Callable[[], bool] | None = None) -> dict[str, Any]:
        return run_processor(self.id, inputs, config, should_cancel=should_cancel)


def get_processor(processor_id: str) -> Processor:
    return Processor(processor_id)


def run_processor(processor_id: str, records: Sequence[Record | dict[str, Any]], config: dict[str, Any] | None = None,
                  *, should_cancel: Callable[[], bool] | None = None) -> dict[str, Any]:
    processor = get_processor(processor_id)
    config = dict(config or {})
    if config.get("storage") == "arrays" and processor_id.startswith(("project.", "cluster.", "outlier.")):
        # These read vectors by id and never touch record content; the coordinator has already validated the records.
        parsed = [r if isinstance(r, (Record, IdentityRecord)) else IdentityRecord(r["id"], r["dataset_id"], r["release_id"], r["snapshot_id"], r.get("unit", "example"))
                  for r in records]
    else:
        parsed = [r if isinstance(r, Record) else Record.model_validate(r) for r in records]
    report = processor.validate_inputs(parsed, config)
    if processor_id in {"quality.basic", "detect.nudenet", "detect.coco_v1"}:
        from .vision import run_vision
        items, provenance = run_vision(processor_id, parsed, config, should_cancel)
    elif processor_id == 'detect.view':
        from .detector_view import run_detector_view
        items, provenance = run_detector_view(parsed, config)
    elif processor_id.startswith("vlm."):
        from .vlm import run_model_task
        items, provenance = run_model_task(processor_id, parsed, config)
    elif processor_id == "embed.api":
        from .vlm import run_api_embeddings
        items, provenance = run_api_embeddings(parsed, config)
    elif processor_id == "score.vqa_accuracy":
        from .vlm import run_vqa_scoring
        items, provenance = run_vqa_scoring(parsed, config)
    elif processor_id.startswith("embed."):
        if config.get("storage") == "arrays":
            from .embeddings import run_embeddings_bulk
            items, provenance = run_embeddings_bulk(processor_id, parsed, config, should_cancel)
        else:
            from .embeddings import run_embeddings
            items, provenance = run_embeddings(processor_id, parsed, config, should_cancel)
    elif processor_id == "import.research":
        from .research_import import run_import
        items, provenance = run_import(parsed, config)
    else:
        from .analysis import run_analysis
        items, provenance = run_analysis(processor_id, parsed, config)
    if isinstance(items, BulkResult):
        items.check([record.id for record in parsed])
        statuses = {"completed": len(items.ids), **dict(Counter(row["status"] for row in items.skipped.values()))}
        return {"processor_id": processor_id, "schema_version": "1.0", "unit": report["unit"], "items": [], "bulk": items,
                "provenance": {"processor_version": "1.0", **provenance},
                "coverage": {"selected": len(parsed), "statuses": statuses}}
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"processor_id": processor_id, "schema_version": "1.0", "unit": report["unit"], "items": items,
            "provenance": {"processor_version": "1.0", **provenance},
            "coverage": {"selected": len(parsed), "statuses": counts}}
