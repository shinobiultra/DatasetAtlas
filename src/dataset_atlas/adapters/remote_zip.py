"""Bounded, revision-pinned reads of selected members in an HTTPS ZIP.

This is an acquisition helper, not a general client-side URL resolver. Callers
must provide the exact official URL, allowed host, strong ETag, and byte caps.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import io
import ipaddress
from pathlib import Path
import re
import socket
import time
from urllib.parse import urlsplit
import zipfile

import httpx
from PIL import Image


class PinnedHTTPRangeReader:
    """Small seekable block cache with strict 206, ETag, and transfer checks."""

    def __init__(self, url: str, *, allowed_host: str, expected_size: int,
                 expected_etag: str, max_transfer: int, block_size: int = 1 << 20,
                 max_requests: int = 500, cache_blocks: int = 16):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != allowed_host
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError("range source must be the exact allowlisted HTTPS host")
        self.url = url
        self.host = allowed_host
        self.size = expected_size
        self.etag = expected_etag
        self.max_transfer = max_transfer
        self.block_size = block_size
        self.max_requests = max_requests
        self.cache_blocks = cache_blocks
        self.position = 0
        self.bytes_transferred = 0
        self.requests = 0
        self.blocks: OrderedDict[int, bytes] = OrderedDict()
        if (expected_size <= 0 or max_transfer <= 0 or block_size <= 0
                or max_requests <= 0 or cache_blocks <= 0
                or not expected_etag.startswith('"') or not expected_etag.endswith('"')):
            raise ValueError("positive bounds and a strong source ETag are required")
        self._validate_dns()
        self.client = httpx.Client(timeout=45, follow_redirects=False)
        response = self.client.head(url, headers={"Accept-Encoding": "identity"})
        if (response.status_code != 200 or response.headers.get("etag") != expected_etag
                or int(response.headers.get("content-length", "0")) != expected_size):
            self.close()
            raise ValueError("source size or ETag changed before ranged reads")

    def _validate_dns(self) -> None:
        addresses = {item[4][0] for item in socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError("range source resolves to a nonpublic address")

    def _block(self, index: int) -> bytes:
        cached = self.blocks.get(index)
        if cached is not None:
            self.blocks.move_to_end(index)
            return cached
        start = index * self.block_size
        end = min(start + self.block_size, self.size) - 1
        length = end - start + 1
        if self.bytes_transferred + length > self.max_transfer or self.requests >= self.max_requests:
            raise ValueError("ZIP range transfer budget exceeded")
        self._validate_dns()
        payload = None
        for attempt in range(4):
            if self.requests >= self.max_requests:
                raise ValueError("ZIP range request budget exceeded")
            with self.client.stream("GET", self.url, headers={
                    "Accept-Encoding": "identity", "Range": f"bytes={start}-{end}",
                    "If-Range": self.etag}) as response:
                self.requests += 1
                if response.status_code in (429, 502, 503, 504):
                    if attempt == 3:
                        raise ValueError(f"ZIP range source unavailable: HTTP {response.status_code}")
                elif (response.status_code != 206 or response.headers.get("etag") != self.etag
                      or response.headers.get("content-range") != f"bytes {start}-{end}/{self.size}"
                      or int(response.headers.get("content-length", "-1")) != length):
                    raise ValueError(f"ZIP range response changed source or ignored bounds: "
                                     f"status={response.status_code}, range={response.headers.get('content-range')}, "
                                     f"etag={response.headers.get('etag')}, expected={start}-{end}/{self.size}")
                else:
                    chunks = []
                    received = 0
                    for chunk in response.iter_bytes():
                        received += len(chunk)
                        if received > length or self.bytes_transferred + received > self.max_transfer:
                            raise ValueError("ZIP range response exceeded approved byte budget")
                        chunks.append(chunk)
                    if received != length:
                        raise ValueError("ZIP range response ended before declared length")
                    payload = b"".join(chunks)
                    break
            time.sleep(2 ** attempt)
        if payload is None:
            raise ValueError("ZIP range did not return a member block")
        self.bytes_transferred += length
        self.blocks[index] = payload
        self.blocks.move_to_end(index)
        while len(self.blocks) > self.cache_blocks:
            self.blocks.popitem(last=False)
        return payload

    def seek(self, offset: int, whence: int = 0) -> int:
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if whence not in (0, 1, 2) or not 0 <= position <= self.size:
            raise ValueError("ZIP seek outside pinned source")
        self.position = position
        return position

    def tell(self) -> int:
        return self.position

    def seekable(self) -> bool:
        return True

    def read(self, count: int = -1) -> bytes:
        remaining = self.size - self.position
        if count < 0:
            count = remaining
        count = min(count, remaining)
        if count > 16 << 20:
            raise ValueError("ZIP read exceeds 16 MiB operation cap")
        chunks: list[bytes] = []
        until = self.position + count
        while self.position < until:
            index, within = divmod(self.position, self.block_size)
            block = self._block(index)
            part = block[within:within + until - self.position]
            chunks.append(part)
            self.position += len(part)
        return b"".join(chunks)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "PinnedHTTPRangeReader":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def acquire_selected_images(url: str, target: Path, members: list[str], *,
                            allowed_host: str, expected_size: int, expected_etag: str,
                            max_transfer: int, max_member: int = 5_000_000,
                            max_output: int = 100_000_000) -> dict:
    """Copy exact original JPEG bytes into a small local ZIP; report each CRC/hash."""
    if len(set(members)) != len(members) or not members:
        raise ValueError("selected ZIP members must be unique and nonempty")
    if any(not re.fullmatch(r"images/[0-9]+\.jpg", name) for name in members):
        raise ValueError("selected ZIP member path is not an original image ID")
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + ".part")
    staged.unlink(missing_ok=True)
    receipts: list[dict] = []
    total_output = 0
    try:
        with PinnedHTTPRangeReader(url, allowed_host=allowed_host, expected_size=expected_size,
                                   expected_etag=expected_etag, max_transfer=max_transfer) as remote:
            with zipfile.ZipFile(remote) as source, zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_STORED) as output:
                counts: dict[str, int] = {}
                wanted = set(members)
                for info in source.infolist():
                    if info.filename in wanted:
                        counts[info.filename] = counts.get(info.filename, 0) + 1
                if any(counts.get(name) != 1 for name in members):
                    raise ValueError("selected image missing or duplicated in source ZIP")
                for name in members:
                    info = source.getinfo(name)
                    if (not 0 < info.file_size <= max_member
                            or not 0 < info.compress_size <= max_member):
                        raise ValueError(f"source image outside member cap: {name}")
                    data = source.read(info)  # zipfile verifies the original member CRC.
                    if not data.startswith(b"\xff\xd8\xff"):
                        raise ValueError(f"source image is not JPEG: {name}")
                    with Image.open(io.BytesIO(data)) as image:
                        if image.format != "JPEG":
                            raise ValueError(f"source image has wrong format: {name}")
                        image.verify()
                    total_output += len(data)
                    if total_output > max_output:
                        raise ValueError("selected image output budget exceeded")
                    output.writestr(name, data)
                    receipts.append({"member": name, "bytes": len(data),
                                     "source_crc32": f"{info.CRC:08x}",
                                     "sha256": hashlib.sha256(data).hexdigest()})
            transfer = remote.bytes_transferred
            requests = remote.requests
        staged.replace(target)
    finally:
        staged.unlink(missing_ok=True)
    return {"source_url": url, "source_etag": expected_etag,
            "source_size_bytes": expected_size, "range_requests": requests,
            "range_bytes_transferred": transfer, "selected_original_bytes": total_output,
            "selected_zip_bytes": target.stat().st_size,
            "selected_zip_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "members": receipts}
