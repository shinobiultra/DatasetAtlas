"""Columnar numeric results: named ``.npy`` arrays beside an ids list, checksummed.

Per-record JSON suits a few thousand records and not hundreds of thousands: a
214k x 768 embedding is gigabytes of JSON lists but 650 MB as float32, and it can
be memory-mapped instead of parsed. A bundle is a directory holding ``ids.json``
and one ``<name>.npy`` per array, plus a manifest (dtype, shape, sha256) that the
registered artifact carries. Nothing here pickles.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

ALLOWED_DTYPES = frozenset({"float16", "float32", "float64", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "bool"})
_NAME = re.compile(r"[a-z][a-z0-9_]{0,39}")
_CHUNK = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(_CHUNK):
            digest.update(block)
    return digest.hexdigest()


def _checked_name(name: str) -> str:
    if not _NAME.fullmatch(name):
        raise ValueError(f"Array name must be lower-case letters, digits and underscores: {name!r}")
    return name


def _atomic_write(path: Path, writer) -> None:
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_array(directory: Path, name: str, array: np.ndarray) -> dict[str, Any]:
    """Write one array and return its manifest entry."""
    _checked_name(name)
    array = np.ascontiguousarray(array)
    if array.dtype.name not in ALLOWED_DTYPES:
        raise ValueError(f"Unsupported array dtype {array.dtype.name}")
    if array.dtype.kind == "f" and not np.isfinite(array).all():
        raise ValueError(f"Array {name} holds non-finite values")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.npy"
    _atomic_write(path, lambda stream: np.save(stream, array, allow_pickle=False))
    return {"file": path.name, "dtype": array.dtype.name, "shape": list(array.shape),
            "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def allocate_array(directory: Path, name: str, shape: Sequence[int], dtype: str) -> np.ndarray:
    """Create an empty memory-mapped ``.npy`` to be filled in place; call ``describe_array`` once it is complete."""
    _checked_name(name)
    if dtype not in ALLOWED_DTYPES:
        raise ValueError(f"Unsupported array dtype {dtype}")
    directory.mkdir(parents=True, exist_ok=True)
    return np.lib.format.open_memmap(directory / f"{name}.npy", mode="w+", dtype=np.dtype(dtype), shape=tuple(shape))


def describe_array(directory: Path, name: str) -> dict[str, Any]:
    """Manifest entry for an array file already on disk (flushes nothing; callers flush their memmap first)."""
    path = directory / f"{_checked_name(name)}.npy"
    array = np.load(path, mmap_mode="r", allow_pickle=False)
    if array.dtype.kind == "f" and not np.isfinite(array).all():
        raise ValueError(f"Array {name} holds non-finite values")
    return {"file": path.name, "dtype": array.dtype.name, "shape": list(array.shape), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def write_ids(directory: Path, ids: Sequence[str]) -> dict[str, Any]:
    payload = json.dumps(list(ids), ensure_ascii=False, separators=(",", ":")).encode()
    _atomic_write(directory / "ids.json", lambda stream: stream.write(payload))
    return {"file": "ids.json", "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def write_bundle(directory: Path, ids: Sequence[str], arrays: Mapping[str, np.ndarray],
                 extras: Mapping[str, np.ndarray] | None = None) -> dict[str, Any]:
    """Write ids and arrays (each with ``len(ids)`` rows) and return the manifest.

    ``extras`` are arrays that are not row-aligned, such as cluster centres.
    """
    ids = list(ids)
    if len(set(ids)) != len(ids):
        raise ValueError("Bundle ids must be unique")
    entries = {}
    for name, array in arrays.items():
        if len(array) != len(ids):
            raise ValueError(f"Array {name} has {len(array)} rows for {len(ids)} ids")
        entries[name] = write_array(directory, name, array)
    extra_entries = {}
    for name, array in (extras or {}).items():
        if name in entries:
            raise ValueError(f"Extra array {name} repeats a row array name")
        extra_entries[name] = write_array(directory, name, array)
    return {"count": len(ids), "ids": write_ids(directory, ids), "arrays": entries, **({"extras": extra_entries} if extra_entries else {})}


def _inside(directory: Path, file: str) -> Path:
    path = (directory / file).resolve()
    if path.parent != directory.resolve() or path.is_symlink():
        raise ValueError("Bundle file escapes its directory")
    return path


def read_array(directory: Path, entry: Mapping[str, Any], *, mmap: bool = True, verify: bool = False) -> np.ndarray:
    """Load one array, memory-mapped by default. ``verify`` re-hashes the file first."""
    path = _inside(directory, str(entry["file"]))
    if verify and sha256_file(path) != entry["sha256"]:
        raise ValueError(f"Array file {path.name} does not match its recorded checksum")
    array = np.load(path, mmap_mode="r" if mmap else None, allow_pickle=False)
    if array.dtype.name != entry["dtype"] or list(array.shape) != list(entry["shape"]):
        raise ValueError(f"Array file {path.name} disagrees with its manifest")
    return array


def read_ids(directory: Path, manifest: Mapping[str, Any]) -> list[str]:
    path = _inside(directory, str(manifest["ids"]["file"]))
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest["ids"]["sha256"]:
        raise ValueError("Bundle ids do not match their recorded checksum")
    ids = json.loads(payload)
    if len(ids) != manifest["count"]:
        raise ValueError("Bundle id count disagrees with its manifest")
    return ids
