"""Read the seven original eLife figure source-data workbooks without evaluating formulas."""

from __future__ import annotations

import hashlib
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

from dataset_atlas.models import Asset, Record, stable_id

from .core import DatasetAdapter, MediaHandle, RecordBatch, SourceDescription


MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _column_number(label: str) -> int:
    number = 0
    for character in label:
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def _column_label(number: int) -> str:
    result = ""
    while number:
        number, digit = divmod(number - 1, 26)
        result = chr(ord("A") + digit) + result
    return result


def _translate_shared(formula: str, anchor: str, target: str) -> str:
    if any(marker in formula for marker in ('"', "'", "!", "[", "]")):
        raise ValueError("Unsupported shared workbook formula reference")
    pattern = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
    first, last = pattern.fullmatch(anchor), pattern.fullmatch(target)
    if first is None or last is None:
        raise ValueError("Invalid shared formula coordinate")
    column_delta = _column_number(last[1]) - _column_number(first[1])
    row_delta = int(last[2]) - int(first[2])

    def move(match):
        column_absolute, column, row_absolute, row = match.groups()
        new_column = _column_number(column) + (0 if column_absolute else column_delta)
        new_row = int(row) + (0 if row_absolute else row_delta)
        if new_column < 1 or new_row < 1:
            raise ValueError("Shared formula translated outside worksheet")
        return f"{column_absolute}{_column_label(new_column)}{row_absolute}{new_row}"

    return re.sub(r"(?<![A-Za-z0-9_.])(\$?)([A-Z]{1,3})(\$?)([1-9][0-9]*)(?![A-Za-z0-9_])",
                  move, formula)


def _workbook_cells(path: Path) -> list[dict]:
    """Preserve native sparse coordinates, values, formulas and cached results."""
    with zipfile.ZipFile(path) as archive:
        members = {item.filename: item for item in archive.infolist()}
        if len(members) != len(archive.infolist()) or len(members) > 80:
            raise ValueError("Unexpected or duplicate workbook members")
        if sum(item.file_size for item in members.values()) > 5_000_000:
            raise ValueError("Workbook decoded content exceeds read budget")
        shared = []
        if "xl/sharedStrings.xml" in members:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.iter(MAIN + "t"))
                      for item in root.findall(MAIN + "si")]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relations}
        sheets = []
        for sheet in workbook.findall("./" + MAIN + "sheets/" + MAIN + "sheet"):
            target = targets[sheet.attrib[REL + "id"]]
            member = posixpath.normpath(posixpath.join("xl", target.lstrip("/"))) if not target.startswith("/xl/") else target.lstrip("/")
            if not member.startswith("xl/worksheets/") or member not in members:
                raise ValueError("Workbook sheet target is missing or unsafe")
            xml = ET.fromstring(archive.read(member))
            rows = []
            shared_formulas = {}
            for row in xml.findall("./" + MAIN + "sheetData/" + MAIN + "row"):
                cells = []
                for cell in row.findall(MAIN + "c"):
                    raw = cell.findtext(MAIN + "v")
                    formula_node = cell.find(MAIN + "f")
                    formula = formula_node.text if formula_node is not None else None
                    if formula_node is not None and formula_node.attrib.get("t") == "shared":
                        key = formula_node.attrib["si"]
                        if formula:
                            if key in shared_formulas:
                                raise ValueError("Duplicate shared formula anchor")
                            shared_formulas[key] = (formula, cell.attrib["r"])
                        else:
                            if key not in shared_formulas:
                                raise ValueError("Shared formula anchor is missing")
                            expression, anchor = shared_formulas[key]
                            formula = _translate_shared(expression, anchor, cell.attrib["r"])
                    kind = cell.attrib.get("t", "n")
                    if kind == "s" and raw is not None:
                        value = shared[int(raw)]
                    elif kind == "inlineStr":
                        value = "".join(node.text or "" for node in cell.iter(MAIN + "t"))
                    elif kind == "b" and raw is not None:
                        value = raw == "1"
                    elif kind == "n" and raw is not None:
                        value = float(raw) if any(mark in raw for mark in ".eE") else int(raw)
                    else:
                        value = raw
                    if value is None and formula is None:
                        continue
                    entry = {"coordinate": cell.attrib["r"], "type": kind}
                    if raw is not None:
                        entry["raw_value"] = raw
                    if formula is not None:
                        entry["formula"] = "=" + formula
                        entry["cached_value"] = value
                    else:
                        entry["value"] = value
                    cells.append(entry)
                if cells:
                    rows.append({"row": int(row.attrib["r"]), "cells": cells})
            sheets.append({"name": sheet.attrib["name"], "rows": rows,
                           "nonempty_cells": sum(len(row["cells"]) for row in rows)})
        if not sheets:
            raise ValueError("Workbook contains no readable sheets")
        return sheets


