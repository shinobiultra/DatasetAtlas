"""SVO-Probes source CSV with separately bounded local image-link coverage."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from dataset_atlas.models import Asset, Record, stable_id
from dataset_atlas.storage import BoundedCache, CacheIdentity, HttpsFetcher

from .core import StructuredAdapter, _write_rooted_atomic


class SVOProbesAdapter(StructuredAdapter):
    """Retain all source URL pairs; attach media only when a local checked copy exists."""

    def _media_entries(self) -> dict:
        cached = getattr(self, "_cached_media_entries", None)
        if cached is not None:
            return cached
        manifest_path = Path(self.config["media_manifest"])
        if not manifest_path.is_file():
            return {}
        manifest = json.loads(manifest_path.read_text())
        if (manifest.get("source_revision") != self.revision
                or manifest.get("source_sha256") != self.config.get("sha256")):
            raise ValueError("SVO media manifest belongs to a different source revision")
        entries = manifest.get("images", {})
        self._cached_media_entries = entries
        return entries

    def _record(self, row: dict, ordinal: int) -> Record:
        record = super()._record(row, ordinal)
        entries = self._media_entries()
        for role in ("pos", "neg"):
            image_id = row[f"{role}_image_id"]
            url = row[f"{role}_url"]
            entry = entries.get(image_id)
            if not entry or entry.get("status") != "verified":
                continue
            if entry.get("url_sha256") != hashlib.sha256(url.encode()).hexdigest():
                raise ValueError(f"SVO media URL changed for image ID {image_id}")
            aid = stable_id(self.dataset.id, self.revision, "asset", image_id)
            asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                          modality="image", uri=entry["path"], sha256=entry["sha256"],
                          metadata={"source_image_id": image_id, "pair_role": role,
                                    "media_access": "local_checked_copy"})
            record.asset_ids.append(aid)
            record.assets.append(asset)
        return record


def acquire_preview_media(dataset, *, row_limit: int = 100,
                          per_image_bytes: int = 1_000_000,
                          total_budget_bytes: int = 200_000_000,
                          workers: int = 8) -> dict:
    """Probe exact source URLs for the first rows with a strict worst-case bound.

    Only HTTPS URLs from the pinned CSV are eligible. The fetcher rejects private
    DNS addresses and redirects outside the exact source-host allowlist. Failed
    links remain explicit in the receipt; no URL is rewritten or silently mirrored.
    """
    if (dataset.adapter != "svo_probes" or not 1 <= row_limit <= 100
            or per_image_bytes < 1 or workers < 1):
        raise ValueError("bounded SVO preview media parameters required")
    config = dataset.adapter_config
    rows = []
    with Path(config["path"]).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            rows.append(row)
            if len(rows) == row_limit:
                break
    refs: dict[str, str] = {}
    for row in rows:
        for role in ("pos", "neg"):
            image_id, url = row[f"{role}_image_id"], row[f"{role}_url"]
            if not image_id.isdecimal() or not url:
                raise ValueError("SVO source row has an invalid image ID or URL")
            if image_id in refs and refs[image_id] != url:
                raise ValueError("SVO source image ID maps to multiple URLs")
            refs[image_id] = url
    if len(refs) * per_image_bytes > total_budget_bytes:
        raise ValueError("worst-case selected media exceeds approved byte budget")
    allowed_hosts = {urlsplit(url).hostname for url in refs.values()
                     if urlsplit(url).scheme.lower() == "https" and urlsplit(url).hostname}
    fetcher = HttpsFetcher(allowed_hosts, timeout=8, max_redirects=3,
                           max_bytes=per_image_bytes)
    cache = BoundedCache(config["media_cache"], total_budget_bytes)
    media_root = Path(config["media_root"]).resolve()
    media_root.mkdir(parents=True, exist_ok=True)

    def get_image(image_id: str, url: str) -> tuple[str, dict]:
        base = {"url": url, "url_sha256": hashlib.sha256(url.encode()).hexdigest()}
        if urlsplit(url).scheme.lower() != "https":
            return image_id, base | {"status": "unsupported_http_source"}
        identity = CacheIdentity(dataset.release, image_id, "original")
        try:
            path = fetcher.fetch(url, cache, identity, byte_budget=per_image_bytes)
            data = path.read_bytes()
            with Image.open(io.BytesIO(data)) as image:
                fmt = image.format
                width, height = image.size
                if not width or not height or width * height > 25_000_000:
                    raise ValueError("source image dimensions exceed local preview bound")
                image.verify()
            suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp",
                      "GIF": ".gif"}.get(fmt)
            if suffix is None:
                raise ValueError(f"source is not a supported image format: {fmt}")
            relative = f"images/{image_id}{suffix}"
            _write_rooted_atomic(media_root, relative, data)
            return image_id, base | {"status": "verified", "path": relative,
                                     "sha256": hashlib.sha256(data).hexdigest(),
                                     "bytes": len(data), "format": fmt,
                                     "width": width, "height": height}
        except Exception as exc:
            return image_id, base | {"status": "failed", "error": type(exc).__name__,
                                     "detail": str(exc)[:240]}

    images = {}
    with ThreadPoolExecutor(max_workers=min(workers, 12)) as pool:
        futures = [pool.submit(get_image, image_id, url) for image_id, url in refs.items()]
        for future in as_completed(futures):
            image_id, entry = future.result()
            images[image_id] = entry
    by_status: dict[str, int] = {}
    for entry in images.values():
        by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
    receipt = {"source_revision": dataset.release,
               "source_sha256": config["sha256"], "selected_rows": len(rows),
               "unique_image_refs": len(refs), "allowed_source_hosts": sorted(allowed_hosts),
               "per_image_byte_cap": per_image_bytes,
               "worst_case_byte_cap": len(refs) * per_image_bytes,
               "verified_image_bytes": sum(e.get("bytes", 0) for e in images.values()),
               "status_counts": by_status, "images": images}
    target = Path(config["media_manifest"])
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + ".part")
    staged.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    staged.replace(target)
    return receipt
