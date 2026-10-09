"""The public guide: what a visitor to the static site can do about each dataset, built only from allowlisted fields.

The static site holds no dataset content beyond the approved previews. This module adds what is still useful without it: how a
researcher gets each dataset (the state is computed from the registry and recipes, never written by hand), which corpus papers name
it, and, for datasets the maintainers have prepared, the field schema of the preview (names, types, declared categories; no record
values). Schemas are produced from local packs by `write_schemas` and committed under `examples/public-schema/`, so the public build
needs neither the packs nor the workspace.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from dataset_atlas.models import Dataset, FieldDescriptor, Pack

from .security import ExchangeError, compact_json, read_json, scan_public

SCHEMA_VERSION = "1.0"
MAX_FIELDS = 200
MAX_VALUES = 30
MAX_SCHEMA_BYTES = 200_000
_SAMPLING_KEYS = ("method", "seed", "grouping", "population_count", "requested_count", "returned_count", "rows_drawn",
                  "row_groups_in_population", "row_groups_selected", "max_rows_per_group", "valid_for_population_prevalence", "design", "draw_rule")
_GATED = {"gated"}
_REQUEST = {"request_required", "author_request_required"}
_UNRELEASED = {"unreleased"}

HOW_TO_GET = {
    "in_site": "Examples are published on this site: open the Samples tab.",
    "fetch_with_atlas": "Install Dataset Atlas, then fetch the preview from the original source. Nothing downloads until you approve the plan.",
    "fetch_after_terms": "The source is gated. Accept its terms on your own account, sign in locally, then fetch the preview with Dataset Atlas.",
    "prepared_by_maintainers_only": "The maintainers prepared a preview, but its recipe is not in this repository yet, so you cannot rebuild it from the source.",
    "accept_terms": "The source is gated. Accept its terms on your own account; Dataset Atlas has no adapter for it yet.",
    "request_from_authors": "The data is released on request. Ask the authors or publisher; Dataset Atlas has no adapter for it yet.",
    "unreleased": "The authors have not released this data. Nothing can be fetched.",
    "source_unverified": "No pinned public source has been verified for this entry.",
    "public_no_adapter": "A public source exists, but Dataset Atlas has no recipe for it yet. That is a gap in Dataset Atlas, not a restriction by the source.",
}


def how_to_get(dataset: Dataset, *, has_recipe: bool, in_site: bool, needs_credentials: bool = False) -> dict[str, Any]:
    """`needs_credentials`: the recipe reads the source with a named local credential, so the source is treated as gated unless the catalogue says it is public."""
    coverage = dataset.coverage
    access = coverage.access
    if in_site:
        state = "in_site"
    elif has_recipe:
        state = "fetch_after_terms" if access in _GATED or (needs_credentials and access != "public") else "fetch_with_atlas"
    elif coverage.preview != "none":
        state = "prepared_by_maintainers_only"
    elif access in _GATED:
        state = "accept_terms"
    elif access in _REQUEST:
        state = "request_from_authors"
    elif access in _UNRELEASED:
        state = "unreleased"
    elif access == "public":
        state = "public_no_adapter"
    else:
        state = "source_unverified"
    result: dict[str, Any] = {"state": state, "summary": HOW_TO_GET[state]}
    if state in {"fetch_with_atlas", "fetch_after_terms"}:
        result["commands"] = [f"atlas previews fetch --dataset {dataset.id}", f"atlas previews fetch --dataset {dataset.id} --execute"]
        result["command_notes"] = ["Plans the fetch and prints the size; downloads nothing.", "Fetches the preview within the plan's download limit."]
    return result


def _papers(dataset: Dataset, papers_dir: Path) -> list[dict[str, Any]]:
    found = []
    for paper_id in dataset.paper_ids:
        path = papers_dir / f"{paper_id}.yaml"
        if not re.fullmatch(r"[A-Za-z0-9_-]+", paper_id) or not path.is_file():
            continue
        entry = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        item = {"paper_id": paper_id, "title": entry.get("title"), "year": entry.get("year"), "doi": entry.get("doi"), "url": entry.get("url")}
        item = {key: str(value) for key, value in item.items() if value not in (None, "")}
        if item.get("url") and not item["url"].startswith(("http://", "https://")):
            item.pop("url")
        found.append(item)
    return found


def schema_document(dataset: Dataset, pack: Pack) -> dict[str, Any]:
    """The field schema of a prepared preview, with no record values, local paths or adapter configuration."""
    fields = []
    for field in pack.fields[:MAX_FIELDS]:
        item: dict[str, Any] = {"id": field.id, "name": field.name, "namespace": field.namespace, "dtype": field.dtype, "unit": field.unit}
        if field.description:
            item["description"] = field.description
        if field.values and len(field.values) <= MAX_VALUES and all(isinstance(value, (str, int, float, bool)) for value in field.values):
            item["values"] = list(field.values)
        fields.append(item)
    document = {
        "schema_version": SCHEMA_VERSION, "id": dataset.id, "snapshot_id": dataset.snapshot_id, "release": dataset.release,
        "unit": dataset.coverage.unit, "preview_count": dataset.coverage.preview_count, "total_count": dataset.coverage.total_count,
        "population_scope": pack.population_scope, "field_count": len(pack.fields), "fields_truncated": len(pack.fields) > MAX_FIELDS,
        "sampling": {key: pack.sampling[key] for key in _SAMPLING_KEYS if key in pack.sampling}, "fields": fields,
    }
    scan_public(document, label=f"schema.{dataset.id}")
    return document


COVERAGE_FILE = "coverage.json"


def write_coverage(registry, directory: Path) -> int:
    """The coverage of every catalogue dataset as a workspace merges it with its prepared version.

    The tracked registry YAML keeps the pre-preparation state, so a build from the repository alone would show prepared datasets as
    having no preview. This file is a maintainers' snapshot of the merged state, committed beside the schemas."""
    directory.mkdir(parents=True, exist_ok=True)
    datasets = {dataset.id: dataset.coverage.model_dump(mode="json") for dataset in registry.datasets() if dataset.origin == "catalogue"}
    document = {"schema_version": SCHEMA_VERSION, "datasets": datasets}
    scan_public(document, label="coverage")
    (directory / COVERAGE_FILE).write_bytes(compact_json(document))
    return len(datasets)


