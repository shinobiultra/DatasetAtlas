"""Original IconQA three-subtask ZIP with exact question and media joins."""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile

from PIL import Image

from dataset_atlas.models import Asset, Record, stable_id

from .core import DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource, RecordBatch, SourceDescription


_DATA = re.compile(r"iconqa_data/iconqa/(train|val|test)/(choose_img|choose_txt|fill_in_blank)/([0-9]+)/data\.json\Z")
_MEDIA = re.compile(r"iconqa_data/iconqa/(train|val|test)/(choose_img|choose_txt|fill_in_blank)/([0-9]+)/(?:image|choice_[0-9]+)\.png\Z")
_CHOICE = re.compile(r"choice_[0-9]+\.png\Z")
_MAX_ZIP_BYTES = 2_000_000_000
_MAX_UNCOMPRESSED_BYTES = 3_000_000_000
_MAX_IMAGE_BYTES = 10_000_000
_MAX_JSON_BYTES = 100_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class IconQAAdapter(DatasetAdapter):
    """One source data.json per example; diagram and choices remain original PNGs."""

    def _archive(self) -> Path:
        return Path(self.config["archive"]).expanduser().resolve()

    def _prepared(self) -> Path:
        return Path(self.config["prepared_root"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        archive = self._archive()
        exists = archive.is_file()
        return SourceDescription(
            "iconqa_original_zip", str(archive), exists, self.revision,
            archive.stat().st_size if exists else None,
            True, True, True, False, True,
            ("All three original question types; PNGs read individually from the author ZIP",),
        )

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        if not re.fullmatch(r"[0-9a-f]{64}", self.config.get("archive_sha256", "")):
            raise ValueError("IconQA requires a pinned archive SHA-256")
        if self._archive().stat().st_size > _MAX_ZIP_BYTES or self._archive().stat().st_size > max_bytes:
            raise ValueError("IconQA ZIP exceeds approved source byte budget")
        return PreparationPlan(
            self.dataset.id, self.revision, cursor, limit, max_bytes, 0,
            200_000_000,
            ("verify author ZIP and every question/diagram/choice reference",),
            "ZIP entries are bounded to 3 GB uncompressed; index size is measured during preparation",
        )

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        archive_path = self._archive()
        archive_hash = _sha256(archive_path)
        if archive_hash != self.config["archive_sha256"]:
            raise ValueError("IconQA archive differs from pinned SHA-256")
        prepared = self._prepared()
        prepared.mkdir(parents=True, exist_ok=True)
        rows_path, index_path = prepared / "rows.jsonl", prepared / "index.json"
        if rows_path.is_file() and index_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if (index.get("archive_sha256") == archive_hash
                    and index.get("row_count") == self.config.get("expected_records")
                    and index.get("rows_bytes") == rows_path.stat().st_size
                    and index.get("rows_sha256") == _sha256(rows_path)):
                return source
            raise ValueError("IconQA prepared index differs from pinned ZIP")

        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) != len({info.filename for info in infos}):
                raise ValueError("IconQA ZIP has duplicate member names")
            total = sum(info.file_size for info in infos)
            if total > _MAX_UNCOMPRESSED_BYTES:
                raise ValueError("IconQA ZIP exceeds uncompressed byte budget")
            for info in infos:
                name = info.filename
                if (name.startswith("/") or "\\" in name or "\x00" in name
                        or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))):
                    raise ValueError(f"IconQA ZIP has unsafe member path: {name!r}")
                mode = stat.S_IFMT(info.external_attr >> 16)
                if mode not in {0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG}:
                    raise ValueError(f"IconQA ZIP has non-regular member: {name!r}")
            media = {info.filename: info for info in infos if info.filename.endswith(".png")}
            data_names = sorted(info.filename for info in infos if _DATA.fullmatch(info.filename))
            if len(data_names) != self.config.get("expected_records"):
                raise ValueError("IconQA question count differs from pinned release")
            source_metadata = json.loads(archive.read("iconqa_data/metadata.json"))
            license_text = archive.read("iconqa_data/LICENSE.md").decode("utf-8")
            if source_metadata.get("version") != "v1" or source_metadata.get("license") != "CC BY-NC-SA 4.0":
                raise ValueError("IconQA author metadata differs from pinned release")
            if "Creative Commons Attribution-NonCommercial-ShareAlike 4.0" not in license_text:
                raise ValueError("IconQA archive license differs from author declaration")
            counts: Counter[str] = Counter()
            referenced_media: set[str] = set()
            checkpoints: list[list[int]] = []
            offset = 0
            digest = hashlib.sha256()
            staged = rows_path.with_suffix(".jsonl.part")
            try:
                with staged.open("wb") as output:
                    for ordinal, member_name in enumerate(data_names):
                        match = _DATA.fullmatch(member_name)
                        assert match is not None
                        split, task, problem_id = match.groups()
                        info = archive.getinfo(member_name)
                        if info.file_size > _MAX_JSON_BYTES:
                            raise ValueError("IconQA question JSON exceeds per-row byte cap")
                        raw = archive.read(info)
                        if len(raw) != info.file_size:
                            raise ValueError("IconQA question JSON is truncated")
                        data = json.loads(raw)
                        if (not isinstance(data, dict) or data.get("ques_type") != task
                                or not isinstance(data.get("question"), str) or not data["question"]
                                or not isinstance(data.get("grade"), str)
                                or not isinstance(data.get("label"), str)):
                            raise ValueError(f"IconQA question schema differs: {member_name}")
                        prefix = member_name[:-len("data.json")]
                        refs = [prefix + "image.png"]
                        if task == "fill_in_blank":
                            if not isinstance(data.get("answer"), str) or not data["answer"]:
                                raise ValueError("IconQA blank answer is missing")
                        else:
                            choices, answer = data.get("choices"), data.get("answer")
                            if not isinstance(choices, list) or not choices or type(answer) is not int or not 0 <= answer < len(choices):
                                raise ValueError("IconQA choices or answer index are invalid")
                            if task == "choose_img":
                                if any(not isinstance(value, str) or not _CHOICE.fullmatch(value) for value in choices):
                                    raise ValueError("IconQA image choice reference is invalid")
                                refs.extend(prefix + value for value in choices)
                            elif any(not isinstance(value, str) for value in choices):
                                raise ValueError("IconQA text choice is invalid")
                        if len(refs) != len(set(refs)):
                            raise ValueError("IconQA question repeats an image choice")
                        for ref in refs:
                            image_info = media.get(ref)
                            if image_info is None or not 0 < image_info.file_size <= _MAX_IMAGE_BYTES:
                                raise ValueError(f"IconQA image is absent or oversized: {ref}")
                            if ref in referenced_media:
                                raise ValueError(f"IconQA image has multiple source owners: {ref}")
                            referenced_media.add(ref)
                        row = {"source_json_member": member_name, "split": split,
                               "subtask": task, "problem_id": problem_id,
                               "data": data, "media_refs": refs}
                        line = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                        source.charge(len(line))
                        if ordinal % 1000 == 0:
                            checkpoints.append([ordinal, offset])
                        output.write(line)
                        digest.update(line)
                        offset += len(line)
                        counts[f"{split}:{task}"] += 1
                if set(media) != referenced_media:
                    raise ValueError("IconQA archive has unreferenced PNGs")
                expected = self.config.get("expected_counts", {})
                if dict(counts) != expected:
                    raise ValueError("IconQA subtask/split counts differ from pinned archive")
                staged.replace(rows_path)
                index = {"archive_sha256": archive_hash, "row_count": len(data_names),
                         "rows_bytes": offset, "rows_sha256": digest.hexdigest(),
                         "zip_member_count": len(infos), "png_count": len(media),
                         "uncompressed_bytes": total, "counts": dict(counts),
                         "author_metadata": source_metadata, "license_text": license_text,
                         "checkpoints": checkpoints}
                staged_index = index_path.with_suffix(".json.part")
                staged_index.write_text(json.dumps(index, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                staged_index.replace(index_path)
            finally:
                staged.unlink(missing_ok=True)
        return source

    def _index(self) -> dict:
        return json.loads((self._prepared() / "index.json").read_text(encoding="utf-8"))

    def _record(self, row: dict) -> Record:
        split, task, problem_id = row["split"], row["subtask"], row["problem_id"]
        source_id = f"{split}/{task}/{problem_id}"
        rid = stable_id(self.dataset.id, self.revision, "example", source_id)
        assets: list[Asset] = []
        for index, ref in enumerate(row["media_refs"]):
            aid = stable_id(self.dataset.id, self.revision, "asset", ref)
            assets.append(Asset(
                id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                modality="image", uri=ref,
                metadata={"role": "diagram" if index == 0 else "image_choice",
                          "choice_index": index - 1 if index else None,
                          "source_problem_id": problem_id},
            ))
        data = row["data"]
        return Record(
            id=rid, dataset_id=self.dataset.id, release_id=self.revision,
            snapshot_id=self.dataset.snapshot_id, unit="example",
            asset_ids=[asset.id for asset in assets], assets=assets,
            question=data["question"], choices=data.get("choices", []),
            source={**data, "split": split, "subtask": task, "problem_id": problem_id,
                    "source_json_member": row["source_json_member"],
                    "diagram_member": row["media_refs"][0],
                    "choice_image_members": row["media_refs"][1:]},
        )

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        index = self._index()
        total = index["row_count"]
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("invalid IconQA cursor") from exc
        if not 0 <= start <= total:
            raise ValueError("IconQA cursor outside release")
        size = min(limit or source.limit, source.limit, total - start)
        checkpoint = max((item for item in index["checkpoints"] if item[0] <= start),
                         default=[0, 0], key=lambda item: item[0])
        records: list[Record] = []
        with (self._prepared() / "rows.jsonl").open("rb") as stream:
            stream.seek(checkpoint[1])
            for _ in range(start - checkpoint[0]):
                stream.readline()
            for _ in range(size):
                line = stream.readline()
                if not line:
                    raise ValueError("IconQA prepared index is truncated")
                source.charge(len(line))
                records.append(self._record(json.loads(line)))
        end = start + len(records)
        return RecordBatch(records, str(end) if end < total else None, len(records))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        if not _MEDIA.fullmatch(asset_ref):
            raise ValueError("invalid IconQA media reference")
        # This ZIP has 472,932 entries; parsing its central directory for each
        # of hundreds of preview assets would turn selective reads into minutes.
        archive = getattr(self, "_media_archive", None)
        if archive is None:
            archive = zipfile.ZipFile(self._archive())
            self._media_archive = archive
        info = archive.getinfo(asset_ref)
        remaining = source.max_bytes - source.bytes_read
        if info.file_size > _MAX_IMAGE_BYTES or info.file_size > remaining:
            raise ValueError("IconQA media exceeds remaining byte budget")
        with archive.open(info) as stream:
            data = stream.read(info.file_size + 1)
        if len(data) != info.file_size or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("IconQA media is not an intact PNG")
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 50_000_000:
                raise ValueError("IconQA image exceeds pixel budget")
            image.verify()
        source.charge(len(data))
        return MediaHandle(data, "image/png", hashlib.sha256(data).hexdigest(), asset_ref)

    def __del__(self) -> None:
        archive = getattr(self, "_media_archive", None)
        if archive is not None:
            archive.close()
