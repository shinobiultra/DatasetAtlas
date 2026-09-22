"""Pinned GQA v1.2 validation-balanced questions with original images."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile

from dataset_atlas.models import Asset, Record, stable_id

from .core import (DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource,
                   RecordBatch, SourceDescription)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GQABalancedAdapter(DatasetAdapter):
    """The exact official val_balanced split, with a strict image-ID join."""

    QUESTION_MEMBER = "val_balanced_questions.json"
    IMAGE_RE = re.compile(r"images/(?P<image_id>[0-9]+)\.jpg\Z")

    def _paths(self) -> tuple[Path, Path]:
        return (Path(self.config["questions_archive"]).expanduser().resolve(),
                Path(self.config["images_archive"]).expanduser().resolve())

    def _prepared(self) -> Path:
        return Path(self.config["prepared_root"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        questions, images = self._paths()
        missing = [str(path) for path in (questions, images) if not path.is_file()]
        size = sum(path.stat().st_size for path in (questions, images) if path.is_file())
        return SourceDescription("gqa_v1_2_val_balanced", f"{questions} + {images}",
                                 not missing, self.revision, size if not missing else None,
                                 True, True, True, False, True,
                                 tuple(f"missing source archive: {path}" for path in missing))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        if not self.config.get("questions_sha256") or not self.config.get("images_sha256"):
            raise ValueError("GQA requires pinned question and image archive hashes")
        requirement = ("verify source questions and explicitly mark images outside the selected local preview"
                       if self.config.get("media_scope") == "selected_preview"
                       else "verify both official archives and join every validation image ID")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit,
                               max_bytes, 0, None,
                               (requirement,),
                               "prepared JSONL size is unknown before conversion")

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        partial_media = self.config.get("media_scope") == "selected_preview"
        if self.config.get("media_scope", "full") not in ("full", "selected_preview"):
            raise ValueError("unknown GQA media scope")
        questions, images = self._paths()
        digests = {"questions": _sha256(questions), "images": _sha256(images)}
        if (digests["questions"] != self.config["questions_sha256"]
                or digests["images"] != self.config["images_sha256"]):
            raise ValueError("GQA archive differs from pinned SHA-256")
        root = self._prepared()
        root.mkdir(parents=True, exist_ok=True)
        index_path, rows_path = root / "index.json", root / "records.jsonl"
        if index_path.is_file() and rows_path.is_file():
            old = json.loads(index_path.read_text())
            if old.get("source_sha256") == digests and old.get("jsonl_bytes") == rows_path.stat().st_size:
                return source

        with zipfile.ZipFile(questions) as archive:
            raw = archive.read(self.QUESTION_MEMBER)
        source.charge(len(raw))
        questions_doc = json.loads(raw)
        del raw
        if not isinstance(questions_doc, dict):
            raise ValueError("GQA validation questions must be keyed by question ID")
        expected = self.config.get("expected_questions")
        if expected is not None and len(questions_doc) != int(expected):
            raise ValueError("GQA validation-balanced source count differs from declared release")
        with zipfile.ZipFile(images) as archive:
            names = archive.namelist()
        image_ids: set[str] = set()
        for name in names:
            match = self.IMAGE_RE.fullmatch(name)
            if not match:
                continue
            image_id = match.group("image_id")
            if image_id in image_ids:
                raise ValueError(f"duplicate GQA image ID {image_id}")
            image_ids.add(image_id)

        referenced_images: set[str] = set()
        unavailable_images: set[str] = set()
        checkpoints: list[list[int]] = []
        staged = rows_path.with_suffix(".jsonl.part")
        offset = 0
        try:
            with staged.open("wb") as output:
                for ordinal, (question_id, original) in enumerate(questions_doc.items()):
                    if not isinstance(original, dict):
                        raise ValueError(f"GQA question {question_id} is not an object")
                    if original.get("isBalanced") is not True:
                        raise ValueError(f"GQA val-balanced question {question_id} is not marked balanced")
                    image_id = original.get("imageId")
                    if not isinstance(image_id, str):
                        raise ValueError(f"GQA question {question_id} has no image ID")
                    if image_id not in image_ids:
                        if not partial_media:
                            raise ValueError(f"GQA question {question_id} has no original image")
                        unavailable_images.add(image_id)
                    if not isinstance(original.get("question"), str) or not isinstance(original.get("answer"), str):
                        raise ValueError(f"GQA question {question_id} lacks text or answer")
                    referenced_images.add(image_id)
                    types = original.get("types") or {}
                    groups = original.get("groups") or {}
                    row = {"question_id": question_id, **original, "split": "val_balanced",
                           "image_filename": f"{image_id}.jpg",
                           "media_available": image_id in image_ids,
                           "structural_type": types.get("structural"),
                           "semantic_type": types.get("semantic"),
                           "detailed_type": types.get("detailed"),
                           "global_group": groups.get("global"),
                           "local_group": groups.get("local")}
                    if ordinal % 1000 == 0:
                        checkpoints.append([ordinal, offset])
                    line = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
                    source.charge(len(line))
                    output.write(line)
                    offset += len(line)
            available_referenced = referenced_images - unavailable_images
            if partial_media and len(available_referenced) < int(self.config.get("minimum_available_images", 100)):
                raise ValueError("GQA selected preview has fewer original images than required")
            staged.replace(rows_path)
            index = {"source_sha256": digests, "jsonl_bytes": offset,
                     "total": len(questions_doc), "available_image_count": len(image_ids),
                     "referenced_image_count": len(referenced_images),
                     "available_referenced_image_count": len(available_referenced),
                     "media_scope": self.config.get("media_scope", "full"),
                     "checkpoints": checkpoints,
                     "join_report": {"duplicate_question_ids": 0, "duplicate_image_ids": 0,
                                     "missing_images": len(unavailable_images)}}
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        finally:
            staged.unlink(missing_ok=True)
        return source

    def _index(self) -> dict:
        return json.loads((self._prepared() / "index.json").read_text())

    def _record(self, row: dict) -> Record:
        question_id, image_id = row["question_id"], row["imageId"]
        asset_ref = f"images/{row['image_filename']}"
        rid = stable_id(self.dataset.id, self.revision, "example", question_id)
        aid = stable_id(self.dataset.id, self.revision, "asset", image_id)
        assets = ([Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                         modality="image", uri=asset_ref,
                         metadata={"gqa_image_id": image_id, "source_split": "val_balanced"})]
                  if row["media_available"] else [])
        return Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                      snapshot_id=self.dataset.snapshot_id, question=row["question"],
                      asset_ids=[aid] if assets else [], assets=assets, source=row)

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        index = self._index()
        total = index["total"]
        start = int(cursor or 0)
        if not 0 <= start <= total:
            raise ValueError("GQA cursor outside validation-balanced release")
        size = min(limit or source.limit, source.limit, total - start)
        checkpoint = max((item for item in index["checkpoints"] if item[0] <= start),
                         default=[0, 0], key=lambda item: item[0])
        rows = []
        with (self._prepared() / "records.jsonl").open("rb") as stream:
            stream.seek(checkpoint[1])
            for _ in range(start - checkpoint[0]):
                stream.readline()
            for _ in range(size):
                line = stream.readline()
                if not line:
                    raise ValueError("truncated GQA prepared index")
                source.charge(len(line))
                rows.append(self._record(json.loads(line)))
        end = start + len(rows)
        return RecordBatch(rows, str(end) if end < total else None, len(rows))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        if not self.IMAGE_RE.fullmatch(asset_ref):
            raise ValueError("invalid GQA image reference")
        with zipfile.ZipFile(self._paths()[1]) as archive:
            info = archive.getinfo(asset_ref)
            if info.file_size > source.max_bytes - source.bytes_read:
                raise ValueError("GQA image exceeds remaining byte budget")
            data = archive.read(info)
        source.charge(len(data))
        if not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("GQA image member is not JPEG")
        return MediaHandle(data, "image/jpeg", hashlib.sha256(data).hexdigest(), asset_ref)
