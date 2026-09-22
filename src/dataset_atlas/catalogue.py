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
