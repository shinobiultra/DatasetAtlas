"""Browse the seven passive original media files in Figshare Test_data v1."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dataset_atlas.models import Asset, Record, stable_id

from .core import DatasetAdapter, MediaHandle, RecordBatch, SourceDescription, _media_type


class FigshareStimuliAdapter(DatasetAdapter):
    def _files(self):
        entries = self.config["media_files"]
        if len(entries) != 7 or len({item["figshare_file_id"] for item in entries}) != 7:
            raise ValueError("Figshare v1 media inventory is incomplete or duplicated")
        for item in entries:
            if item["name"] != Path(item["name"]).name or item["modality"] not in {"image", "video"}:
                raise ValueError("Invalid Figshare media inventory entry")
        return entries

    def probe(self):
        entries = self._files()
        paths = [Path(self.config[item["path_key"]]) for item in entries if item.get("path_key") in self.config]
        exists = len(paths) == len(entries) and all(path.is_file() for path in paths)
        return SourceDescription("figshare_stimuli_v1", str(paths[0]) if paths else "Figshare Test_data v1",
                                 exists, self.revision, sum(item["bytes"] for item in entries),
                                 False, True, True, True, False,
                                 ("Seven original v1 media files; paper test conditions are not inferred from filenames.",))

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        for item in self._files():
            path = Path(self.config[item["path_key"]])
            if path.stat().st_size != item["bytes"]:
                raise ValueError("Figshare media size changed")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                    raise ValueError("Figshare media checksum changed")
        return source

    def iter_records(self, source, cursor=None, limit=None):
        entries = self._files()
        start = int(cursor or 0)
        if start < 0 or start > len(entries):
            raise ValueError("Invalid Figshare cursor")
        end = min(len(entries), start + min(limit or source.limit, source.limit))
        records = []
        for item in entries[start:end]:
            ref = item["name"]
            asset_id = stable_id(self.dataset.id, self.revision, "asset", str(item["figshare_file_id"]))
            asset = Asset(id=asset_id, dataset_id=self.dataset.id, release_id=self.revision,
                          modality=item["modality"], uri=ref, sha256=item["sha256"],
                          metadata={"figshare_file_id": item["figshare_file_id"],
                                    "source_name": ref, "original_bytes": item["bytes"]})
            record = Record(id=stable_id(self.dataset.id, self.revision, "record", str(item["figshare_file_id"])),
                            dataset_id=self.dataset.id, release_id=self.revision,
                            snapshot_id=self.dataset.snapshot_id, unit="asset",
                            asset_ids=[asset_id], assets=[asset],
                            source={"figshare_article_id": 5483680, "figshare_version": 1,
                                    "figshare_file_id": item["figshare_file_id"], "filename": ref,
                                    "modality": item["modality"], "bytes": item["bytes"],
                                    "source_md5": item["md5"]})
            source.charge(len(record.model_dump_json().encode()))
            records.append(record)
        return RecordBatch(records, str(end) if end < len(entries) else None, len(records))

    def resolve_asset(self, source, asset_ref):
        item = next((entry for entry in self._files() if entry["name"] == asset_ref), None)
        if item is None:
            raise ValueError("Asset is absent from pinned Figshare v1 inventory")
        if item["bytes"] > source.max_bytes - source.bytes_read:
            raise ValueError("Figshare media exceeds byte budget")
        path = Path(self.config[item["path_key"]])
        data = path.read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Figshare media checksum changed")
        source.charge(len(data))
        return MediaHandle(data, _media_type(asset_ref), item["sha256"], asset_ref)
