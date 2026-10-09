"""MultiTrust (thu-ml/MultiTrust): one catalogue record per query row of a heterogeneous trustworthiness suite.

The release is five aspect folders (truthfulness, safety, robustness, fairness, privacy) holding query files in six
layouts (JSON arrays, JSON Lines saved under a `.json` name, CSV, JSON objects of lists, JSON objects of objects, plain
text lines) next to image folders. `structured_collection` already supplies the media machinery (a pinned inventory of
original files, a Hub credential, bounded reads, hash checks), but it cannot express this suite for four reasons, which
is why this thin subclass exists:

* it has no per-task constants, so `task` and `aspect` could not be filterable categorical fields;
* an image name is sometimes derived (`images/<category>_<md5 of the prompt>.png`, `<Type lower-cased>/<n>.png`,
  `<Name with underscores>.jpeg`, `<row modulo 14>.png`) and the base templates only substitute fields;
* a query row whose image is absent from the pinned release must stay a visible record with a named absent asset, and
  the base class refuses the whole preparation instead;
* a layout is one JSON object of lists (AdvGLUE, OOD-text, RealToxicityPrompts) or of objects (MM-SafetyBench).

Everything else is inherited: the pinned media inventory, `file/` asset references, hash verification and the Hub
credential profile (resolved at request time, never stored). A task is declared in `adapter_config.tasks`; each names
the pinned query file(s) in `source_files`, their layout and the image templates. Joins are only those the query file
itself carries (`join_basis: key_in_query_row`), a derived key, or an ordinal pairing that the authors' loader
performs. A pairing that only exists at run time (a random pick, `os.listdir` order, a cross product) is not joined.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
from collections import Counter
from pathlib import Path

from PIL import Image

from dataset_atlas.storage import BoundedCache, CacheIdentity, HttpsFetcher

from .core import MediaHandle, SourceDescription, _safe_relative
from .remote_columnar import MediaLimitError
from .structured_collection import StructuredCollectionAdapter

FORMATS = {"json", "jsonl", "csv", "text_lines", "json_groups", "json_keyed"}
FILTERS = {
    "lower": lambda value: value.lower(),
    "md5": lambda value: hashlib.md5(value.encode("utf-8"), usedforsecurity=False).hexdigest(),
    "underscore": lambda value: "_".join(value.split(" ")),
}
RESERVED = {"task", "aspect", "query_file"}
TRANSIENT = ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")


class MultiTrustAdapter(StructuredCollectionAdapter):
    """Query rows of a gated, heterogeneous suite with remote pinned originals."""

    def __init__(self, dataset):
        super().__init__(dataset)
        self.media_bytes_fetched = 0
        self._join_stats: dict | None = None

    # -- source files ------------------------------------------------------------------------------------------------

    def _tasks(self) -> list[dict]:
        tasks = self.config.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise ValueError("MultiTrust requires adapter_config.tasks")
        return tasks

    def _query_files(self, task: dict) -> list[str]:
        names = task.get("query_files") or [task.get("query_file")]
        if not names or any(not isinstance(name, str) or not name for name in names):
            raise ValueError(f"Task {task.get('task')!r} names no query file")
        return [str(name) for name in names]

    def _paths(self) -> dict[str, Path]:
        return {entry["source_name"]: Path(entry["path"]) for entry in self.config.get("source_files", [])}

    def probe(self):
        paths = self._paths()
        needed = {name for task in self._tasks() for name in self._query_files(task)}
        needed |= {task["companion_lines"]["source_name"] for task in self._tasks() if task.get("companion_lines")}
        exists = bool(paths) and needed <= set(paths) and all(path.is_file() for path in paths.values())
        return SourceDescription("multitrust_suite", f"{len(paths)} pinned query files", exists, self.revision,
                                 sum(path.stat().st_size for path in paths.values() if path.is_file()), False, True, True, True, True,
                                 ("Query files are pinned by SHA-256; original images stay remote and are fetched one at a time "
                                  "through the Hub credential profile, checked against a pinned inventory.",))

    # -- rows ----------------------------------------------------------------------------------------------------------

    @staticmethod
    def _items(task: dict, name: str, payload: bytes):
        """(subset, native row) pairs in file order. `subset` is a group key, file stem or None."""
        layout = task.get("format", "json")
        if layout not in FORMATS:
            raise ValueError(f"Unsupported MultiTrust layout {layout!r}")
        text = payload.decode("utf-8-sig")
        stem = Path(name).stem
        multi = bool(task.get("query_files"))
        if layout in {"text_lines"}:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return [(stem if multi else None, {"line": number, "text": line}) for number, line in enumerate(lines, 1)]
        if layout == "csv":
            rows = list(csv.DictReader(io.StringIO(text, newline="")))
            return [(stem if multi else None, dict(row)) for row in rows]
        if layout == "jsonl":
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            rows = json.loads(text)
        if layout in {"json", "jsonl"}:
            if not isinstance(rows, list):
                raise ValueError(f"{name} must hold a list of rows")
            if any(not isinstance(row, dict) for row in rows):
                raise ValueError(f"{name} holds a row that is not an object")
            return [(stem if multi else None, dict(row)) for row in rows]
        if not isinstance(rows, dict):
            raise ValueError(f"{name} must hold one JSON object")
        out = []
        if layout == "json_groups":
            field = task["group_field"]
            wrap = task.get("string_item_field")
            for key, group in rows.items():
                if not isinstance(group, list):
                    raise ValueError(f"{name}: group {key!r} is not a list")
                for item in group:
                    if isinstance(item, str) and wrap:
                        item = {wrap: item}
                    if not isinstance(item, dict):
                        raise ValueError(f"{name}: group {key!r} holds an item that is not an object")
                    if field in item:
                        raise ValueError(f"{name}: group field {field!r} collides with a native field")
                    out.append((key, {**item, field: key}))
            return out
        field = task["key_field"]  # json_keyed
        for key, item in rows.items():
            if not isinstance(item, dict) or field in item:
                raise ValueError(f"{name}: keyed row {key!r} is not an object or collides with {field!r}")
            out.append((key, {field: key, **item}))
        return out

    @staticmethod
    def _expand(template: str, row: dict, variables: dict) -> str:
        def substitute(match):
            name, *filters = match[1].split("|")
            if name in variables:
                value = variables[name]
            else:
                value = row.get(name)
            if value is None or isinstance(value, (dict, list)):
                raise ValueError(f"Image template names {name!r}, which this row does not hold as a scalar")
            value = str(value)
            for item in filters:
                if item not in FILTERS:
                    raise ValueError(f"Unknown image template filter {item!r}")
                value = FILTERS[item](value)
            return value
        return re.sub(r"\{([A-Za-z0-9_ ]+(?:\|[a-z0-9]+)*)\}", substitute, template)

    def _rows(self):
        if hasattr(self, "_annotation_rows"):
            return self._annotation_rows
        inventory = self._inventory()
        paths = self._paths()
        rows, identities = [], set()
        stats = {"tasks": {}, "referenced": set(), "absent": {}}
        for task in self._tasks():
            name, aspect = task.get("task"), task.get("aspect")
            if not isinstance(name, str) or not name or not isinstance(aspect, str) or not aspect:
                raise ValueError("Every MultiTrust task needs a task name and an aspect")
            companion = None
            if task.get("companion_lines"):
                spec = task["companion_lines"]
                if spec["source_name"] not in paths:
                    raise ValueError(f"Companion file {spec['source_name']!r} is not among the pinned source files")
                companion = [line.strip() for line in paths[spec["source_name"]].read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            task_stats = {"aspect": aspect, "rows": 0, "rows_with_image_reference": 0, "rows_without_image_reference": 0,
                          "image_references": 0, "references_present": 0, "references_absent": 0, "rows_with_absent_image": 0,
                          "files": {}, "join_basis": task.get("join_basis")}
            for file_name in self._query_files(task):
                if file_name not in paths:
                    raise ValueError(f"Query file {file_name!r} is not among the pinned source files")
                items = self._items(task, file_name, paths[file_name].read_bytes())
                task_stats["files"][file_name] = len(items)
                for flat, (subset, native) in enumerate(items):
                    if companion is not None and task["companion_lines"].get("field"):
                        native = {**native, task["companion_lines"]["field"]: companion[flat] if flat < len(companion) else None}
                    if RESERVED & set(native) or any(key.startswith("_atlas_") for key in native):
                        raise ValueError(f"{file_name}: a native field collides with a reserved Atlas field")
                    modulus = task.get("row_modulo")
                    variables = {"_row": flat + 1, "_row0": flat, "_group": subset if subset is not None else "",
                                 "_row_mod": flat % modulus if modulus else flat, "_row_mod1": flat % modulus + 1 if modulus else flat + 1}
                    refs, roles = [], {}
                    for media in task.get("media", []):
                        if "row_lt" in media and not flat < media["row_lt"]:
                            continue
                        path = _safe_relative(self._expand(media["template"], native, variables))
                        ref = f"file/{path}"
                        if ref in refs:
                            continue
                        refs.append(ref)
                        if media.get("role"):
                            roles[ref] = {"role": media["role"]}
                    identity = f"{name}:{subset}:{flat}" if task.get("query_files") else f"{name}:{flat}"
                    if identity in identities:
                        raise ValueError(f"Duplicate record identity {identity}")
                    identities.add(identity)
                    absent = [ref for ref in refs if ref[5:] not in inventory]
                    task_stats["rows"] += 1
                    task_stats["image_references"] += len(refs)
                    task_stats["references_absent"] += len(absent)
                    task_stats["references_present"] += len(refs) - len(absent)
                    task_stats["rows_with_image_reference"] += bool(refs)
                    task_stats["rows_without_image_reference"] += not refs
                    task_stats["rows_with_absent_image"] += bool(absent)
                    stats["referenced"].update(ref[5:] for ref in refs)
                    for ref in absent:
                        stats["absent"][ref[5:]] = stats["absent"].get(ref[5:], 0) + 1
                    row = {**native, "task": name, "aspect": aspect, "query_file": file_name,
                           "_atlas_origin": {"split": name, "row": flat, "file": file_name, "identity": identity, "group": aspect,
                                             **({"subset": subset} if subset is not None else {})},
                           "_atlas_media_refs": refs}
                    if roles:
                        row["_atlas_media_conditions"] = roles
                    rows.append(row)
            stats["tasks"][name] = task_stats
        # An absent image is declared so that the inherited reader marks the asset absent instead of failing.
        self.config["declared_absent_media"] = sorted(f"file/{path}" for path in stats["absent"])
        self._join_stats = stats
        self._annotation_rows = rows
        return rows

    def join_report(self) -> dict:
        """Counts of every join, computed from the rows; nothing is dropped."""
        self._rows()
        stats = self._join_stats
        if stats is None:
            raise ValueError("MultiTrust rows were not built")
        inventory = self._inventory()
        unreferenced = sorted(set(inventory) - stats["referenced"])
        return {"rows": len(self._annotation_rows), "tasks": stats["tasks"], "absent_image_paths": sorted(stats["absent"]),
                "inventory_images": len(inventory), "referenced_inventory_images": len(stats["referenced"] & set(inventory)),
                "inventory_images_without_a_query_row": unreferenced}

    # -- media validation (no transfer) --------------------------------------------------------------------------------

    def validate_media(self, budget, cancel=None):
        """Join every row to the pinned inventory without fetching an image. Absent images are counted, never dropped."""
        report = self.join_report()
        absent = report["absent_image_paths"]
        rows_with = sum(task["rows_with_image_reference"] for task in report["tasks"].values())
        return {"referenced_images": report["referenced_inventory_images"], "archives": 0, "metadata_bytes_fetched": 0,
                "rows": report["rows"], "rows_with_image_reference": rows_with, "rows_without_image_reference": report["rows"] - rows_with,
                "absent_media_references": len(absent), "absent_media": [f"file/{path}" for path in absent[:200]],
                "inventory_images_without_a_query_row": len(report["inventory_images_without_a_query_row"]),
                "integrity": "Original files are checked against the pinned inventory (Hub LFS SHA-256, or the Git blob SHA-1 where the Hub "
                             "has no LFS hash) when read. Rows whose image is absent from the pinned release stay records with a named absent asset."}

    # -- originals -----------------------------------------------------------------------------------------------------

    def resolve_asset(self, source, asset_ref):
        if not asset_ref.startswith("file/"):
            raise ValueError("Invalid MultiTrust asset reference")
        name = _safe_relative(asset_ref[5:])
        entry = self._inventory().get(name)
        if not entry:
            raise ValueError("Image is absent from pinned inventory")
        remaining = source.max_bytes - source.bytes_read
        if entry["bytes"] > remaining:
            raise ValueError("Source image exceeds byte budget")
        if self.preparation_transfer_limit is not None and self.media_bytes_fetched + entry["bytes"] > self.preparation_transfer_limit:
            raise ValueError("Original image transfer budget exhausted")
        from urllib.parse import quote
        cache = BoundedCache(self.config["remote_cache_root"], max_bytes=self.config.get("remote_cache_bytes", 1_000_000_000))
        url = self.config["media_base_url"].rstrip("/") + "/" + quote(name, safe="/")
        fetcher = HttpsFetcher(self.config["media_allowed_hosts"], max_bytes=remaining, credential_profile=self.config.get("credential_profile"))
        identity = CacheIdentity(self.revision, entry.get("sha256", entry.get("git_blob_sha1")), "source-image")
        path = None
        for attempt in range(3):
            try:
                path = fetcher.fetch(url, cache, identity, expected_sha256=entry.get("sha256"), byte_budget=entry["bytes"])
                break
            except ValueError as error:
                text = str(error)
                status = re.search(r"HTTP (401|403)", text)
                if status:
                    raise ValueError(f"Source refused access (HTTP {status[1]}): this release is gated or the local sign-in is missing. "
                                     "Accept its terms on your own Hugging Face account and sign in locally "
                                     '(credential profile "huggingface"), then retry. Nothing was read.') from None
                if attempt < 2 and any(code in text for code in TRANSIENT):
                    time.sleep(1 + attempt)
                    continue
                raise
            except TimeoutError:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        self.media_bytes_fetched += fetcher.bytes_fetched
        if path is None:
            raise ValueError("Source image was not fetched")
        data = path.read_bytes()
        if len(data) != entry["bytes"]:
            raise ValueError("Source image length changed")
        if entry.get("sha256") and hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Source image checksum changed")
        if entry.get("git_blob_sha1") and hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() != entry["git_blob_sha1"]:
            raise ValueError("Source image differs from pinned Git object")
        return self._image_handle(source, data, asset_ref)

    def _image_handle(self, source, data, asset_ref):
        source.charge(len(data))
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 50_000_000:
                raise MediaLimitError("Original image exceeds the 50-million-pixel preview decode limit")
            mime = Image.MIME.get(image.format, "application/octet-stream")
            image.verify()
        return MediaHandle(data, mime, hashlib.sha256(data).hexdigest(), asset_ref)

    # -- coverage helpers ----------------------------------------------------------------------------------------------

    def population_by_aspect(self) -> dict[str, int]:
        return dict(Counter(row["aspect"] for row in self._rows()))
