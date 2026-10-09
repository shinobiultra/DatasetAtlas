import io
import zipfile

import pytest

from dataset_atlas.storage.multipart import MultipartRangeReader
from dataset_atlas.storage.ranges import HttpsRangeReader


def reader(monkeypatch, payloads, budget):
    calls = []

    def fetch(self, start, end):
        calls.append((self.url, start, end, self.etag))
        return payloads[self.url][start : end + 1]

    monkeypatch.setattr(HttpsRangeReader, "_fetch", fetch)
    parts = [
        {
            "url": key,
            "bytes": len(value),
            "etag": f'"part-{index}"',
            "allowed_hosts": ["example.com"],
        }
        for index, (key, value) in enumerate(payloads.items())
    ]
    return MultipartRangeReader(parts, byte_budget=budget), calls


def test_reads_and_seeks_across_exact_part_boundaries(monkeypatch):
    source, calls = reader(
        monkeypatch,
        {"https://example.com/1": b"abc", "https://example.com/2": b"defgh"},
        30,
    )
    with source:
        source.seek(2)
        assert source.read(4) == b"cdef"
        assert source.bytes_fetched == 4
        assert [call[3] for call in calls] == ['"part-0"', '"part-1"']
        source.seek(-3, 2)
        target = bytearray(10)
        assert source.readinto(target) == 3 and target[:3] == b"fgh"
        source.seek(0)
        assert source.read() == b"abcdefgh"
        assert source.read() == b""
    assert all(child.closed for child in source.readers)
    with pytest.raises(ValueError, match="closed"):
        source.read(1)


def test_transfer_cap_is_shared_across_parts_and_repeated_reads(monkeypatch):
    source, calls = reader(
        monkeypatch,
        {"https://example.com/1": b"abcd", "https://example.com/2": b"efgh"},
        6,
    )
    with source:
        assert source.read(5) == b"abcde"
        source.seek(0)
        with pytest.raises(ValueError, match="budget"):
            source.read(2)
        assert source.bytes_fetched == 5
        assert len(calls) == 2


def test_standard_zip_directory_and_member_can_straddle_byte_chunks(monkeypatch):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("native/image.jpg", b"exact native bytes" * 100)
    payload = output.getvalue()
    chunks = {
        f"https://example.com/{index}": payload[start : start + 23]
        for index, start in enumerate(range(0, len(payload), 23))
    }
    source, _ = reader(monkeypatch, chunks, 10000)
    with source, zipfile.ZipFile(source) as archive:
        assert archive.read("native/image.jpg") == b"exact native bytes" * 100
    assert source.bytes_fetched < 10000


def test_invalid_part_closes_constructed_readers(monkeypatch):
    readers = []
    original = HttpsRangeReader.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        readers.append(self)

    monkeypatch.setattr(HttpsRangeReader, "__init__", init)
    good = {
        "url": "https://example.com/1",
        "bytes": 10,
        "etag": '"v1"',
        "allowed_hosts": ["example.com"],
    }
    with pytest.raises(ValueError, match="strong ETag"):
        MultipartRangeReader([good, {**good, "etag": 'W/"weak"'}], byte_budget=10)
    assert readers[0].closed
