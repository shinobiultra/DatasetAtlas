import hashlib, json, zipfile
import pytest
from dataset_atlas.adapters.find import FindAdapter
from dataset_atlas.models import Dataset


def fixture(tmp_path, orphan=False):
    path = tmp_path / "functions.zip"
    code = 'raise RuntimeError("must never execute")\n'
    weights = b"not-a-loadable-model"
    with zipfile.ZipFile(path, "w") as z:
        prefix = "find_dataset/strings/"
        z.writestr(
            prefix + "data.json",
            json.dumps([{"dir": "/native/author/f00000", "name": "source definition"}]),
        )
        z.writestr(prefix + "f00000/function_code.py", code)
        z.writestr(prefix + "f00000/mlp_approx_model.pt", weights)
        z.writestr(
            prefix + "unit_test_data.json",
            json.dumps([{"name": "f00001" if orphan else "f00000", "test_vec": []}]),
        )
    d = Dataset(
        id="find",
        name="Fixture",
        release="r",
        snapshot_id="s",
        adapter="find",
        adapter_config={
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "groups": ["strings"],
        },
    )
    return FindAdapter(d), code, weights


def test_code_and_model_bytes_are_passive_and_exact(tmp_path):
    adapter, code, weights = fixture(tmp_path)
    source = adapter.prepare(adapter.plan(10, 100000))
    batch = adapter.iter_records(source)
    assert batch.next_cursor is None and len(batch.records) == 1
    row = batch.records[0]
    assert row.text == code and row.source["execution_status"] == "not_executed"
    assert row.source["definition"]["dir"] == "/native/author/f00000"
    assert adapter.resolve_asset(source, row.assets[0].uri).data == code.encode()
    assert adapter.resolve_asset(source, row.assets[1].uri).data == weights
    with pytest.raises(ValueError, match="registered"):
        adapter.resolve_asset(source, "find_dataset/strings/data.json")
    source = adapter.prepare(adapter.plan(1, 1))
    with pytest.raises(ValueError, match="budget"):
        adapter.iter_records(source)


def test_orphaned_auxiliary_function_rows_fail(tmp_path):
    adapter, _, _ = fixture(tmp_path, orphan=True)
    with pytest.raises(ValueError, match="auxiliary"):
        adapter.prepare(adapter.plan(10, 100000))
