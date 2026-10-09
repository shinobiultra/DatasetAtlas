"""XLSX source cells and formulas remain passive, exact and source-addressable."""

import hashlib
import zipfile

import pytest

from dataset_atlas.adapters.core import PreparationPlan, get_adapter
from dataset_atlas.adapters.elife_workbooks import _translate_shared
from dataset_atlas.models import Dataset


def _fixture_workbook(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>""")
        archive.writestr("xl/_rels/workbook.xml.rels", """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>""")
        archive.writestr("xl/sharedStrings.xml", """<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Value</t></si></sst>""")
        archive.writestr("xl/worksheets/sheet1.xml", """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="B2"><f>SUM(2,3)</f><v>5</v></c></row><row r="3"><c r="C3"><v>2.5</v></c></row></sheetData></worksheet>""")


def test_elife_workbook_cells_formula_and_pinned_original(tmp_path):
    config, entries = {}, []
    for number in range(7):
        name = f"figure-{number}.xlsx"
        path = tmp_path / name
        _fixture_workbook(path)
        key = f"workbook_{number}"
        config[key] = str(path)
        entries.append({"name": name, "path_key": key, "figure": f"Figure {number}",
                        "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    config["workbooks"] = entries
    dataset = Dataset(id="workbooks", name="Workbooks", release="elife-55378-v1",
                      snapshot_id="s1", adapter="elife_workbooks", adapter_config=config)
    adapter = get_adapter(dataset)
    source = adapter.prepare(PreparationPlan(dataset.id, dataset.release, None, 7, 100_000, 0, 100_000))
    records = adapter.iter_records(source, limit=7).records
    assert len(records) == 7 and {record.unit for record in records} == {"asset"}
    first = records[0].source
    assert first["nonempty_cells"] == 3 and first["formula_cells"] == 1
    rows = first["sheets"][0]["rows"]
    assert rows[0]["cells"][0]["value"] == "Value"
    assert rows[1]["cells"][0]["formula"] == "=SUM(2,3)"
    assert rows[1]["cells"][0]["cached_value"] == 5
    assert rows[2]["cells"][0]["value"] == 2.5
    assert adapter.resolve_asset(source, entries[0]["name"]).sha256 == entries[0]["sha256"]
    with pytest.raises(ValueError, match="absent"):
        adapter.resolve_asset(source, "unknown.xlsx")
    (tmp_path / entries[0]["name"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum|size"):
        adapter.resolve_asset(source, entries[0]["name"])


def test_shared_formula_translation_preserves_absolute_references():
    assert _translate_shared("ROUND(B2,-1)+$D$1+B$3+$E4", "C2", "C4") == "ROUND(B4,-1)+$D$1+B$3+$E6"
