"""COCO 2017 validation captions and instances from the original archives.

The only prepared copy is a paginated JSONL index. Original JPEGs stay in the
official ZIP and are read individually for the local workbench media endpoint.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import zipfile

from dataset_atlas.models import Annotation, Asset, Record, Relation, stable_id

from .core import (DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource,
                   RecordBatch, SourceDescription)


_IMAGE_REF = re.compile(r"val2017/\d{12}\.jpg\Z")
_CAPTIONS_MEMBER = "annotations/captions_val2017.json"
_INSTANCES_MEMBER = "annotations/instances_val2017.json"
_MAX_ANNOTATION_MEMBER_BYTES = 100_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CocoAdapter(DatasetAdapter):
    """One example per original caption, sharing source image and box identities."""

    def _images_archive(self) -> Path:
        return Path(self.config["images_archive"]).expanduser().resolve()

    def _annotations_archive(self) -> Path:
        return Path(self.config["annotations_archive"]).expanduser().resolve()

    def _prepared(self) -> Path:
        return Path(self.config["prepared_root"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        images, annotations = self._images_archive(), self._annotations_archive()
        exists = images.is_file() and annotations.is_file()
        size = images.stat().st_size + annotations.stat().st_size if exists else None
        return SourceDescription(
            "coco_val2017", str(images), exists, self.revision, size,
            True, True, True, False, True,
            ("captions and instances for 2017 validation; images retrieved from ZIP",),
        )

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        if not self.config.get("images_sha256") or not self.config.get("annotations_sha256"):
            raise ValueError("COCO archives require pinned SHA-256 values")
        if base.expected_download_bytes is None or base.expected_download_bytes > max_bytes:
            raise ValueError("COCO archives exceed approved preparation byte budget")
        return PreparationPlan(self.dataset.id, self.revision, cursor, limit, max_bytes,
                               0, None,
                               ("verify both original ZIPs; index validation captions, images, instances",),
                               "JSONL index size is unknown until preparation")

    @staticmethod
    def _read_member(archive: zipfile.ZipFile, member: str, max_bytes: int) -> dict:
        info = archive.getinfo(member)
        if info.file_size > max_bytes:
            raise ValueError(f"COCO annotation member exceeds budget: {member}")
        with archive.open(info) as handle:
            data = handle.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"COCO annotation member exceeds budget: {member}")
        value = json.loads(data)
        if not isinstance(value, dict) or not isinstance(value.get("images"), list) or not isinstance(value.get("annotations"), list):
            raise ValueError(f"invalid COCO annotation member: {member}")
        return value

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        images_path, annotations_path = self._images_archive(), self._annotations_archive()
        if images_path.stat().st_size + annotations_path.stat().st_size > source.max_bytes:
            raise ValueError("COCO archives exceed approved preparation byte budget")
        image_hash = _sha256(images_path)
        annotation_hash = _sha256(annotations_path)
        if image_hash != self.config["images_sha256"] or annotation_hash != self.config["annotations_sha256"]:
            raise ValueError("COCO archive SHA-256 differs from pinned source snapshot")
        prepared = self._prepared()
        prepared.mkdir(parents=True, exist_ok=True)
        index_path = prepared / "index.json"
        rows_path = prepared / "caption-records.jsonl"
        if index_path.is_file() and rows_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if (index.get("images_sha256") == image_hash
                    and index.get("annotations_sha256") == annotation_hash
                    and index.get("records_bytes") == rows_path.stat().st_size
                    and all(index.get(index_key) == self.config[expected_key]
                            for expected_key, index_key in (("expected_images", "images"),
                                                            ("expected_captions", "total"),
                                                            ("expected_instances", "instances"))
                            if expected_key in self.config)
                    and ("expected_categories" not in self.config
                         or len(index.get("categories", {})) == self.config["expected_categories"])):
                return source

        with zipfile.ZipFile(annotations_path) as archive:
            member_budget = min(source.max_bytes, _MAX_ANNOTATION_MEMBER_BYTES)
            captions = self._read_member(archive, _CAPTIONS_MEMBER, member_budget)
            instances = self._read_member(archive, _INSTANCES_MEMBER, member_budget)
        image_by_id: dict[int, dict] = {}
        for image in captions["images"]:
            iid = image["id"]
            if iid in image_by_id:
                raise ValueError(f"duplicate COCO image ID {iid}")
            if not _IMAGE_REF.fullmatch("val2017/" + image["file_name"]):
                raise ValueError("invalid COCO image file name")
            image_by_id[iid] = image
        if {item["id"] for item in instances["images"]} != set(image_by_id):
            raise ValueError("caption and instance validation image sets differ")
        with zipfile.ZipFile(images_path) as archive:
            image_members = {name for name in archive.namelist() if _IMAGE_REF.fullmatch(name)}
        if image_members != {"val2017/" + image["file_name"] for image in image_by_id.values()}:
            raise ValueError("image ZIP does not match COCO validation annotation image set")
        expected_images = self.config.get("expected_images")
        if expected_images is not None and len(image_by_id) != expected_images:
            raise ValueError("COCO validation image count differs from pinned release")
        category_by_id: dict[int, dict] = {}
        for category in instances["categories"]:
            cid = category["id"]
            if cid in category_by_id:
                raise ValueError(f"duplicate COCO category ID {cid}")
            category_by_id[cid] = category
        instances_by_image: dict[int, list[dict]] = defaultdict(list)
        seen_instances: set[int] = set()
        for annotation in instances["annotations"]:
            aid, iid, cid = annotation["id"], annotation["image_id"], annotation["category_id"]
            if aid in seen_instances or iid not in image_by_id or cid not in category_by_id:
                raise ValueError("duplicate or unmatched COCO instance annotation")
            seen_instances.add(aid)
            instances_by_image[iid].append(annotation)
        captions_by_image: dict[int, list[dict]] = defaultdict(list)
        seen_captions: set[int] = set()
        for caption in captions["annotations"]:
            cid, iid = caption["id"], caption["image_id"]
            if cid in seen_captions or iid not in image_by_id:
                raise ValueError("duplicate or unmatched COCO caption annotation")
            seen_captions.add(cid)
            captions_by_image[iid].append(caption)
        for key, observed in (("expected_captions", len(seen_captions)),
                              ("expected_instances", len(seen_instances)),
                              ("expected_categories", len(category_by_id))):
            expected = self.config.get(key)
            if expected is not None and observed != expected:
                raise ValueError(f"COCO {key} differs from pinned release")

        staged = rows_path.with_suffix(".jsonl.part")
        checkpoints: list[list[int]] = []
        count = 0
        offset = 0
        try:
            with staged.open("wb") as output:
                for iid in sorted(image_by_id):
                    image = image_by_id[iid]
                    image_captions = sorted(captions_by_image[iid], key=lambda item: item["id"])
                    if not image_captions:
                        raise ValueError(f"COCO image {iid} has no captions")
                    image_instances = sorted(instances_by_image[iid], key=lambda item: item["id"])
                    for caption in image_captions:
                        if count % 1000 == 0:
                            checkpoints.append([count, offset])
                        row = {"image": image, "caption": caption,
                               "caption_ids_for_image": [item["id"] for item in image_captions],
                               "instances": image_instances}
                        line = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                        source.charge(len(line))
                        output.write(line)
                        offset += len(line)
                        count += 1
            staged.replace(rows_path)
            index = {
                "images_sha256": image_hash, "annotations_sha256": annotation_hash,
                "records_bytes": offset, "total": count, "images": len(image_by_id),
                "instances": len(seen_instances), "categories": category_by_id,
                "caption_info": captions.get("info", {}), "caption_licenses": captions.get("licenses", []),
                "instance_info": instances.get("info", {}), "instance_licenses": instances.get("licenses", []),
                "checkpoints": checkpoints,
            }
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            staged.unlink(missing_ok=True)
        return source

    def _index(self) -> dict:
        return json.loads((self._prepared() / "index.json").read_text(encoding="utf-8"))

    def _record(self, row: dict, index: dict) -> Record:
        image, caption, instances = row["image"], row["caption"], row["instances"]
        categories = index["categories"]
        ref = "val2017/" + image["file_name"]
        aid = stable_id(self.dataset.id, self.revision, "asset", str(image["id"]))
        rid = stable_id(self.dataset.id, self.revision, "example", str(caption["id"]))
        asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                      modality="image", uri=ref,
                      metadata={"source_image_id": image["id"], "width": image["width"],
                                "height": image["height"], "source_file_name": image["file_name"]})
        used_categories = {str(item["category_id"]): categories[str(item["category_id"])]
                           for item in instances}
        names = sorted({item["name"] for item in used_categories.values()})
        image_license = next((item for item in index["instance_licenses"]
                              if item.get("id") == image.get("license")), None)
        annotations = [
            Annotation(id=stable_id(self.dataset.id, self.revision, "annotation", str(item["id"])),
                       subject_id=aid, subject_unit="asset", field_id="source.instance",
                       value={**item, "category": categories[str(item["category_id"])]},
                       provenance={"source_member": _INSTANCES_MEMBER,
                                   "source_annotation_id": item["id"],
                                   "coordinate_system": "original_pixels_xywh"})
            for item in instances
        ]
        relations = [
            Relation(subject_id=rid,
                     object_id=stable_id(self.dataset.id, self.revision, "example", str(other)),
                     type="same_asset", provenance={"source_image_id": image["id"]})
            for other in row["caption_ids_for_image"] if other != caption["id"]
        ]
        return Record(
            id=rid, dataset_id=self.dataset.id, release_id=self.revision,
            snapshot_id=self.dataset.snapshot_id, unit="example", asset_ids=[aid], assets=[asset],
            text=caption["caption"],
            source={"image": image, "image_license": image_license,
                    "caption": caption, "instances": instances,
                    "categories": list(used_categories.values()),
                    "image_id": image["id"], "caption_id": caption["id"],
                    "category_names": names, "instance_count": len(instances),
                    "person_count": sum(categories[str(item["category_id"])]["name"] == "person"
                                        for item in instances)},
            annotations=annotations, relations=relations,
        )

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        index = self._index()
        total = index["total"]
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("invalid COCO cursor") from exc
        if not 0 <= start <= total:
            raise ValueError("COCO cursor outside release")
        size = min(limit or source.limit, source.limit, total - start)
        if size < 0:
            raise ValueError("invalid COCO batch size")
        checkpoint = max((item for item in index["checkpoints"] if item[0] <= start),
                         default=[0, 0], key=lambda item: item[0])
        records: list[Record] = []
        with (self._prepared() / "caption-records.jsonl").open("rb") as handle:
            handle.seek(checkpoint[1])
            for _ in range(start - checkpoint[0]):
                handle.readline()
            for _ in range(size):
                line = handle.readline()
                if not line:
                    raise ValueError("truncated COCO caption index")
                source.charge(len(line))
                records.append(self._record(json.loads(line), index))
        end = start + len(records)
        return RecordBatch(records, str(end) if end < total else None, len(records))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        if not _IMAGE_REF.fullmatch(asset_ref):
            raise ValueError("invalid COCO validation asset reference")
        with zipfile.ZipFile(self._images_archive()) as archive:
            info = archive.getinfo(asset_ref)
            if info.file_size > source.max_bytes - source.bytes_read:
                raise ValueError("COCO image exceeds remaining media byte budget")
            with archive.open(info) as handle:
                data = handle.read(info.file_size + 1)
        if len(data) != info.file_size or not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("COCO image member is not an intact JPEG")
        source.charge(len(data))
        return MediaHandle(data, "image/jpeg", hashlib.sha256(data).hexdigest(), asset_ref)
