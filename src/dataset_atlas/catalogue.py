"""Catalogue-level preview thumbnails.

The catalogue is thumbnail-led, so it must show real dataset media without
downloading a whole preview pack per card. This derives a tiny summary from
records that are already prepared (workbench) or already approved for
publication (static build). It never invents media: a dataset with no
usable asset gets an explicit empty entry.
"""

from __future__ import annotations

from typing import Any, Iterable

MAX_TILES = 4
MAX_TEXT = 220

_IMAGE_MODALITIES = {"image"}


def _text_of(record: Any) -> str | None:
    for value in (getattr(record, "question", None), getattr(record, "text", None)):
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_TEXT]
    for asset in getattr(record, "assets", []) or []:
        text = getattr(asset, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()[:MAX_TEXT]
    conversation = getattr(record, "conversation", None) or []
    for turn in conversation:
        content = turn.get("content") if isinstance(turn, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()[:MAX_TEXT]
    return None


def summarize_records(records: Iterable[Any], *, limit: int = MAX_TILES) -> dict[str, Any]:
    """Return {'tiles': [...], 'modality': str|None} for up to `limit` distinct assets."""
    tiles: list[dict[str, str]] = []
    seen: set[str] = set()
    fallback_text: list[dict[str, str]] = []
    modality: str | None = None
    for record in records:
        for asset in getattr(record, "assets", []) or []:
            asset_modality = getattr(asset, "modality", None)
            if modality is None and asset_modality:
                modality = asset_modality
            uri = getattr(asset, "uri", None)
            asset_id = getattr(asset, "id", "")
            if asset_modality in _IMAGE_MODALITIES and isinstance(uri, str) and uri and asset_id not in seen:
                seen.add(asset_id)
                tiles.append({"kind": "image", "uri": uri})
                if len(tiles) >= limit:
                    return {"tiles": tiles, "modality": modality}
        if len(fallback_text) < limit:
            text = _text_of(record)
            if text:
                fallback_text.append({"kind": "text", "text": text})
    if not tiles:
        tiles = fallback_text[:limit]
        if tiles and modality is None:
            modality = "text"
    return {"tiles": tiles, "modality": modality}


def thumbnails_document(entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": "1.0", "datasets": entries}


def with_availability(dataset: Any, has_preview: bool, has_complete: bool) -> Any:
    """Correct registry coverage claims that depend on files this workspace does not hold.

    A tracked registry entry says what a maintainer prepared; a colleague's clone has
    none of it until it is fetched. A preview that exists only upstream is reported as
    `on_request` with zero browsable records, so nothing is advertised as inspectable
    that would fail to open. Complete-data support is downgraded to
    `requires_preparation` unless its index is present."""
    from dataset_atlas.models import Availability

    coverage = dataset.coverage.model_copy(deep=True)
    upstream = coverage.preview_count or 0
    if dataset.origin == "user" and not upstream:
        # Registering the source declares that a population exists; its preview is built from it on request.
        upstream = min(coverage.total_count or 100, 100)
    if not has_preview:
        coverage.preview, coverage.preview_count = "none", 0
    if coverage.complete_data == "supported" and not has_complete:
        coverage.complete_data = "requires_preparation"
    wants_complete = coverage.complete_data in {"supported", "requires_preparation"}
    availability = Availability(
        preview="local" if has_preview else "on_request" if upstream else "none",
        complete_data="local" if has_complete else "on_request" if wants_complete else "none",
        upstream_preview_count=upstream,
    )
    return dataset.model_copy(update={"coverage": coverage, "availability": availability})
