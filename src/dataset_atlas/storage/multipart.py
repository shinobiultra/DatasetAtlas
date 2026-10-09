"""Seek across pinned remote byte chunks without concatenating them on disk."""

from __future__ import annotations

from bisect import bisect_right
import io

from .ranges import HttpsRangeReader


class MultipartRangeReader(io.RawIOBase):
    """A concatenated file, with one shared transfer cap and per-part ETags.

    This reads byte-split archives, not ZIP's multi-disk archive format. The
    caller pins the order and identity of every part in an immutable recipe.
    """

    def __init__(self, parts, *, byte_budget, cache=None, cancel=None):
        super().__init__()
        self.readers = []
        if not isinstance(parts, list) or not 1 <= len(parts) <= 256:
            raise ValueError("Multipart source requires 1..256 ordered parts")
        if type(byte_budget) is not int or byte_budget < 1:
            raise ValueError("Multipart source requires a positive transfer budget")
        self.starts = []
        self.size = 0
        self.position = 0
        self.byte_budget = byte_budget
        self.bytes_fetched = 0
        try:
            for part in parts:
                self.starts.append(self.size)
                reader = HttpsRangeReader(
                    part["url"],
                    size=part["bytes"],
                    etag=part["etag"],
                    allowed_hosts=part["allowed_hosts"],
                    byte_budget=byte_budget,
                    cache=cache,
                    cancel=cancel,
                )
                self.readers.append(reader)
                self.size += reader.size
        except BaseException:
            self.close()
            raise

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset + (
            self.position if whence == 1 else self.size if whence == 2 else 0
        )
        if whence not in (0, 1, 2) or position < 0:
            raise ValueError("Invalid multipart seek")
        self.position = position
        return position

    def read(self, size=-1):
        if self.closed:
            raise ValueError("Reader is closed")
        count = (
            max(0, self.size - self.position)
            if size < 0
            else min(size, max(0, self.size - self.position))
        )
        if count > self.byte_budget:
            raise ValueError("Multipart read exceeds byte budget")
        chunks = []
        while count:
            part = bisect_right(self.starts, self.position) - 1
            reader = self.readers[part]
            reader.seek(self.position - self.starts[part])
            wanted = min(count, reader.size - reader.tell())
            # A child can use only the parent's remaining transfer allowance.
            reader.byte_budget = (
                reader.bytes_fetched + self.byte_budget - self.bytes_fetched
            )
            before = reader.bytes_fetched
            try:
                data = reader.read(wanted)
            finally:
                self.bytes_fetched += reader.bytes_fetched - before
            if len(data) != wanted:
                raise ValueError("Multipart source returned a short read")
            chunks.append(data)
            self.position += wanted
            count -= wanted
        return b"".join(chunks)

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self):
        for reader in self.readers:
            reader.close()
        super().close()