class ElifeWorkbooksAdapter(DatasetAdapter):
    def _files(self):
        entries = self.config["workbooks"]
        if len(entries) != 7 or len({item["name"] for item in entries}) != 7:
            raise ValueError("eLife source-data workbook inventory is incomplete or duplicated")
        for item in entries:
            if item["name"] != Path(item["name"]).name or not item["name"].endswith(".xlsx"):
                raise ValueError("Invalid source-data workbook name")
        return entries

    def probe(self):
        entries = self._files()
        paths = [Path(self.config[item["path_key"]]) for item in entries if item["path_key"] in self.config]
        exists = len(paths) == len(entries) and all(path.is_file() for path in paths)
        return SourceDescription("elife_figure_workbooks", str(paths[0]) if paths else "eLife 55378 source data",
                                 exists, self.revision, sum(item["bytes"] for item in entries),
                                 False, True, True, True, False,
                                 ("Original workbooks are passive; formulas are retained but never evaluated.",))

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        for item in self._files():
            path = Path(self.config[item["path_key"]])
            if path.stat().st_size != item["bytes"]:
                raise ValueError("eLife workbook size changed")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                    raise ValueError("eLife workbook checksum changed")
        return source

    def _records(self):
        if hasattr(self, "_native_records"):
            return self._native_records
        records = []
        for item in self._files():
            sheets = _workbook_cells(Path(self.config[item["path_key"]]))
            name = item["name"]
            asset_id = stable_id(self.dataset.id, self.revision, "asset", name)
            asset = Asset(id=asset_id, dataset_id=self.dataset.id, release_id=self.revision,
                          modality="table", uri=name, sha256=item["sha256"],
                          metadata={"format": "xlsx", "original_bytes": item["bytes"],
                                    "figure": item["figure"]})
            records.append(Record(
                id=stable_id(self.dataset.id, self.revision, "record", name),
                dataset_id=self.dataset.id, release_id=self.revision,
                snapshot_id=self.dataset.snapshot_id, unit="asset",
                asset_ids=[asset_id], assets=[asset],
                source={"article_id": "55378", "article_version": 1, "filename": name,
                        "figure": item["figure"], "sheets": sheets,
                        "nonempty_cells": sum(sheet["nonempty_cells"] for sheet in sheets),
                        "formula_cells": sum("formula" in cell for sheet in sheets for row in sheet["rows"] for cell in row["cells"])}))
        self._native_records = records
        return records

    def iter_records(self, source, cursor=None, limit=None):
        records = self._records()
        start = int(cursor or 0)
        if start < 0 or start > len(records):
            raise ValueError("Invalid eLife workbook cursor")
        end = min(len(records), start + min(limit or source.limit, source.limit))
        batch = records[start:end]
        for record in batch:
            source.charge(len(record.model_dump_json().encode()))
        return RecordBatch(batch, str(end) if end < len(records) else None, len(batch))

    def resolve_asset(self, source, asset_ref):
        item = next((entry for entry in self._files() if entry["name"] == asset_ref), None)
        if item is None:
            raise ValueError("Workbook absent from pinned eLife source-data inventory")
        if item["bytes"] > source.max_bytes - source.bytes_read:
            raise ValueError("Workbook exceeds byte budget")
        data = Path(self.config[item["path_key"]]).read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("eLife workbook checksum changed")
        source.charge(len(data))
        return MediaHandle(data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           item["sha256"], asset_ref)
