"""Selective access to the official CLEVR v1.0 archive.

Only question JSON is materialized as JSONL. Images remain in the original ZIP
and are decompressed individually when a record's asset is requested.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from dataset_atlas.models import Asset, Record, stable_id

from .core import (DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource,
                   RecordBatch, SourceDescription)


def _questions(handle: io.TextIOBase):
    """Iterate objects in a CLEVR question array without loading the whole JSON."""
    decoder = json.JSONDecoder()
    buffer = ""
    eof = False
    prefix = re.compile(r'"questions"\s*:\s*\[')
    while True:
        match = prefix.search(buffer)
        if match:
            buffer = buffer[match.end():]
            break
        chunk = handle.read(1 << 20)
        if not chunk:
            raise ValueError("CLEVR JSON lacks a questions array")
        buffer = (buffer + chunk)[-2_000_000:]
    position = 0
    while True:
        while position < len(buffer) and buffer[position] in " \t\r\n,":
            position += 1
        if position < len(buffer) and buffer[position] == "]":
            return
        try:
            row, end = decoder.raw_decode(buffer, position)
        except json.JSONDecodeError:
            if eof or len(buffer) - position > 20_000_000:
                raise ValueError("invalid or oversized CLEVR question object") from None
            chunk = handle.read(1 << 20)
            eof = not chunk
            buffer += chunk
            continue
        if not isinstance(row, dict):
            raise ValueError("CLEVR question must be an object")
        yield row
        position = end
        if position > 1 << 20:
            buffer = buffer[position:]
            position = 0


class CLEVRFullAdapter(DatasetAdapter):
    """Full official train/val/test questions and selective original image bytes."""

    SPLITS = ("train", "val", "test")

    def _archive(self) -> Path:
        return Path(self.config["archive"]).expanduser().resolve()

    def _remote(self):
        """The official 19 GB archive as an ETag-pinned remote ZIP, when it is not held locally."""
        if "remote_archive" not in self.config:
            return None
        from .remote_media import RemoteZip
        return RemoteZip(self.config["remote_archive"], self.config["remote_cache_root"], self.config.get("remote_cache_bytes", 1_000_000_000))

    def _prepared(self) -> Path:
        return Path(self.config["prepared_root"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        archive = self._archive() if self._remote() is None else None
        present = archive.is_file() if archive else True
        return SourceDescription("clevr_full", str(archive) if archive else "remote ZIP", present,
                                 self.revision, archive.stat().st_size if archive and archive.is_file() else None,
                                 True, True, True, False, True,
                                 ("full official ZIP; question-only extraction, image-on-demand",))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        if self._remote() is None and not self.config.get("archive_sha256"):
            raise ValueError("full CLEVR archive requires a pinned SHA-256")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit,
                               max_bytes, 0, None,
                               ("verify full archive SHA-256; stream question JSON to indexed JSONL",),
                               "question JSONL output size is unknown until preparation")

    def _members(self, archive: zipfile.ZipFile) -> tuple[dict[str, str], str]:
        names = archive.namelist()
        questions: dict[str, str] = {}
        for split in self.SPLITS:
            suffix = f"questions/CLEVR_{split}_questions.json"
            found = [name for name in names if name.endswith(suffix)]
            if len(found) != 1:
                raise ValueError(f"expected one CLEVR {split} question member")
            questions[split] = found[0]
        prefix = questions["train"].split("questions/")[0]
        if any(not member.startswith(prefix) for member in questions.values()):
            raise ValueError("CLEVR question member roots disagree")
        return questions, prefix

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        remote = self._remote()
        if remote:
            # A ranged read cannot hash 19 GB; the strong ETag is the consistency fingerprint instead.
            fingerprint = "remote-etag:" + remote.etag
        else:
            digest = hashlib.sha256()
            with self._archive().open("rb") as handle:
                for chunk in iter(lambda: handle.read(4 << 20), b""):
                    digest.update(chunk)
            if digest.hexdigest() != self.config["archive_sha256"]:
                raise ValueError("CLEVR archive differs from pinned SHA-256")
            fingerprint = digest.hexdigest()
        root = self._prepared(); root.mkdir(parents=True, exist_ok=True)
        index_path = root / "questions-index.json"
        records_path = root / "questions.jsonl"
        if index_path.is_file() and records_path.is_file():
            index = json.loads(index_path.read_text())
            if (index.get("archive_sha256") == fingerprint
                    and index.get("jsonl_bytes") == records_path.stat().st_size):
                return source
        staged = records_path.with_suffix(".jsonl.part")
        checkpoints: list[list[int]] = []
        split_counts: dict[str, int] = {}
        offset = 0
        count = 0
        try:
            with self._open_archive() as archive:
                question_members, prefix = self._members(archive)
                with staged.open("wb") as output:
                    for split in self.SPLITS:
                        split_counts[split] = 0
                        with archive.open(question_members[split]) as raw:
                            with io.TextIOWrapper(raw, encoding="utf-8") as text:
                                for row in _questions(text):
                                    if count % 1000 == 0:
                                        checkpoints.append([count, offset])
                                    row["split"] = split
                                    line = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                                    source.charge(len(line))
                                    output.write(line)
                                    offset += len(line)
                                    count += 1
                                    split_counts[split] += 1
            staged.replace(records_path)
            index = {"archive_sha256": fingerprint, "jsonl_bytes": offset,
                     "total": count, "split_counts": split_counts,
                     "checkpoints": checkpoints, "zip_prefix": prefix}
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        finally:
            staged.unlink(missing_ok=True)
        return source

    def _open_archive(self):
        """The official ZIP, local or by ranges, as a context manager that also closes the range reader."""
        import contextlib
        remote = self._remote()
        if remote is None:
            return zipfile.ZipFile(self._archive())
        from dataset_atlas.storage.ranges import SmallReadBuffer
        stack = contextlib.ExitStack()
        reader = stack.enter_context(remote.reader(self.config.get("remote_metadata_bytes", 400_000_000)))
        # The three question files stream sequentially, so read large blocks instead of one round trip per 64 KB.
        archive = stack.enter_context(zipfile.ZipFile(SmallReadBuffer(reader, block_bytes=1 << 20)))
        archive._atlas_stack = stack  # closed with the archive
        original_close = archive.close
        archive.close = lambda: (original_close(), stack.close())
        return archive

    def _index(self) -> dict:
        return json.loads((self._prepared() / "questions-index.json").read_text())

    def _record(self, row: dict) -> Record:
        split = row["split"]
        index = row["question_index"]
        filename = row["image_filename"]
        if split not in self.SPLITS or not re.fullmatch(r"CLEVR_(train|val|test)_\d{6}\.png", filename):
            raise ValueError("invalid CLEVR source image filename")
        key = f"{split}:{index}"
        asset_ref = f"images/{split}/{filename}"
        aid = stable_id(self.dataset.id, self.revision, "asset", asset_ref)
        rid = stable_id(self.dataset.id, self.revision, "example", key)
        asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                      modality="image", uri=asset_ref,
                      metadata={"source_split": split, "source_image_filename": filename})
        return Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                      snapshot_id=self.dataset.snapshot_id, question=row.get("question"),
                      asset_ids=[aid], assets=[asset], source=row)

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        index = self._index()
        total = index["total"]
        start = int(cursor or 0)
        if not 0 <= start <= total:
            raise ValueError("CLEVR cursor outside release")
        size = min(limit or source.limit, source.limit, total - start)
        checkpoint = max((item for item in index["checkpoints"] if item[0] <= start),
                         default=[0, 0], key=lambda item: item[0])
        rows: list[Record] = []
        with (self._prepared() / "questions.jsonl").open("rb") as handle:
            handle.seek(checkpoint[1])
            for _ in range(start - checkpoint[0]):
                handle.readline()
            for _ in range(size):
                line = handle.readline()
                if not line:
                    raise ValueError("truncated CLEVR question index")
                source.charge(len(line))
                rows.append(self._record(json.loads(line)))
        end = start + len(rows)
        return RecordBatch(rows, str(end) if end < total else None, len(rows))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        match = re.fullmatch(r"images/(train|val|test)/CLEVR_(train|val|test)_\d{6}\.png", asset_ref)
        if not match or match.group(1) != match.group(2):
            raise ValueError("invalid CLEVR asset reference")
        prefix = self._index()["zip_prefix"]
        member = prefix + asset_ref
        if self._remote():
            data = self._remote().read(member, source.max_bytes - source.bytes_read, self.config.get("media_transfer_bytes", 40_000_000))
        else:
            from dataset_atlas.storage.zip_members import LOCAL_ZIP_MEMBERS
            data = LOCAL_ZIP_MEMBERS.read(self._archive(), member, source.max_bytes - source.bytes_read,
                                          self.config['archive_sha256'])
        source.charge(len(data))
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("CLEVR image member is not PNG")
        return MediaHandle(data, "image/png", hashlib.sha256(data).hexdigest(), asset_ref)
