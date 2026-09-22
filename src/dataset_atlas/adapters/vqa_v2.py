"""VQA v2 validation questions and ten-answer annotations on COCO 2014 images."""
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
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class VQAv2Adapter(DatasetAdapter):
    """Original 2017 v2.0 validation annotation overlay, not COCO 2017."""

    QUESTION_MEMBER = "v2_OpenEnded_mscoco_val2014_questions.json"
    ANNOTATION_MEMBER = "v2_mscoco_val2014_annotations.json"
    IMAGE_RE = re.compile(r"val2014/COCO_val2014_\d{12}\.jpg\Z")

    def _paths(self) -> dict[str, Path]:
        return {key: Path(self.config[f"{key}_archive"]).expanduser().resolve()
                for key in ("questions", "annotations", "images")}

    def _prepared(self) -> Path:
        return Path(self.config["prepared_root"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        paths = self._paths()
        missing = [str(path) for path in paths.values() if not path.is_file()]
        size = sum(path.stat().st_size for path in paths.values() if path.is_file())
        return SourceDescription("vqa_v2_val2014", " + ".join(map(str, paths.values())),
                                 not missing, self.revision, size if not missing else None,
                                 True, True, True, False, True,
                                 tuple(f"missing source archive: {path}" for path in missing))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        if any(not self.config.get(f"{key}_sha256") for key in self._paths()):
            raise ValueError("VQA v2 requires three pinned archive hashes")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit,
                               max_bytes, 0, None,
                               ("verify original archives and strict question/annotation/image join",),
                               "prepared JSONL size is unknown until indexing")

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        paths = self._paths()
        digests = {key: _sha256(path) for key, path in paths.items()}
        if any(digests[key] != self.config[f"{key}_sha256"] for key in paths):
            raise ValueError("VQA v2 archive differs from pinned SHA-256")
        root = self._prepared(); root.mkdir(parents=True, exist_ok=True)
        index_path, rows_path = root / "index.json", root / "records.jsonl"
        if index_path.is_file() and rows_path.is_file():
            old = json.loads(index_path.read_text())
            if old.get("source_sha256") == digests and old.get("jsonl_bytes") == rows_path.stat().st_size:
                return source

        with zipfile.ZipFile(paths["questions"]) as archive:
            raw = archive.read(self.QUESTION_MEMBER)
        source.charge(len(raw))
        questions_doc = json.loads(raw)
        del raw
        with zipfile.ZipFile(paths["annotations"]) as archive:
            raw = archive.read(self.ANNOTATION_MEMBER)
        source.charge(len(raw))
        annotations_doc = json.loads(raw)
        del raw
        if (questions_doc.get("data_subtype") != "val2014"
                or annotations_doc.get("data_subtype") != "val2014"
                or not isinstance(questions_doc.get("questions"), list)
                or not isinstance(annotations_doc.get("annotations"), list)):
            raise ValueError("VQA v2 source archives do not contain val2014 records")
        questions = questions_doc["questions"]
        annotations = annotations_doc["annotations"]
        expected = self.config.get("expected_questions")
        if expected is not None and (len(questions) != expected or len(annotations) != expected):
            raise ValueError("VQA v2 val2014 source count differs from declared release")
        by_question: dict[int, dict] = {}
        for annotation in annotations:
            qid = annotation["question_id"]
            if qid in by_question:
                raise ValueError(f"duplicate VQA annotation question ID {qid}")
            if len(annotation.get("answers", [])) != 10:
                raise ValueError(f"VQA annotation lacks ten answers: {qid}")
            by_question[qid] = annotation
        with zipfile.ZipFile(paths["images"]) as archive:
            images = {name for name in archive.namelist() if self.IMAGE_RE.fullmatch(name)}
        seen_questions: set[int] = set()
        image_ids: set[int] = set()
        checkpoints: list[list[int]] = []
        staged = rows_path.with_suffix(".jsonl.part")
        offset = 0
        try:
            with staged.open("wb") as output:
                for ordinal, question in enumerate(questions):
                    qid, image_id = question["question_id"], question["image_id"]
                    if qid in seen_questions:
                        raise ValueError(f"duplicate VQA question ID {qid}")
                    seen_questions.add(qid)
                    annotation = by_question.get(qid)
                    if annotation is None or annotation["image_id"] != image_id:
                        raise ValueError(f"unmatched VQA question/annotation: {qid}")
                    filename = f"COCO_val2014_{image_id:012d}.jpg"
                    if f"val2014/{filename}" not in images:
                        raise ValueError(f"VQA question has no COCO 2014 image: {qid}")
                    image_ids.add(image_id)
                    row = {"question_id": qid, "image_id": image_id,
                           "question": question["question"],
                           "question_type": annotation["question_type"],
                           "answer_type": annotation["answer_type"],
                           "multiple_choice_answer": annotation["multiple_choice_answer"],
                           "answers": annotation["answers"],
                           "image_filename": filename, "split": "val2014"}
                    if ordinal % 1000 == 0:
                        checkpoints.append([ordinal, offset])
                    line = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
                    source.charge(len(line))
                    output.write(line)
                    offset += len(line)
            if seen_questions != set(by_question):
                raise ValueError("VQA annotations include unmatched question IDs")
            staged.replace(rows_path)
            index = {"source_sha256": digests, "jsonl_bytes": offset,
                     "total": len(questions), "unique_image_count": len(image_ids),
                     "available_image_count": len(images), "checkpoints": checkpoints,
                     "join_report": {"duplicate_question_ids": 0,
                                     "duplicate_annotation_ids": 0,
                                     "unmatched_questions": 0, "unmatched_annotations": 0,
                                     "missing_images": 0}}
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        finally:
            staged.unlink(missing_ok=True)
        return source

    def _index(self) -> dict:
        return json.loads((self._prepared() / "index.json").read_text())

    def _record(self, row: dict) -> Record:
        qid, image_id = row["question_id"], row["image_id"]
        asset_ref = f"val2014/{row['image_filename']}"
        rid = stable_id(self.dataset.id, self.revision, "example", str(qid))
        aid = stable_id(self.dataset.id, self.revision, "asset", str(image_id))
        asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                      modality="image", uri=asset_ref,
                      metadata={"coco_split": "val2014", "coco_image_id": image_id})
        return Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                      snapshot_id=self.dataset.snapshot_id, question=row["question"],
                      asset_ids=[aid], assets=[asset], source=row)

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        index = self._index()
        total = index["total"]
        start = int(cursor or 0)
        if not 0 <= start <= total:
            raise ValueError("VQA v2 cursor outside validation release")
        size = min(limit or source.limit, source.limit, total - start)
        checkpoint = max((item for item in index["checkpoints"] if item[0] <= start),
                         default=[0, 0], key=lambda item: item[0])
        rows = []
        with (self._prepared() / "records.jsonl").open("rb") as handle:
            handle.seek(checkpoint[1])
            for _ in range(start - checkpoint[0]):
                handle.readline()
            for _ in range(size):
                line = handle.readline()
                if not line:
                    raise ValueError("truncated VQA v2 index")
                source.charge(len(line))
                rows.append(self._record(json.loads(line)))
        end = start + len(rows)
        return RecordBatch(rows, str(end) if end < total else None, len(rows))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        if not self.IMAGE_RE.fullmatch(asset_ref):
            raise ValueError("invalid VQA v2 COCO 2014 image reference")
        with zipfile.ZipFile(self._paths()["images"]) as archive:
            info = archive.getinfo(asset_ref)
            if info.file_size > source.max_bytes - source.bytes_read:
                raise ValueError("VQA v2 image exceeds remaining byte budget")
            data = archive.read(info)
        source.charge(len(data))
        if not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("VQA v2 image member is not JPEG")
        return MediaHandle(data, "image/jpeg", hashlib.sha256(data).hexdigest(), asset_ref)