def load_coverage(directory: Path) -> dict[str, dict[str, Any]]:
    path = directory / COVERAGE_FILE
    if not path.is_file():
        return {}
    document = read_json(path, limit=5_000_000)
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION or not isinstance(document.get("datasets"), dict):
        raise ExchangeError("Invalid public coverage snapshot")
    return document["datasets"]


def write_schemas(registry, directory: Path) -> list[str]:
    """Write one schema file per catalogue dataset whose local preview pack can be loaded; returns their IDs. A maintainers' step: needs the workspace."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for dataset in registry.datasets():
        if dataset.coverage.preview_count == 0 or dataset.origin != "catalogue":
            continue
        try:
            pack = registry.pack(dataset.id)
        except (FileNotFoundError, KeyError, ValueError):
            continue  # an active version without a preview pack (a complete index only) has no preview schema
        document = schema_document(dataset, pack)
        data = compact_json(document)
        if len(data) > MAX_SCHEMA_BYTES:
            raise ExchangeError(f"Schema is too large for {dataset.id}: {len(data)} bytes")
        (directory / f"{dataset.id}.json").write_bytes(data)
        written.append(dataset.id)
    if not written:
        raise ExchangeError("No local preview pack could be read; refusing to delete the committed schemas")
    for stale in directory.glob("*.json"):
        if stale.stem in written or stale.name == COVERAGE_FILE:
            continue
        try:
            document = json.loads(stale.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(document, dict) and document.get("schema_version") == SCHEMA_VERSION and document.get("id") == stale.stem and "fields" in document:
            stale.unlink()  # only a schema this module wrote, whose dataset no longer has a preview
    return written


def _load_schema(path: Path, dataset: Dataset) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    document = read_json(path, limit=MAX_SCHEMA_BYTES)
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION or document.get("id") != dataset.id:
        raise ExchangeError(f"Invalid public schema: {dataset.id}")
    for field in document.get("fields", []):
        FieldDescriptor.model_validate({**field, "id": field["id"]})
    scan_public(document, label=f"schema.{dataset.id}")
    return document


def build_guide(datasets: list[Dataset], *, registry_dir: Path, schema_dir: Path, published: set[str]) -> bytes:
    """One JSON document keyed by dataset ID; the site loads it lazily on a dataset page."""
    entries: dict[str, Any] = {}
    for dataset in datasets:
        recipe = registry_dir / "recipes" / f"{dataset.id}.yaml"
        gated_recipe = recipe.is_file() and bool((yaml.safe_load(recipe.read_text(encoding="utf-8")) or {}).get("credential_profile"))
        entry: dict[str, Any] = {
            "how_to_get": how_to_get(dataset, has_recipe=recipe.is_file(), in_site=dataset.id in published, needs_credentials=gated_recipe),
            "papers": _papers(dataset, registry_dir / "papers"),
        }
        schema = _load_schema(schema_dir / f"{dataset.id}.json", dataset)
        if schema:
            entry["schema"] = {key: value for key, value in schema.items() if key not in {"schema_version", "id"}}
        entries[dataset.id] = entry
    document = {"schema_version": SCHEMA_VERSION, "datasets": entries}
    scan_public(document, label="guide")
    return compact_json(document)


__all__ = ["build_guide", "how_to_get", "load_coverage", "schema_document", "write_coverage", "write_schemas", "HOW_TO_GET"]
