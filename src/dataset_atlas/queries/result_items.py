"""Per-record result items of any artifact, whether stored as JSON items or as arrays.

JSON artifacts carry ``data["items"]``. Array-backed artifacts carry ``data["bulk"]`` and no items,
so this yields the same item dicts lazily from the arrays: one-dimensional arrays become one
scalar each, and a ``coords`` matrix becomes ``x``, ``y`` (and ``z``). Records that were skipped
or failed appear with their status, as they do in JSON artifacts. Consumers that join results onto
records, filter on them or hand them to tools use this instead of reading ``data["items"]``.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

import numpy as np

from dataset_atlas.models import Artifact
from dataset_atlas.storage import arrays as store
from .embedding_space import bulk_directory

_AXES = "xyz"
_BLOCK = 50_000


def bulk_columns(artifact: Artifact) -> dict[str, tuple[str, int | None]]:
    """Scalar result columns of an array-backed artifact: output key -> (array name, column or None)."""
    columns: dict[str, tuple[str, int | None]] = {}
    for name, entry in artifact.data["bulk"]["arrays"].items():
        shape = entry["shape"]
        if len(shape) == 1:
            columns[name] = (name, None)
        elif name == "coords" and len(shape) == 2 and shape[1] <= len(_AXES):
            columns.update({_AXES[axis]: (name, axis) for axis in range(shape[1])})
        # Other matrices (embedding vectors) are not scalar results and never were in JSON items either.
    return columns


def result_items(artifact: Artifact, only: set[str] | None = None) -> Iterable[dict[str, Any]]:
    bulk = artifact.data.get("bulk")
    if not isinstance(bulk, dict):
        items = artifact.data.get("items", [])
        return items if only is None else [item for item in items if item.get("id") in only]
    return _bulk_items(artifact, bulk, only)


def _bulk_items(artifact: Artifact, bulk: dict[str, Any], only: set[str] | None) -> Iterator[dict[str, Any]]:
    directory = bulk_directory(artifact)
    ids = store.read_ids(directory, bulk)
    columns = bulk_columns(artifact)
    arrays = {name: store.read_array(directory, bulk["arrays"][name]) for name in {name for name, _ in columns.values()}}
    for start in range(0, len(ids), _BLOCK):
        block = slice(start, start + _BLOCK)
        values = {key: (arrays[name][block] if axis is None else arrays[name][block, axis]).tolist() for key, (name, axis) in columns.items()}
        for offset, record_id in enumerate(ids[block]):
            if only is None or record_id in only:
                yield {"id": record_id, "status": "completed", "output": {key: column[offset] for key, column in values.items()}}
    skipped_file = directory / "skipped.json"
    if skipped_file.is_file():
        for record_id, row in json.loads(skipped_file.read_text(encoding="utf-8")).items():
            if only is None or record_id in only:
                yield {"id": record_id, "status": row.get("status", "failed"), "output": None, **({"error": row["error"]} if row.get("error") else {})}


def has_items(artifact: Artifact) -> bool:
    return isinstance(artifact.data.get("bulk"), dict) or "items" in artifact.data
