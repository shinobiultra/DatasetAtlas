"""Local source access that rejects traversal and symlink escapes."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import stat
from typing import Mapping, BinaryIO


class SafeRoots:
    def __init__(self, roots: Mapping[str, str | Path]):
        self.roots = {}
        for name, value in roots.items():
            path = Path(value).resolve(strict=True)
            if not path.is_dir():
                raise ValueError(f"Configured root is not a directory: {name}")
            self.roots[name] = path

    @staticmethod
    def _parts(relative: str | Path) -> tuple[str, ...]:
        raw = str(relative)
        if not raw or "\x00" in raw or "\\" in raw or raw.startswith("/"):
            raise ValueError("Expected a nonempty relative path")
        parts = PurePosixPath(raw).parts
        if not parts or any(part in ("", ".", "..") for part in raw.split("/")):
            raise ValueError("Path traversal is forbidden")
        return parts

    def resolve(self, root: str, relative: str | Path) -> Path:
        base = self.roots[root]
        parts = self._parts(relative)
        current = base
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Symlink access is forbidden")
        resolved = current.resolve(strict=True)
        if not resolved.is_relative_to(base):
            raise ValueError("Path escapes configured root")
        return resolved

    def open(self, root: str, relative: str | Path) -> BinaryIO:
        """Open read-only using dir fds and O_NOFOLLOW to close check/open races."""
        base = self.roots[root]
        parts = self._parts(relative)
        directory = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in parts[:-1]:
                next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = next_directory
            file_descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                os.close(file_descriptor)
                raise ValueError("Only regular files may be read")
            return os.fdopen(file_descriptor, "rb")
        finally:
            os.close(directory)


def read_rooted_file(path: str | Path, roots: list[str | Path] | tuple[str | Path, ...],
                     max_bytes: int) -> bytes:
    """Read a regular file under an approved root without following any symlink.

    Absolute paths are matched lexically against roots before opening. Relative
    paths are tried beneath each root. The file is bounded even if it grows while
    being read. Use this for source/media bytes instead of resolve-then-read.
    """
    if max_bytes < 0 or not roots:
        raise ValueError("A byte bound and configured roots are required")
    configured = SafeRoots({str(index): root for index, root in enumerate(roots)})
    candidate = Path(path)
    for name, base in configured.roots.items():
        if candidate.is_absolute():
            try:
                relative = candidate.relative_to(base)
            except ValueError:
                continue
        else:
            relative = candidate
        try:
            with configured.open(name, relative.as_posix()) as stream:
                data = stream.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("File exceeds configured byte bound")
            return data
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError("File cannot be read under configured root") from exc
    raise ValueError("File is unavailable within configured roots")
