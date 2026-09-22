"""Construct the exact model input from canonical records, without hidden labels."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Callable, Sequence

from PIL import Image

from dataset_atlas.models import Asset, Record
from dataset_atlas.storage import read_rooted_file

from .schemas import ContextPreview, ContextRequest, ProviderView

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _image_bytes(asset: Asset, roots: Sequence[Path]) -> tuple[bytes, str]:
    if not asset.uri or "://" in asset.uri:
        raise ValueError(f"image {asset.id} has no allowed local file")
    mime = _MIME.get(Path(asset.uri).suffix.lower())
    if not mime:
        raise ValueError(f"unsupported image format for {asset.id}")
    try:
        content = read_rooted_file(asset.uri, tuple(roots), max_bytes=5_000_000)
    except (OSError, ValueError) as exc:
        raise ValueError(f"image {asset.id} is unavailable or unsafe under configured roots") from exc
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError(f"image {asset.id} exceeds pixel limit")
            actual = Image.MIME.get(image.format)
            if actual != mime:
                raise ValueError(f"image {asset.id} format does not match its extension")
            image.verify()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f"image {asset.id} is not a valid supported image") from exc
    return content, mime


def _field_value(record: Record, field: str) -> object:
    namespace, dot, key = field.partition(".")
    if not dot or not key or "." in key or namespace not in ("source", "prediction", "human"):
        raise ValueError(f"unsupported context field: {field}")
    value = getattr(record, namespace).get(key)
    if value is None:
        raise ValueError(f"unknown or empty context field: {field}")
    return value


def build_context(
    request: ContextRequest,
    provider: ProviderView,
    record_lookup: Callable[[str], Record | None],
    image_roots: Sequence[Path],
) -> ContextPreview:
    records: list[Record] = []
    for record_id in request.record_ids:
        record = record_lookup(record_id)
        if record is None or record.id != record_id:
            raise ValueError(f"record unavailable: {record_id}")
        records.append(record)

    if request.mode == "evaluation" and (request.fields or request.include_annotations):
        raise ValueError("evaluation excludes annotations, labels, filenames, and predictions")
    if len(request.image_asset_ids) > min(8, provider.config.max_images):
        raise ValueError("image count exceeds provider or application limit")
    if request.mode == "evaluation" and len(records) > 1 and not request.independent_records:
        raise ValueError("multi-record evaluation requires independent_records=true")
    if request.independent_records and len(records) > 1:
        if request.mode != "evaluation":
            raise ValueError("independent multi-record requests currently require evaluation mode")
        selected_assets = {asset.id for record in records for asset in record.assets}
        if not set(request.image_asset_ids).issubset(selected_assets):
            raise ValueError("selected image assets do not belong to approved records")
        per_record = []
        all_images = []
        total_text_characters = 0
        for record in records:
            image_ids = [asset_id for asset_id in request.image_asset_ids if asset_id in {asset.id for asset in record.assets}]
            single_request = request.model_copy(update={"record_ids": [record.id], "image_asset_ids": image_ids, "independent_records": False})
            single = build_context(single_request, provider, record_lookup, image_roots)
            per_record.append({"record_id": record.id, "context_digest": single.context_digest, "outgoing": single.outgoing, "image_representations": single.image_representations, "notices": single.notices, "policy": single.policy})
            all_images.extend(single.image_representations)
            total_text_characters += len(single.outgoing[0]["content"][0]["text"])
        if total_text_characters > 250_000:
            raise ValueError("batch context exceeds 250,000 text characters")
        if len(all_images) > min(8, provider.config.max_images):
            raise ValueError("batch transmitted image count exceeds provider or application limit")
        policy = {"mode": request.mode, "delivery": "independent", "record_scope": request.record_ids, "image_asset_ids": request.image_asset_ids, "fields": [], "include_annotations": False, "provider_endpoint": provider.config.base_url}
        digest_input = {"provider_config": provider.config.model_dump(mode="json"), "policy": policy, "per_record_digests": [item["context_digest"] for item in per_record]}
        digest = hashlib.sha256(json.dumps(digest_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        return ContextPreview(context_digest=digest, provider_id=provider.config.id, model=provider.config.model, record_ids=request.record_ids, mode=request.mode, outgoing=[], delivery="independent", per_record_contexts=per_record, image_representations=all_images, notices=["Records are sent in separate model requests; one response per record."], policy=policy)

    image_capability = "single_image_input" if len(request.image_asset_ids) == 1 else "multiple_image_input"
    if request.image_asset_ids and provider.capabilities[image_capability].status != "supported":
        raise ValueError(f"{image_capability} has not been verified for this model-server combination")

    allowed_assets = {asset.id: asset for record in records for asset in record.assets if asset.modality.lower() in ("image", "photo")}
    missing = set(request.image_asset_ids) - set(allowed_assets)
    if missing:
        raise ValueError("selected image assets do not belong to approved records")

    notices: list[str] = []
    if any(record.assets for record in records) and not request.image_asset_ids:
        notices.append("Images are unavailable to this request; the model receives textual evidence only.")

    text_records = []
    for record in records:
        item: dict[str, object] = {"record_id": record.id, "dataset_id": record.dataset_id, "release_id": record.release_id, "snapshot_id": record.snapshot_id}
        if record.text is not None:
            item["text"] = record.text
        if record.question is not None:
            item["question"] = record.question
        if record.choices:
            item["choices"] = record.choices
        if request.mode == "exploration":
            if record.conversation:
                item["conversation"] = record.conversation
            for field in request.fields:
                item[field] = _field_value(record, field)
            if request.include_annotations:
                item["annotations"] = [annotation.model_dump(mode="json") for annotation in record.annotations]
        text_records.append(item)

    context_text = json.dumps({"mode": request.mode, "records": text_records, "notices": notices}, ensure_ascii=False, sort_keys=True)
    if len(context_text) > provider.config.max_input_characters:
        raise ValueError("selected context exceeds configured input character limit")
    parts: list[dict[str, object]] = [{"type": "text", "text": context_text}]
    image_representations = []
    for asset_id in request.image_asset_ids:
        asset = allowed_assets[asset_id]
        content, mime = _image_bytes(asset, image_roots)
        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"}})
        image_representations.append({"asset_id": asset.id, "representation": asset.representation, "mime_type": mime, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content), "client_preprocessing": "none; file bytes encoded as data URL", "provider_preprocessing": "unknown"})

    outgoing = [{"role": "user", "content": parts}]
    policy = {"mode": request.mode, "fields": request.fields, "include_annotations": request.include_annotations, "image_asset_ids": request.image_asset_ids, "independent_records": request.independent_records, "record_scope": request.record_ids, "provider_endpoint": provider.config.base_url}
    digest_input = {"provider_config": provider.config.model_dump(mode="json"), "outgoing": outgoing, "policy": policy}
    digest = hashlib.sha256(json.dumps(digest_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return ContextPreview(context_digest=digest, provider_id=provider.config.id, model=provider.config.model, record_ids=request.record_ids, mode=request.mode, outgoing=outgoing, image_representations=image_representations, notices=notices, policy=policy)
