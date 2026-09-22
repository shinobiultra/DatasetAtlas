"""Explicitly bounded, resumable HTTPS file acquisition for configured sources."""
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx


def fetch_bounded(url: str, target: Path, max_bytes: int,
                  expected_md5: str | None = None,
                  expected_sha256: str | None = None) -> dict[str, str | int]:
    if not url.startswith("https://") or max_bytes <= 0:
        raise ValueError("HTTPS URL and positive byte budget required")
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + ".part")
    if target.is_file():
        return _verified(target, max_bytes, expected_md5, expected_sha256, 0)
    prior = staged.stat().st_size if staged.exists() else 0
    if prior > max_bytes:
        raise ValueError("partial transfer exceeds byte budget")
    headers = {"Range": f"bytes={prior}-"} if prior else {}
    downloaded = 0
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            if prior and response.status_code == 206:
                content_range = response.headers.get("content-range", "")
                if not content_range.startswith(f"bytes {prior}-"):
                    raise ValueError("server returned an inconsistent resume range")
                mode = "ab"
            elif prior and response.status_code == 200:
                prior = 0
                mode = "wb"
            elif response.status_code == 200:
                mode = "wb"
            else:
                raise ValueError(f"unexpected HTTP status {response.status_code}")
            with staged.open(mode) as handle:
                for chunk in response.iter_bytes():
                    downloaded += len(chunk)
                    if prior + downloaded > max_bytes:
                        raise ValueError("download exceeded approved byte budget")
                    handle.write(chunk)
    result = _verified(staged, max_bytes, expected_md5, expected_sha256, downloaded)
    staged.replace(target)
    result["path"] = str(target)
    return result


def _verified(path: Path, max_bytes: int, expected_md5: str | None,
              expected_sha256: str | None, downloaded: int) -> dict[str, str | int]:
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError("source exceeds approved byte budget")
    md5 = hashlib.md5(usedforsecurity=False)
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            md5.update(chunk); sha.update(chunk)
    if expected_md5 and md5.hexdigest() != expected_md5:
        raise ValueError("source MD5 differs from official checksum")
    if expected_sha256 and sha.hexdigest() != expected_sha256:
        raise ValueError("source SHA-256 differs from pinned checksum")
    return {"path": str(path), "bytes": size, "downloaded_this_call": downloaded,
            "md5": md5.hexdigest(), "sha256": sha.hexdigest()}
