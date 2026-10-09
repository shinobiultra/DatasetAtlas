"""Passive inspection of the native FIND function benchmark; never execute code."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile
from dataset_atlas.models import Asset, Record, stable_id
from dataset_atlas.storage.zip_members import LOCAL_ZIP_MEMBERS
from .core import (
    DatasetAdapter,
    SourceDescription,
    RecordBatch,
    MediaHandle,
    _safe_relative,
)

GROUPS = ("strings", "numeric", "neurons_entities", "neurons_relations")


class FindAdapter(DatasetAdapter):
    def probe(self):
        path = Path(self.config["path"])
        return SourceDescription(
            "find_archive",
            str(path),
            path.is_file(),
            self.revision,
            path.stat().st_size if path.is_file() else None,
            False,
            True,
            True,
            True,
            False,
            (
                "Native Python functions and model bytes are inspected as data; no code execution or deserialization.",
            ),
        )

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        with Path(self.config["path"]).open("rb") as stream:
            if (
                hashlib.file_digest(stream, "sha256").hexdigest()
                != self.config["sha256"]
            ):
                raise ValueError("FIND source archive checksum changed")
        self._rows()
        return source

    def _rows(self):
        if hasattr(self, "_native_rows"):
            return self._native_rows
        rows = []
        consumed = 0
        used = set()
        with zipfile.ZipFile(self.config["path"]) as archive:
            entries = [item for item in archive.infolist() if not item.is_dir()]
            names = {_safe_relative(item.filename): item for item in entries}
            if len(names) != len(entries):
                raise ValueError("Duplicate FIND archive member")

            def read(name):
                nonlocal consumed
                info = names[name]
                consumed += info.file_size
                if consumed > self.config.get("max_annotation_bytes", 20_000_000):
                    raise ValueError("FIND native files exceed decoded read budget")
                used.add(name)
                return archive.read(info)

            groups = self.config.get("groups", GROUPS)
            if (
                not groups
                or len(groups) != len(set(groups))
                or set(groups) - set(GROUPS)
            ):
                raise ValueError("Unknown FIND groups")
            for group in groups:
                prefix = "find_dataset/" + group + "/"
                definitions = json.loads(read(prefix + "data.json"))
                seen = set()
                tables = {}
                for table in ("unit_test_data", "test_data", "func_name_dict"):
                    name = prefix + table + ".json"
                    if name not in names:
                        continue
                    data = json.loads(read(name))
                    if table == "func_name_dict":
                        if not isinstance(data, dict):
                            raise ValueError("FIND filename inventory must be keyed")
                        tables[table] = data
                    else:
                        if not isinstance(data, list):
                            raise ValueError("FIND auxiliary table must be a list")
                        lookup = {}
                        for item in data:
                            if item["name"] in lookup:
                                raise ValueError("Duplicate FIND auxiliary identity")
                            lookup[item["name"]] = item
                        tables[table] = lookup
                if not isinstance(definitions, list):
                    raise ValueError("FIND definitions must be a list")
                for definition in definitions:
                    identity = PurePosixPath(definition["dir"]).name
                    if not re.fullmatch(r"f\d{5}", identity) or identity in seen:
                        raise ValueError("Duplicate or invalid FIND function identity")
                    seen.add(identity)
                    directory = prefix + identity + "/"
                    code_name = directory + "function_code.py"
                    payloads = {code_name: read(code_name)}
                    code = payloads[code_name].decode("utf-8")
                    supplements = {}
                    files = [code_name]
                    for table, lookup in tables.items():
                        if identity not in lookup:
                            raise ValueError("Missing FIND auxiliary function join")
                        supplements[table] = lookup[identity]
                    initial = directory + "initial.json"
                    if initial in names:
                        supplements["initial_file"] = json.loads(read(initial))
                    weights = directory + "mlp_approx_model.pt"
                    if weights in names:
                        # Hash bytes only; torch.load and pickle are never used.
                        payloads[weights] = read(weights)
                        files.append(weights)
                    native_files = []
                    for name in files:
                        payload = payloads[name]
                        native_files.append(
                            {
                                "member": name,
                                "bytes": len(payload),
                                "sha256": hashlib.sha256(payload).hexdigest(),
                            }
                        )
                    rows.append(
                        {
                            "group": group,
                            "function_id": identity,
                            "definition": definition,
                            "supplements": supplements,
                            "function_code": code,
                            "native_files": native_files,
                            "execution_status": "not_executed",
                            "origin": {
                                "archive": "FIND-dataset.zip",
                                "definition_member": prefix + "data.json",
                                "directory": directory,
                            },
                        }
                    )
                for lookup in tables.values():
                    if set(lookup) != seen:
                        raise ValueError("Orphaned FIND auxiliary function identities")
            unexpected = set(names) - used
            if unexpected:
                raise ValueError(
                    f"Unaccounted FIND archive members: {sorted(unexpected)[:3]}"
                )
        self._native_rows = rows
        return rows

    @property
    def count(self):
        return len(self._rows())

    def iter_records(self, source, cursor=None, limit=None):
        start = int(cursor or 0)
        if start < 0:
            raise ValueError("Negative FIND cursor")
        rows = self._rows()
        end = min(start + min(limit or source.limit, source.limit), len(rows))
        records = []
        for row in rows[start:end]:
            identity = row["group"] + "/" + row["function_id"]
            assets = []
            for item in row["native_files"]:
                code = item["member"].endswith(".py")
                assets.append(
                    Asset(
                        id=stable_id(
                            self.dataset.id, self.revision, "asset", item["member"]
                        ),
                        dataset_id=self.dataset.id,
                        release_id=self.revision,
                        modality="text" if code else "array",
                        uri=item["member"],
                        sha256=item["sha256"],
                        metadata={
                            "role": "native function source"
                            if code
                            else "native serialized approximation weights",
                            "encoding": "UTF-8 Python source, not executed"
                            if code
                            else "PyTorch bytes, not deserialized",
                        },
                    )
                )
            record = Record(
                id=stable_id(self.dataset.id, self.revision, "example", identity),
                dataset_id=self.dataset.id,
                release_id=self.revision,
                snapshot_id=self.dataset.snapshot_id,
                text=row["function_code"],
                source=row,
                assets=assets,
                asset_ids=[asset.id for asset in assets],
            )
            source.charge(len(record.model_dump_json().encode()))
            records.append(record)
        return RecordBatch(records, str(end) if end < len(rows) else None, len(records))

    def resolve_asset(self, source, asset_ref):
        name = _safe_relative(asset_ref)
        allowed = {
            item["member"]: item for row in self._rows() for item in row["native_files"]
        }
        if name not in allowed:
            raise ValueError("FIND member is not a registered sample asset")
        data = LOCAL_ZIP_MEMBERS.read(
            Path(self.config["path"]),
            name,
            source.max_bytes - source.bytes_read,
            self.config["sha256"],
        )
        sha = hashlib.sha256(data).hexdigest()
        if sha != allowed[name]["sha256"]:
            raise ValueError("FIND native asset checksum changed")
        source.charge(len(data))
        return MediaHandle(
            data,
            "text/plain; charset=utf-8"
            if name.endswith(".py")
            else "application/octet-stream",
            sha,
            name,
        )
