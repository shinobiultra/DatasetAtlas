import hashlib
import io
from pathlib import Path
import zipfile

import httpx
import pytest

from dataset_atlas.adapters import remote_zip


def _source_bytes() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("images/1.jpg", b"\xff\xd8\xff\xd9")
        archive.writestr("images/2.jpg", b"\xff\xd8\xff\xd9")
    return data.getvalue()


def _client(monkeypatch, source: bytes, *, drift: bool = False):
    etag = '"pinned"'
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-length": str(len(source)), "etag": etag})
        byte_range = request.headers["range"]
        assert request.headers["if-range"] == etag
        start, end = map(int, byte_range.removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=source[start:end + 1], headers={
            "etag": '"changed"' if drift else etag,
            "content-range": f"bytes {start}-{end}/{len(source)}"})

    original = httpx.Client
    monkeypatch.setattr(remote_zip.httpx, "Client",
                        lambda **kwargs: original(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(remote_zip.PinnedHTTPRangeReader, "_validate_dns", lambda self: None)
    return etag


def test_pinned_zip_member_crc_and_exact_budget(tmp_path: Path, monkeypatch):
    from PIL import Image
    data = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(data, format="JPEG")
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("images/1.jpg", data.getvalue())
    payload = source.getvalue()
    etag = _client(monkeypatch, payload)
    target = tmp_path / "selected.zip"
    receipt = remote_zip.acquire_selected_images("https://example.org/images.zip", target,
              ["images/1.jpg"], allowed_host="example.org", expected_size=len(payload),
              expected_etag=etag, max_transfer=10_000, max_member=10_000)
    assert receipt["range_bytes_transferred"] <= 10_000
    assert receipt["members"][0]["sha256"] == hashlib.sha256(data.getvalue()).hexdigest()
    with zipfile.ZipFile(target) as selected:
        assert selected.read("images/1.jpg") == data.getvalue()


def test_range_reader_rejects_etag_drift(monkeypatch):
    source = _source_bytes()
    etag = _client(monkeypatch, source, drift=True)
    with remote_zip.PinnedHTTPRangeReader("https://example.org/images.zip",
            allowed_host="example.org", expected_size=len(source), expected_etag=etag,
            max_transfer=10_000) as reader:
        with pytest.raises(ValueError, match="changed source"):
            reader.read(1)


def test_range_reader_rejects_private_dns(monkeypatch):
    monkeypatch.setattr(remote_zip.socket, "getaddrinfo",
                        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="nonpublic"):
        remote_zip.PinnedHTTPRangeReader("https://example.org/images.zip",
            allowed_host="example.org", expected_size=100, expected_etag='"pinned"',
            max_transfer=1000)
