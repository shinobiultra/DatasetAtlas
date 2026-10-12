"""Images for a model prompt: read from an approved local root, verified, downscaled, JPEG-encoded, base64."""
from __future__ import annotations

import base64
import hashlib
import io
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any

from PIL import Image, ImageOps

from dataset_atlas.storage.local import read_rooted_file

_CACHE: OrderedDict[tuple, str] = OrderedDict()
_CACHE_LIMIT = 512
_LOCK = Lock()


def encode_image(asset: Any, roots: list[str], *, max_side: int = 672, quality: int = 90, max_pixels: int = 50_000_000) -> str:
    """Base64 JPEG of one image asset, at most ``max_side`` pixels on its longer side.

    Reads only inside ``roots`` and checks the asset's recorded SHA-256 when it has one, so a model is never shown bytes that
    differ from the dataset's. Results are cached per process: many questions often share one image.
    """
    key = (asset.id, asset.sha256, max_side, quality)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            _CACHE.move_to_end(key)
            return hit
    if not asset.uri or "://" in asset.uri:
        raise ValueError("Image asset has no permitted local URI")
    data = read_rooted_file(asset.uri, roots, max_bytes=100_000_000)
    if asset.sha256 and hashlib.sha256(data).hexdigest() != asset.sha256:
        raise ValueError("Asset sha256 mismatch")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > max_pixels:
            raise ValueError("Image exceeds max_pixels")
        image = ImageOps.exif_transpose(source).convert("RGB")
    image.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    with _LOCK:
        _CACHE[key] = encoded
        while len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)
    return encoded


def encode_many(assets: list[Any], roots: list[str], *, threads: int = 8, **options) -> dict[str, str | Exception]:
    """Encode distinct assets concurrently; a failure is returned for that asset, not raised."""
    unique = list({asset.id: asset for asset in assets}.values())

    def one(asset):
        try:
            return encode_image(asset, roots, **options)
        except Exception as exc:  # reported per asset
            return exc

    with ThreadPoolExecutor(max_workers=max(1, min(threads, len(unique) or 1))) as pool:
        return {asset.id: result for asset, result in zip(unique, pool.map(one, unique))}
