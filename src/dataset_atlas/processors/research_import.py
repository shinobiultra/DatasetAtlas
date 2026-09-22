"""Validate externally computed result rows without executing research code."""
from __future__ import annotations

import json
import math
from typing import Any

from dataset_atlas.models import Record


def _validate_value(value: Any, kind: str, dimension: int | None) -> Any:
    if kind == "scalar":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Scalar import values must be finite numbers")
        return float(value)
    if kind == "categorical":
        if not isinstance(value, (str, bool, int)) or len(str(value)) > 1000:
            raise ValueError("Categorical import values must be short strings, booleans, or integers")
        return value
    if kind == "vector":
        if not isinstance(value, list) or dimension is None or len(value) != dimension:
            raise ValueError("Vector dimension mismatch")
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
            raise ValueError("Vectors must contain finite numbers")
        return [float(x) for x in value]
    if kind == "region":
        if not isinstance(value, list) or len(value) > 1000:
            raise ValueError("Regions must be a bounded list")
        for region in value:
            if not isinstance(region, dict) or not isinstance(region.get("box"), list) or len(region["box"]) != 4:
                raise ValueError("Each region needs an xyxy box")
            coords = region["box"]
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in coords):
                raise ValueError("Region coordinates must be finite")
            if coords[0] >= coords[2] or coords[1] >= coords[3]:
                raise ValueError("Region box has non-positive area")
        return value
    if kind == "response":
        if not isinstance(value, (str, dict, list)) or len(json.dumps(value, ensure_ascii=False, allow_nan=False)) > 100_000:
            raise ValueError("Model response must be bounded JSON or text")
        return value
    raise ValueError("Unsupported imported result kind")


def run_import(records: list[Record], config: dict[str, Any]):
    rows = config.get("rows")
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise ValueError("Import rows must be a bounded list")
    if len(json.dumps(rows, ensure_ascii=False, allow_nan=False)) > 20_000_000:
        raise ValueError("Import exceeds 20 MB JSON bound")
    field_id = config.get("field_id")
    if not isinstance(field_id, str) or not field_id.startswith("prediction.") or not field_id.removeprefix("prediction.") or len(field_id) > 200 or field_id.count(".") != 1:
        raise ValueError("Imported field_id must be prediction.<name>")
    kind = config.get("kind")
    dimension = config.get("dimension")
    if kind == "vector":
        if not isinstance(dimension, int) or isinstance(dimension, bool) or not 1 <= dimension <= 4096:
            raise ValueError("Vector import requires dimension within 1..4096")
    if kind == "region" and config.get("coordinate_space") not in {"xyxy_pixels_exif_transposed", "xyxy_normalized"}:
        raise ValueError("Region import requires an explicit coordinate_space")
    source = config.get("source_reference")
    if not isinstance(source, str) or not source.strip() or len(source) > 2048:
        raise ValueError("Import requires a source_reference")
    rights = config.get("rights")
    if rights not in {"private", "approved_for_publication"}:
        raise ValueError("Import requires explicit private or approved_for_publication rights")
    record_ids = {record.id for record in records}
    units = {record.unit for record in records}
    if len(units) > 1:
        raise ValueError("Import selection contains mixed units")
    imported: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or "value" not in row:
            raise ValueError("Every import row needs stable id and value")
        item_id = row["id"]
        if item_id not in record_ids:
            raise ValueError(f"Import row ID is outside frozen selection: {item_id}")
        if item_id in imported:
            raise ValueError(f"Duplicate imported row ID: {item_id}")
        if row.get("unit", next(iter(units), "example")) != next(iter(units), "example"):
            raise ValueError("Imported row sample unit differs from selection")
        imported[item_id] = _validate_value(row["value"], kind, dimension)
    items = [{"id": record.id, "status": "completed", "output": {"field_id": field_id, "value": imported[record.id]}}
             if record.id in imported else {"id": record.id, "status": "not_applicable", "output": None}
             for record in records]
    provenance = {"field_id": field_id, "kind": kind, "dimension": dimension, "source_reference": source,
                  "rights": rights, "coordinate_space": config.get("coordinate_space"),
                  "sample_unit": next(iter(units), "example"), "snapshot_ids": sorted({r.snapshot_id for r in records}),
                  "selection_ids": [r.id for r in records], "imported_count": len(imported),
                  "missing_count": len(records) - len(imported)}
    return items, provenance
