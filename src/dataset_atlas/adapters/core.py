"""Reusable adapters with stable source IDs, bounded preparation and explicit joins.

Configuration lives in a local Dataset.adapter_config; it is never copied to a
public pack. Network reads require an explicit byte and row budget.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import tarfile
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlencode, urlparse
import zipfile

import httpx

from dataset_atlas.models import Asset, Dataset, FieldDescriptor, Pack, Record, stable_id
from dataset_atlas.storage.local import read_rooted_file
from dataset_atlas.storage import BoundedCache, CacheIdentity, HttpsFetcher


@dataclass(frozen=True)
class SourceDescription:
    kind: str
    location: str
    exists: bool
    source_revision: str
    size_bytes: int | None
    streaming: bool
    random_access: bool
    resumable: bool
    requires_local_copy: bool
    selective_media: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparationPlan:
    dataset_id: str
    source_revision: str
    cursor: str | None
    limit: int
    max_bytes: int
    expected_download_bytes: int | None
    expected_output_bytes: int | None
    requirements: tuple[str, ...] = ()
    uncertainty: str = ""


@dataclass
class PreparedSource:
    dataset_id: str
    source_revision: str
    max_bytes: int
    limit: int
    location: str
    bytes_read: int = 0

    def charge(self, amount: int) -> None:
        self.bytes_read += amount
        if self.bytes_read > self.max_bytes:
            raise ValueError(f"source byte budget exceeded: {self.bytes_read} > {self.max_bytes}")


@dataclass(frozen=True)
class RecordBatch:
    records: list[Record]
    next_cursor: str | None
    source_rows_read: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MediaHandle:
    data: bytes
    media_type: str
    sha256: str
    source_ref: str


@dataclass(frozen=True)
class ValidationReport:
    checked_count: int
    duplicate_source_ids: tuple[str, ...] = ()
    unmatched_overlay_ids: tuple[str, ...] = ()
    multiply_matched_overlay_ids: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def _nested(row: dict[str, Any], key: str | None) -> Any:
    if not key:
        return None
    value: Any = row
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _safe_relative(value: str) -> str:
    if not value or "\x00" in value or "\\" in value or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise ValueError(f"unsafe relative asset path: {value!r}")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not value or any(p in {"..", ""} for p in path.parts):
        raise ValueError(f"unsafe relative asset path: {value!r}")
    return str(path)


def _write_rooted_atomic(root: Path, relative: str, data: bytes) -> None:
    """Cache one media file beneath a configured root without following symlinks."""
    parts = _safe_relative(relative).split("/")
    root.mkdir(parents=True, exist_ok=True)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, dir_fd=directory)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=directory)
            os.close(directory)
            directory = child
        temporary = f".{parts[-1]}.{secrets.token_hex(8)}.part"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, parts[-1], src_dir_fd=directory, dst_dir_fd=directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
    finally:
        os.close(directory)


def _media_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif", ".mp3": "audio/mpeg",
            ".wav": "audio/wav", ".mp4": "video/mp4"}.get(suffix, "application/octet-stream")


class DatasetAdapter:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset
        self.config = dataset.adapter_config
        self.revision = dataset.release

    def probe(self) -> SourceDescription:
        raise NotImplementedError

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        # Large releases may be prepared when the caller has explicitly
        # approved their source-specific budget. The preview default remains
        # 20 MB, and adapters still enforce the approved cap while reading.
        if not 1 <= limit <= 1000 or not 1 <= max_bytes <= 10_000_000_000_000:
            raise ValueError("an explicit positive row and byte budget is required")
        desc = self.probe()
        if not desc.exists:
            raise FileNotFoundError(desc.location)
        expected_download = (desc.size_bytes if urlparse(desc.location).scheme in {"http", "https"}
                             else None if desc.kind == "huggingface_rows" else 0)
        return PreparationPlan(self.dataset.id, desc.source_revision, cursor, limit, max_bytes,
                               expected_download, None, desc.notes,
                               "source row widths are unknown" if desc.size_bytes is None else "")

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        if approved_plan.dataset_id != self.dataset.id or approved_plan.source_revision != self.revision:
            raise ValueError("plan does not match dataset release")
        return PreparedSource(self.dataset.id, self.revision, approved_plan.max_bytes,
                              approved_plan.limit, self.probe().location)

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        raise NotImplementedError

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        raise NotImplementedError

    def validate(self, source: PreparedSource, limit: int = 1000) -> ValidationReport:
        seen: set[str] = set()
        dup: set[str] = set()
        cursor = None
        count = 0
        while count < limit:
            batch = self.iter_records(source, cursor, min(100, limit - count))
            for rec in batch.records:
                if rec.id in seen:
                    dup.add(rec.id)
                seen.add(rec.id)
            count += len(batch.records)
            if not batch.next_cursor or not batch.records:
                break
            cursor = batch.next_cursor
        return ValidationReport(count, tuple(sorted(dup)))

    def _record(self, row: dict[str, Any], ordinal: int | str) -> Record:
        mapping = self.config.get("mapping", {})
        source_id = _nested(row, mapping.get("id"))
        if source_id is None:
            # Only valid when a pinned, immutable source snapshot fixes ordering.
            if not self.dataset.snapshot_id:
                raise ValueError("row lacks upstream ID and dataset lacks pinned snapshot")
            source_id = f"row:{ordinal}"
        source_id = str(source_id)
        rid = stable_id(self.dataset.id, self.revision, "example", source_id)
        source_fields = dict(row)
        assets: list[Asset] = []
        image_key = mapping.get("media")
        value = _nested(row, image_key)
        if value:
            values = value if isinstance(value, list) else [value]
            for i, item in enumerate(values):
                if isinstance(item, dict):
                    item = item.get("path") or item.get("src") or item.get("url")
                if not isinstance(item, str):
                    continue
                aid = stable_id(self.dataset.id, self.revision, "asset", item)
                assets.append(Asset(id=aid, dataset_id=self.dataset.id,
                                    release_id=self.revision, modality=mapping.get("media_modality", "image"),
                                    uri=item, metadata={"source_field": image_key, "order": i}))
            # Keep source filenames as queryable fields. Avoid embedding image
            # objects or base64 payloads in a JSON preview pack.
            if isinstance(value, dict) or (isinstance(value, list) and any(isinstance(x, dict) for x in value)):
                source_fields.pop(image_key.split(".")[0], None)
        text = _nested(row, mapping.get("text"))
        question = _nested(row, mapping.get("question"))
        choices = _nested(row, mapping.get("choices"))
        return Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                      snapshot_id=self.dataset.snapshot_id, unit="example",
                      asset_ids=[a.id for a in assets], assets=assets,
                      text=str(text) if text is not None else None,
                      question=str(question) if question is not None else None,
                      choices=choices if isinstance(choices, list) else [], source=source_fields)


class StructuredAdapter(DatasetAdapter):
    """Local JSON, JSONL, CSV and Parquet files. Reopening at cursor is bounded in memory."""

    def _path(self) -> Path:
        value = self.config.get("path")
        if not value:
            raise ValueError("structured adapter requires path")
        return Path(value).expanduser().resolve()

    def probe(self) -> SourceDescription:
        path = self._path()
        kind = self.config.get("format", path.suffix.lstrip(".")).lower()
        if kind not in {"json", "jsonl", "csv", "parquet"}:
            raise ValueError(f"unsupported structured format: {kind}")
        exists = path.is_file()
        return SourceDescription(kind, str(path), exists, self.revision,
                                 path.stat().st_size if exists else None,
                                 kind in {"jsonl", "csv", "parquet"}, kind == "parquet",
                                 True, False, False)

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        expected = self.config.get("sha256")
        if expected:
            digest = hashlib.sha256()
            with self._path().open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError("source checksum differs from pinned snapshot")
        return source

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        plan = super().plan(limit, max_bytes, cursor)
        if self.probe().kind == "json" and self._path().stat().st_size > max_bytes:
            raise ValueError("JSON source requires loading the entire file and exceeds byte budget")
        return plan

    def _rows(self) -> Iterator[dict[str, Any]]:
        path = self._path()
        kind = self.probe().kind
        if kind == "jsonl":
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)
        elif kind == "csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                yield from csv.DictReader(handle)
        elif kind == "json":
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            key = self.config.get("records_key")
            if key:
                data = _nested(data, key)
            if not isinstance(data, list):
                raise ValueError("JSON source must contain a list of records")
            yield from data
        else:
            import pyarrow.parquet as pq
            parquet = pq.ParquetFile(path)
            for batch in parquet.iter_batches(batch_size=128):
                yield from batch.to_pylist()

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        size = min(limit or source.limit, source.limit)
        start = int(cursor or 0)
        if start < 0:
            raise ValueError("negative cursor")
        if self.probe().kind == "parquet":
            return self._parquet_records(source, start, size)
        out = []
        more = False
        for i, row in enumerate(self._rows()):
            if i < start:
                continue
            if len(out) >= size:
                more = True
                break
            source.charge(len(json.dumps(row, ensure_ascii=False, default=str).encode()))
            out.append(self._record(row, i))
        return RecordBatch(out, str(start + len(out)) if more else None, len(out))

    def _parquet_records(self, source: PreparedSource, start: int, size: int) -> RecordBatch:
        """Seek by Parquet row-group counts before decoding the requested page."""
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(self._path())
        total = parquet.metadata.num_rows
        if start >= total:
            return RecordBatch([], None, 0)
        group_start = 0
        first_group = 0
        for index in range(parquet.metadata.num_row_groups):
            group_end = group_start + parquet.metadata.row_group(index).num_rows
            if start < group_end:
                first_group = index
                break
            group_start = group_end
        skip = start - group_start
        out: list[Record] = []
        for group in range(first_group, parquet.metadata.num_row_groups):
            for batch in parquet.iter_batches(batch_size=128, row_groups=[group]):
                if skip >= batch.num_rows:
                    skip -= batch.num_rows
                    continue
                selected = batch.slice(skip, min(size - len(out), batch.num_rows - skip))
                skip = 0
                for row in selected.to_pylist():
                    source.charge(len(json.dumps(row, ensure_ascii=False, default=str).encode()))
                    out.append(self._record(row, start + len(out)))
                if len(out) == size:
                    end = start + len(out)
                    return RecordBatch(out, str(end) if end < total else None, len(out))
        end = start + len(out)
        return RecordBatch(out, str(end) if end < total else None, len(out))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        root_value = self.config.get("media_root")
        name = _safe_relative(asset_ref)
        path = None
        if root_value:
            root = Path(root_value).expanduser().resolve()
            path = root / name
        if path and path.is_file():
            data = read_rooted_file(path, [root], source.max_bytes - source.bytes_read)
        else:
            base_url = self.config.get("media_base_url")
            if not base_url or not base_url.startswith("https://") or not self.config.get("media_revision"):
                raise ValueError("asset is absent and no pinned HTTPS media source is configured")
            if self.config["media_revision"] not in base_url:
                raise ValueError("media URL does not contain configured revision")
            if not root_value:
                raise ValueError("pinned remote media requires a configured local media root")
            url = base_url.rstrip("/") + "/" + name
            source_host = urlparse(base_url).hostname
            allowed_hosts = self.config.get("media_allowed_hosts", [source_host])
            if (not source_host or not isinstance(allowed_hosts, list)
                    or source_host not in allowed_hosts
                    or not all(isinstance(host, str) and host for host in allowed_hosts)):
                raise ValueError("pinned remote media requires explicit source/CDN host allowlist")
            remaining = source.max_bytes - source.bytes_read
            if remaining <= 0:
                raise ValueError("asset exceeds remaining byte budget")
            cache_root = Path(self.config.get("media_fetch_cache", root.parent / ".media-fetch-cache"))
            cache_limit = int(self.config.get("media_fetch_cache_max_bytes", 500_000_000))
            cache = BoundedCache(cache_root, cache_limit)
            identity = CacheIdentity(self.config["media_revision"],
                                     stable_id(self.dataset.id, self.revision, "asset", name),
                                     "original")
            fetched = HttpsFetcher(allowed_hosts, timeout=20, max_redirects=4,
                                   max_bytes=min(remaining, 100_000_000)).fetch(
                                       url, cache, identity, byte_budget=remaining)
            data = read_rooted_file(fetched, [cache.root], remaining)
            source.charge(len(data))
            _write_rooted_atomic(root, name, data)
            return MediaHandle(data, _media_type(name), hashlib.sha256(data).hexdigest(), name)
        source.charge(len(data))
        return MediaHandle(data, _media_type(name), hashlib.sha256(data).hexdigest(), name)


class HTTPSStructuredAdapter(StructuredAdapter):
    """Download a single immutable structured file only after a bounded plan."""

    def _url(self) -> str:
        url = self.config.get("url", "")
        revision = self.config.get("revision", "")
        if not url.startswith("https://") or not revision or revision not in url:
            raise ValueError("HTTPS source requires a URL containing its pinned revision")
        if not self.config.get("sha256"):
            raise ValueError("HTTPS source requires SHA-256 integrity")
        return url

    def probe(self) -> SourceDescription:
        url = self._url()
        path = self._path()
        kind = self.config.get("format", path.suffix.lstrip(".")).lower()
        if kind not in {"json", "jsonl", "csv", "parquet"}:
            raise ValueError(f"unsupported structured format: {kind}")
        if path.is_file():
            return SourceDescription(kind, url, True, self.revision, path.stat().st_size,
                                     kind in {"jsonl", "csv", "parquet"}, kind == "parquet",
                                     True, False, False, ("cached source file; SHA-256 checked at prepare",))
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                response = client.head(url)
                response.raise_for_status()
                size_header = response.headers.get("content-length")
        except httpx.HTTPError:
            return SourceDescription(kind, url, False, self.revision, None,
                                     kind in {"jsonl", "csv", "parquet"}, False,
                                     False, True, False, ("HTTPS source unavailable at probe",))
        return SourceDescription(kind, url, True, self.revision,
                                 int(size_header) if size_header and size_header.isdigit() else None,
                                 kind in {"jsonl", "csv", "parquet"}, False,
                                 False, True, False, ("entire structured file must be downloaded",))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        plan = DatasetAdapter.plan(self, limit, max_bytes, cursor)
        expected_download = 0 if self._path().is_file() else plan.expected_download_bytes
        if expected_download is not None and expected_download > max_bytes:
            raise ValueError("HTTPS source exceeds approved byte budget")
        return PreparationPlan(plan.dataset_id, plan.source_revision, plan.cursor, plan.limit,
                               plan.max_bytes, expected_download, plan.expected_output_bytes,
                               plan.requirements, plan.uncertainty)

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        if approved_plan.dataset_id != self.dataset.id or approved_plan.source_revision != self.revision:
            raise ValueError("plan does not match dataset release")
        path = self._path()
        source = PreparedSource(self.dataset.id, self.revision, approved_plan.max_bytes,
                                approved_plan.limit, self._url())
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            staged = path.with_name(path.name + ".part")
            digest = hashlib.sha256()
            try:
                with httpx.Client(timeout=30, follow_redirects=True) as client:
                    with client.stream("GET", self._url()) as response:
                        response.raise_for_status()
                        with staged.open("wb") as handle:
                            for chunk in response.iter_bytes():
                                source.charge(len(chunk))
                                digest.update(chunk)
                                handle.write(chunk)
                if digest.hexdigest() != self.config["sha256"]:
                    raise ValueError("download checksum differs from pinned snapshot")
                staged.replace(path)
            finally:
                staged.unlink(missing_ok=True)
        if path.stat().st_size > approved_plan.max_bytes:
            raise ValueError("cached source exceeds approved byte budget")
        expected = self.config["sha256"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError("cached source checksum differs from pinned snapshot")
        return source


class DirectoryArchiveAdapter(DatasetAdapter):
    """Media files in a directory or archive, one asset/example per member."""

    def _path(self) -> Path:
        return Path(self.config["path"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        path = self._path()
        kind = "directory" if path.is_dir() else "archive"
        exists = path.is_dir() or path.is_file()
        return SourceDescription(kind, str(path), exists, self.revision,
                                 path.stat().st_size if exists and path.is_file() else None,
                                 True, False, True, False, True,
                                 ("archive member reads may require scanning the archive",) if kind == "archive" else ())

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        expected = self.config.get("sha256")
        path = self._path()
        if expected and path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(4 << 20), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError("archive differs from pinned SHA-256")
        return source

    def _names(self) -> list[str]:
        cached = getattr(self, "_cached_names", None)
        if cached is not None:
            return cached
        path = self._path()
        suffixes = {suffix.lower() for suffix in self.config.get("suffixes", [".jpg", ".jpeg", ".png", ".webp"])}
        if self.config.get('original_access_index'):
            from dataset_atlas.storage.indexed_tar import IndexedTarArchive
            names = [i.filename for i in IndexedTarArchive(self.config['original_access_index']).infolist()]
        elif path.is_dir():
            names = [str(p.relative_to(path).as_posix()) for p in path.rglob("*") if p.is_file()]
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                names = [i.filename for i in archive.infolist() if not i.is_dir()]
        elif tarfile.is_tarfile(path):
            with tarfile.open(path) as archive:
                names = [i.name for i in archive.getmembers() if i.isfile()]
        else:
            raise ValueError("unsupported archive")
        names = sorted(_safe_relative(n) for n in names if PurePosixPath(n).suffix.lower() in suffixes)
        pattern = self.config.get("path_regex")
        if pattern:
            compiled = re.compile(pattern)
            names = [name for name in names if compiled.fullmatch(name)]
        if self.config.get("order") == "round_robin_label":
            if not pattern or "label" not in compiled.groupindex:
                raise ValueError("round_robin_label requires a path_regex label group")
            groups: dict[str, list[str]] = {}
            for name in names:
                groups.setdefault(compiled.fullmatch(name).group("label"), []).append(name)
            ordered: list[str] = []
            for ordinal in range(max(map(len, groups.values()), default=0)):
                for label in sorted(groups):
                    if ordinal < len(groups[label]):
                        ordered.append(groups[label][ordinal])
            names = ordered
        elif self.config.get("order") == "section_priority":
            if not pattern or "section" not in compiled.groupindex:
                raise ValueError("section_priority requires a path_regex section group")
            priorities = self.config.get("section_priority")
            if not isinstance(priorities, list) or len(priorities) != len(set(priorities)):
                raise ValueError("section_priority requires a unique ordered section list")
            rank = {section: index for index, section in enumerate(priorities)}
            sections = {compiled.fullmatch(name).group("section") for name in names}
            if sections != set(rank):
                raise ValueError("section_priority must enumerate every source section")
            names.sort(key=lambda name: (rank[compiled.fullmatch(name).group("section")], name))
        self._cached_names = names
        return names

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        names = self._names()
        start = int(cursor or 0)
        size = min(limit or source.limit, source.limit)
        out = []
        for name in names[start:start + size]:
            source.charge(len(name.encode()))
            aid = stable_id(self.dataset.id, self.revision, "asset", name)
            rid = stable_id(self.dataset.id, self.revision, "example", name)
            asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                          modality="image", uri=name)
            source_fields = {"path": name}
            if self.config.get("path_regex"):
                source_fields.update(re.fullmatch(self.config["path_regex"], name).groupdict())
                label = source_fields.get("label")
                if label in self.config.get("label_names", {}):
                    source_fields["class_name"] = self.config["label_names"][label]
                if label in self.config.get("label_indices", {}):
                    source_fields[self.config.get("label_index_field", "class_index")] = \
                        self.config["label_indices"][label]
                for index_field, index_map in self.config.get("label_index_maps", {}).items():
                    if label not in index_map:
                        raise ValueError(f"archive label absent from {index_field} mapping: {label}")
                    source_fields[index_field] = index_map[label]
                for key, field_type in self.config.get("field_types", {}).items():
                    if key not in source_fields:
                        raise ValueError(f"missing captured field for cast: {key}")
                    if field_type == "integer":
                        source_fields[key] = int(source_fields[key])
                    else:
                        raise ValueError(f"unsupported captured field cast: {field_type}")
            constants = self.config.get("constant_fields", {})
            if not isinstance(constants, dict) or set(constants) & set(source_fields):
                raise ValueError("constant_fields must be a mapping without source field collisions")
            source_fields.update(constants)
            out.append(Record(id=rid, dataset_id=self.dataset.id,
                              release_id=self.revision, snapshot_id=self.dataset.snapshot_id,
                              asset_ids=[aid], assets=[asset], source=source_fields))
        end = start + len(out)
        return RecordBatch(out, str(end) if end < len(names) else None, len(out))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        name = _safe_relative(asset_ref)
        path = self._path()
        if self.config.get('original_access_index'):
            from dataset_atlas.storage.indexed_tar import read_tar_member
            data, _ = read_tar_member(self.config['original_access_index'], name,
                max_bytes=source.max_bytes - source.bytes_read, local_source=self.config.get('original_archive_path'))
        elif path.is_dir():
            data = read_rooted_file(path / name, [path], source.max_bytes - source.bytes_read)
        elif zipfile.is_zipfile(path):
            from dataset_atlas.storage.zip_members import LOCAL_ZIP_MEMBERS
            data = LOCAL_ZIP_MEMBERS.read(path, name, source.max_bytes - source.bytes_read, self.config.get('sha256'))
        else:
            with tarfile.open(path) as archive:
                member = archive.getmember(name)
                if not member.isfile() or member.size > source.max_bytes - source.bytes_read:
                    raise ValueError("asset absent or exceeds remaining byte budget")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("asset absent")
                data = stream.read(source.max_bytes - source.bytes_read + 1)
        source.charge(len(data))
        return MediaHandle(data, _media_type(name), hashlib.sha256(data).hexdigest(), name)


class HuggingFaceRowsAdapter(DatasetAdapter):
    """Paged HF dataset-server rows; live API caveat is explicit.

    The endpoint currently ignores a `revision` query parameter. We require
    an opt-in and verify repository HEAD before every page, but cannot prove
    the server's materialization matches that HEAD. Use a pinned source file
    for release-grade packs.
    """

    API = "https://datasets-server.huggingface.co/rows"

    def probe(self) -> SourceDescription:
        repo = self.config.get("repository")
        split = self.config.get("split")
        config = self.config.get("config")
        if not all([repo, split, config]):
            raise ValueError("HF source requires repository, config and split")
        return SourceDescription("huggingface_rows", f"{repo}/{config}/{split}", True,
                                 self.revision, None, True, False, True, False, False,
                                 ("HF rows API is live and does not honor a revision query parameter",))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        if not self.config.get("allow_live_rows"):
            raise ValueError("HF rows API is live; set allow_live_rows only for explicitly non-pinned exploration")
        super().plan(limit, max_bytes, cursor)
        return PreparationPlan(self.dataset.id, self.revision, cursor, limit, max_bytes,
                               None, None, ("remote live rows API, paged reads",),
                               "response sizes and source revision are not guaranteed by rows API; hard byte budget is enforced")

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        size = min(limit or source.limit, source.limit, 100)
        offset = int(cursor or 0)
        params = {"dataset": self.config["repository"], "config": self.config["config"],
                  "split": self.config["split"], "offset": offset, "length": size}
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            with client.stream("GET", self.API, params=params) as response:
                response.raise_for_status()
                chunks = []
                for chunk in response.iter_bytes():
                    source.charge(len(chunk))
                    chunks.append(chunk)
        payload = json.loads(b"".join(chunks))
        rows = payload.get("rows", [])
        out = [self._record(item["row"], item.get("row_idx", offset + i))
               for i, item in enumerate(rows)]
        total = payload.get("num_rows_total")
        end = offset + len(out)
        more = (end < total) if isinstance(total, int) else len(out) == size
        return RecordBatch(out, str(end) if more else None, len(out))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        raise ValueError("HF media resolution requires a separately approved pinned media source")


class OverlayAdapter(StructuredAdapter):
    """Join annotations to base records while exposing all join defects."""

    def __init__(self, dataset: Dataset):
        super().__init__(dataset)
        self.base_config = self.config.get("base")
        self.overlay_config = self.config.get("overlay")
        if not isinstance(self.base_config, dict) or not isinstance(self.overlay_config, dict):
            raise ValueError("overlay adapter requires base and overlay configurations")

    def _reader(self, config: dict[str, Any]) -> StructuredAdapter:
        data = self.dataset.model_copy(update={"adapter_config": config})
        return StructuredAdapter(data)

    def probe(self) -> SourceDescription:
        base = self._reader(self.base_config).probe()
        overlay = self._reader(self.overlay_config).probe()
        return SourceDescription("overlay", f"{base.location} + {overlay.location}",
                                 base.exists and overlay.exists, self.revision,
                                 (base.size_bytes or 0) + (overlay.size_bytes or 0),
                                 False, False, True, False, False,
                                 ("overlay joins require bounded local index preparation",))

    def _joined(self) -> tuple[list[dict[str, Any]], ValidationReport]:
        base = list(self._reader(self.base_config)._rows())
        overlay = list(self._reader(self.overlay_config)._rows())
        base_key = self.config["join_base_key"]
        overlay_key = self.config["join_overlay_key"]
        index: dict[str, list[dict[str, Any]]] = {}
        errors: list[str] = []
        for ordinal, row in enumerate(overlay):
            value = _nested(row, overlay_key)
            if value is None:
                errors.append(f"overlay row {ordinal} lacks join key {overlay_key}")
                continue
            index.setdefault(str(value), []).append(row)
        matched = set()
        seen_base: set[str] = set()
        duplicate_base: set[str] = set()
        joined = []
        for ordinal, row in enumerate(base):
            value = _nested(row, base_key)
            if value is None:
                errors.append(f"base row {ordinal} lacks join key {base_key}")
                key = None
            else:
                key = str(value)
                if key in seen_base:
                    duplicate_base.add(key)
                seen_base.add(key)
            matches = index.get(key, []) if key is not None else []
            if matches:
                matched.add(key)
            result = dict(row)
            result["overlay"] = matches
            joined.append(result)
        return joined, ValidationReport(len(joined),
                                        duplicate_source_ids=tuple(sorted(duplicate_base)),
                                        unmatched_overlay_ids=tuple(sorted(set(index) - matched)),
                                        multiply_matched_overlay_ids=tuple(sorted(k for k, v in index.items() if len(v) > 1)),
                                        errors=tuple(errors))

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        if self.probe().size_bytes > source.max_bytes:
            raise ValueError("overlay sources exceed preparation byte budget")
        rows, report = self._joined()
        start = int(cursor or 0)
        size = min(limit or source.limit, source.limit)
        out = [self._record(row, i) for i, row in enumerate(rows[start:start + size], start)]
        end = start + len(out)
        warnings = tuple(f"unmatched overlay ID: {x}" for x in report.unmatched_overlay_ids) + \
                   tuple(f"multiply matched overlay ID: {x}" for x in report.multiply_matched_overlay_ids) + \
                   tuple(f"duplicate base join ID: {x}" for x in report.duplicate_source_ids) + report.errors
        return RecordBatch(out, str(end) if end < len(rows) else None, len(out), warnings)

    def validate(self, source: PreparedSource, limit: int = 1000) -> ValidationReport:
        if self.probe().size_bytes > source.max_bytes:
            raise ValueError("overlay sources exceed preparation byte budget")
        _, report = self._joined()
        return report


def get_adapter(dataset: Dataset) -> DatasetAdapter:
    if dataset.adapter == 'roco':
        from .roco import RocoAdapter
        return RocoAdapter(dataset)
    if dataset.adapter == 'qava':
        from .qava import QavaAdapter
        return QavaAdapter(dataset)
    if dataset.adapter == 'covid_radiography':
        from .covid_radiography import CovidRadiographyAdapter
        return CovidRadiographyAdapter(dataset)
    if dataset.adapter == 'safebench':
        from .safebench import SafeBenchAdapter
        return SafeBenchAdapter(dataset)
    if dataset.adapter == 'elife_workbooks':
        from .elife_workbooks import ElifeWorkbooksAdapter
        return ElifeWorkbooksAdapter(dataset)
    if dataset.adapter == 'figshare_stimuli':
        from .figshare_stimuli import FigshareStimuliAdapter
        return FigshareStimuliAdapter(dataset)
    if dataset.adapter == 'pathways_shapes':
        from .pathways_shapes import PathwaysShapesAdapter
        return PathwaysShapesAdapter(dataset)
    if dataset.adapter == 'find':
        from .find import FindAdapter
        return FindAdapter(dataset)
    if dataset.adapter == 'seed_bench':
        from .seed_bench import SeedBenchAdapter
        return SeedBenchAdapter(dataset)
    if dataset.adapter == 'vqa_constraints':
        from .vqa_constraints import VQAConstraintsAdapter
        return VQAConstraintsAdapter(dataset)
    if dataset.adapter == 'nocaps':
        from .nocaps import NocapsAdapter
        return NocapsAdapter(dataset)
    if dataset.adapter == 'textvqa_x':
        from .textvqa_x import TextVQAXAdapter
        return TextVQAXAdapter(dataset)
    if dataset.adapter == 'pathways':
        from .pathways import PathwaysAdapter
        return PathwaysAdapter(dataset)
    if dataset.adapter == 'sad_structs':
        from .sad import SADStructsAdapter
        return SADStructsAdapter(dataset)
    if dataset.adapter == 'text_pairs':
        from .text_pairs import TextPairsAdapter
        return TextPairsAdapter(dataset)
    if dataset.adapter == 'nrc_vad':
        from .nrc_vad import NRCVADAdapter
        return NRCVADAdapter(dataset)
    if dataset.adapter == 'inventory_variants':
        from .inventory_variants import InventoryVariantsAdapter
        return InventoryVariantsAdapter(dataset)
    if dataset.adapter == 'archive_variants':
        from .archive_variants import ArchiveVariantsAdapter
        return ArchiveVariantsAdapter(dataset)
    if dataset.adapter == 'mm_safetybench':
        from .mm_safetybench import MMSafetyBenchAdapter
        return MMSafetyBenchAdapter(dataset)
    if dataset.adapter == 'mme':
        from .mme import MMEAdapter
        return MMEAdapter(dataset)
    if dataset.adapter == 'sun397':
        from .sun397 import SUN397Adapter
        return SUN397Adapter(dataset)
    if dataset.adapter == 'emnist_archive':
        from .emnist import EMNISTAdapter
        return EMNISTAdapter(dataset)
    if dataset.adapter == 'ravel':
        from .ravel import RavelAdapter
        return RavelAdapter(dataset)
    if dataset.adapter == 'embedded_tsv':
        from .embedded_tsv import EmbeddedTSVAdapter
        return EmbeddedTSVAdapter(dataset)
    if dataset.adapter == "coco_images":
        from .coco_images import CocoImagesAdapter
        return CocoImagesAdapter(dataset)
    if dataset.adapter == "coco_questions":
        from .coco_questions import CocoQuestionsAdapter
        return CocoQuestionsAdapter(dataset)
    if dataset.adapter == "perceptual":
        from .perceptual import PerceptualAdapter
        return PerceptualAdapter(dataset)
    if dataset.adapter == "visual_genome":
        from .visual_genome import VisualGenomeAdapter
        return VisualGenomeAdapter(dataset)
    if dataset.adapter == "phantom":
        from .phantom import PhantomAdapter
        return PhantomAdapter(dataset)
    if dataset.adapter == "structured_collection":
        from .structured_collection import StructuredCollectionAdapter
        return StructuredCollectionAdapter(dataset)
    if dataset.adapter == "remote_columnar":
        from .remote_columnar import RemoteColumnarAdapter
        return RemoteColumnarAdapter(dataset)
    if dataset.adapter == "classic_vision":
        from .classic_vision import ClassicVisionAdapter
        return ClassicVisionAdapter(dataset)
    if dataset.adapter == "cifar_c_npy":
        from .corruptions import CIFARCorruptionsAdapter
        return CIFARCorruptionsAdapter(dataset)
    if dataset.adapter == "annotated_archive":
        from .annotated_archive import AnnotatedArchiveAdapter
        return AnnotatedArchiveAdapter(dataset)
    if dataset.adapter == "oxford_archive":
        from .oxford import OxfordArchiveAdapter
        return OxfordArchiveAdapter(dataset)
    if dataset.adapter == "columnar":
        from .columnar import ColumnarAdapter
        return ColumnarAdapter(dataset)
    if dataset.adapter in {"idx", "cifar_binary", "cifar100_binary"}:
        from .binary import CIFAR100BinaryAdapter, CIFARBinaryAdapter, IDXAdapter
        return {"idx": IDXAdapter, "cifar_binary": CIFARBinaryAdapter,
                "cifar100_binary": CIFAR100BinaryAdapter}[dataset.adapter](dataset)
    if dataset.adapter == "clevr_full":
        from .clevr_full import CLEVRFullAdapter
        return CLEVRFullAdapter(dataset)
    if dataset.adapter == "coco":
        from .coco import CocoAdapter
        return CocoAdapter(dataset)
    if dataset.adapter == "stl10":
        from .stl10 import STL10BinaryAdapter
        return STL10BinaryAdapter(dataset)
    if dataset.adapter == "svhn_cropped_mat":
        from .svhn import SVHNAdapter
        return SVHNAdapter(dataset)
    if dataset.adapter == "vqa_v2":
        from .vqa_v2 import VQAv2Adapter
        return VQAv2Adapter(dataset)
    if dataset.adapter == "gqa_balanced":
        from .gqa import GQABalancedAdapter
        return GQABalancedAdapter(dataset)
    if dataset.adapter == "docci":
        from .docci import DocciAdapter
        return DocciAdapter(dataset)
    if dataset.adapter == "artbench_binary":
        from .artbench import ArtBenchBinaryAdapter
        return ArtBenchBinaryAdapter(dataset)
    if dataset.adapter == "structured_archive":
        from .structured_archive import StructuredArchiveAdapter
        return StructuredArchiveAdapter(dataset)
    if dataset.adapter == "iconqa":
        from .iconqa import IconQAAdapter
        return IconQAAdapter(dataset)
    if dataset.adapter == "vhd11k":
        from .vhd11k import VHD11KAdapter
        return VHD11KAdapter(dataset)
    if dataset.adapter == "embedded_parquet":
        from .embedded_parquet import EmbeddedParquetAdapter
        return EmbeddedParquetAdapter(dataset)
    if dataset.adapter == "svo_probes":
        from .svo_probes import SVOProbesAdapter
        return SVOProbesAdapter(dataset)
    kinds = {"structured": StructuredAdapter, "json": StructuredAdapter,
             "jsonl": StructuredAdapter, "csv": StructuredAdapter,
             "parquet": StructuredAdapter, "https": HTTPSStructuredAdapter,
             "directory": DirectoryArchiveAdapter,
             "archive": DirectoryArchiveAdapter, "huggingface": HuggingFaceRowsAdapter,
             "overlay": OverlayAdapter}
    try:
        return kinds[dataset.adapter](dataset)
    except KeyError as exc:
        raise ValueError(f"unknown adapter: {dataset.adapter}") from exc


from collections import OrderedDict
import threading
_PREPARED_ADAPTERS: OrderedDict[str, DatasetAdapter] = OrderedDict()
_PREPARED_ADAPTER_LOCK = threading.RLock()
_DECODED_CACHES: dict[str, BoundedCache] = {}


def _decoded_cache(cache_root: Path) -> BoundedCache:
    """The media endpoint is the hottest route; reuse its cache handle per root."""
    key = str(Path(cache_root).resolve())
    cache = _DECODED_CACHES.get(key)
    if cache is None:
        cache = BoundedCache(cache_root, max_bytes=1_000_000_000)
        _DECODED_CACHES[key] = cache
    return cache


def resolve_dataset_asset(dataset: Dataset, asset_ref: str,
                          max_bytes: int = 10_000_000, cache_root: Path | None = None,
                          workspace_root: Path | None = None) -> MediaHandle:
    """Resolve one configured source asset for the workbench media endpoint.

    Preparation is cached per dataset configuration; each media request still
    gets an independent byte limit. The reference must come from a Record
    produced by this adapter, not an arbitrary client-supplied filesystem path.
    """
    if max_bytes < 1 or max_bytes > 250_000_000:
        raise ValueError("invalid per-asset byte budget")
    key = hashlib.sha256(dataset.model_dump_json().encode()).hexdigest()
    cache = _decoded_cache(cache_root) if cache_root is not None else None
    identity=CacheIdentity(key,asset_ref,'decoded-original-v1')
    if cache:
        cached=cache.get(identity)
        if cached:
            if cached.stat().st_size>max_bytes+1024:raise ValueError('Cached asset exceeds byte budget')
            mime,data=cached.read_bytes().split(b'\n',1)
            if len(data)>max_bytes:raise ValueError('Cached asset exceeds byte budget')
            return MediaHandle(data,mime.decode('ascii'),hashlib.sha256(data).hexdigest(),asset_ref)
    if workspace_root is not None:
        # Workbench compression never changes canonical model inputs. Protected
        # originals and range-addressable native archives survive source eviction.
        root = Path(workspace_root).resolve()
        from dataset_atlas.storage.compact import compact_entry, read_compact
        entry = compact_entry(root, dataset.id, dataset.snapshot_id, asset_ref)
        if entry and entry['representation'] == 'original':
            data, mime, proof = read_compact(root, dataset.id, dataset.snapshot_id, asset_ref, max_bytes)
            return MediaHandle(data, mime, proof['original_sha256'], asset_ref)
        from dataset_atlas.storage.indexed_tar import read_original_route
        original = read_original_route(root, dataset.id, dataset.snapshot_id, asset_ref, max_bytes)
        if original:
            import mimetypes
            data, proof = original
            return MediaHandle(data, mimetypes.guess_type(asset_ref)[0] or 'application/octet-stream', proof['sha256'], asset_ref)
    with _PREPARED_ADAPTER_LOCK:
        adapter = _PREPARED_ADAPTERS.get(key)
        if adapter is None:
            adapter = get_adapter(dataset)
            prep_budget = int(dataset.adapter_config.get("preparation_budget_bytes", max_bytes))
            plan = adapter.plan(1, prep_budget)
            adapter.prepare(plan)
            _PREPARED_ADAPTERS[key] = adapter
            while len(_PREPARED_ADAPTERS) > 6:
                _PREPARED_ADAPTERS.popitem(last=False)
        _PREPARED_ADAPTERS.move_to_end(key)
    source = PreparedSource(dataset.id, dataset.release, max_bytes, 1, adapter.probe().location)
    handle=adapter.resolve_asset(source, asset_ref)
    if cache:
        import tempfile
        import fcntl
        with (cache.root/'partial'/(identity.key+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if not cache.get(identity):
                path=cache.partial_path(identity)
                with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as stream:
                    temporary=Path(stream.name)
                    stream.write(handle.media_type.encode('ascii')+b'\n'+handle.data)
                try:
                    os.replace(temporary,path)
                    cache.commit(identity,path)
                finally:temporary.unlink(missing_ok=True)
    return handle


def build_preview(dataset: Dataset, output_dir: Path, limit: int = 100,
                  max_bytes: int = 20_000_000, cursor: str | None = None,
                  distinct_assets: bool = False, include_media: bool = False, max_output_bytes: int | None = None, adapter: DatasetAdapter | None = None) -> Pack:
    """Make a local pack from a bounded plan. Publication is a separate rights gate."""
    adapter = adapter or get_adapter(dataset)
    plan = adapter.plan(limit, max_bytes, cursor)
    source = adapter.prepare(plan)
    records: list[Record] = []
    seen_assets: set[str] = set()
    next_cursor = cursor
    warnings: list[str] = []
    while len(records) < limit:
        batch = adapter.iter_records(source, next_cursor, min(100, limit - len(records)))
        for record in batch.records:
            if distinct_assets and record.asset_ids:
                if record.asset_ids[0] in seen_assets:
                    continue
                seen_assets.add(record.asset_ids[0])
            records.append(record)
        warnings.extend(batch.warnings)
        next_cursor = batch.next_cursor
        if not next_cursor or not batch.records:
            break
    checksums: dict[str, str] = {}
    if include_media:
        media_dir = output_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        for record in records:
            for asset in record.assets:
                if not asset.uri:
                    continue
                handle = adapter.resolve_asset(source, asset.uri)
                relative = f"media/{_safe_relative(asset.uri)}"
                target = output_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != handle.sha256:
                    raise ValueError(f"media filename collision: {relative}")
                target.write_bytes(handle.data)
                asset.uri = relative
                asset.sha256 = handle.sha256
                checksums[relative] = handle.sha256
    fields = []
    for field_id, spec in dataset.adapter_config.get("fields", {}).items():
        if isinstance(spec, dict):
            description = str(spec.get("description", ""))
            dtype = spec.get("dtype", "string")
            values = spec.get("values")
        else:
            description = str(spec)
            values = None
            values = [r.source.get(field_id) for r in records if field_id in r.source]
            value = next((v for v in values if v is not None), None)
            if isinstance(value, bool):
                dtype = "boolean"
            elif isinstance(value, (int, float)):
                dtype = "number"
            elif isinstance(value, list):
                dtype = "array"
            elif isinstance(value, dict):
                dtype = "object"
            else:
                dtype = "string"
        fields.append(FieldDescriptor(id=f"source.{field_id}", name=field_id,
                                      dtype=dtype, values=values, description=description,
                                      provenance={"source_url": dataset.source_url}))
    public_dataset = dataset.model_copy(update={"adapter_config": {}})
    pack = Pack(dataset=public_dataset, fields=fields, records=records,
                population_scope="preview",
                sampling={"method": "first_per_asset_source_order" if distinct_assets else "source_order", "unit": "example",
                          "population": dataset.adapter_config.get("population", "configured source split"),
                          "offset": int(cursor or 0), "requested_count": limit,
                          "returned_count": len(records),
                          "next_cursor": next_cursor,
                          "source_revision": dataset.release,
                          "bytes_read": source.bytes_read,
                          "warnings": warnings,
                          "selection_note": dataset.adapter_config.get("selection_note", "")},
                checksums=checksums)
    payload=pack.model_dump_json(indent=2)
    if max_output_bytes is not None and len(payload.encode())>max_output_bytes:
        raise ValueError("Preview exceeds approved output budget")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "pack.json"
    target.write_text(payload, encoding="utf-8")
    return pack
