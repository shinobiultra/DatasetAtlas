"""Local-only migration behavior over synthetic immutable snapshots."""
import hashlib
import json
from pathlib import Path

import pytest

from dataset_atlas.models import Dataset, FieldDescriptor, Pack, Record
from dataset_atlas.queries.parquet import build_parquet_snapshot


def workspace(tmp_path):
    dataset = Dataset(id="pata", name="Synthetic metadata fixture", release="synthetic-release",
                      snapshot_id="synthetic-snapshot")
    dataset.coverage.total_count = 12
    records = [Record(id=f"synthetic-{i}", dataset_id="pata", release_id=dataset.release,
                      snapshot_id=dataset.snapshot_id, source={"scene": f"group-{i % 3}", "media_available": False})
               for i in range(12)]
    fields = [FieldDescriptor(id="source.scene", name="scene", dtype="category")]
    directory = tmp_path / "work/prepared/pata/base"
    directory.mkdir(parents=True)
    build_parquet_snapshot(records, fields, directory / "snapshot", root=tmp_path,
                           dataset_id="pata", release_id=dataset.release, snapshot_id=dataset.snapshot_id,
                           expected_count=12, population_scope="complete")
    (directory / "dataset.json").write_text(dataset.model_dump_json())
    pointer = directory.parent / "active.json"
    pointer.write_text(json.dumps({"version": "base"}))
    return directory, pointer


def test_metadata_preview_preserves_snapshot_and_never_claims_image_samples(tmp_path):
    from dataset_atlas.preparation.native_units import prepare_pata_preview
    original, pointer = workspace(tmp_path)
    parquet = original / "snapshot/records.parquet"
    before = hashlib.sha256(parquet.read_bytes()).hexdigest()
    result = prepare_pata_preview(tmp_path, execute=True, count=4, max_output_bytes=1_000_000)
    assert json.loads(pointer.read_text()) == {"version": "base"}
    candidate = original.parent / result["version"]
    pack = Pack.model_validate_json((candidate / "pack/pack.json").read_text())
    assert len(pack.records) == 4
    assert pack.dataset.snapshot_id == "synthetic-snapshot"
    assert all(not r.assets and r.source["media_available"] is False for r in pack.records)
    assert pack.sampling["method"] == "sha256_bottom_k_metadata_records"
    assert pack.sampling["population_count"] == 12
    assert result["downloaded_bytes"] == result["native_image_preview_count"] == 0
    assert hashlib.sha256(parquet.read_bytes()).hexdigest() == before
    activated = prepare_pata_preview(tmp_path, execute=True, activate=True, count=4, max_output_bytes=1_000_000)
    assert activated["version"] == result["version"]
    assert json.loads(pointer.read_text())["version"] == result["version"]


def test_insufficient_budget_never_activates_or_changes_old_snapshot(tmp_path):
    from dataset_atlas.preparation.native_units import prepare_pata_preview
    original, pointer = workspace(tmp_path)
    before = (original / "snapshot/records.parquet").read_bytes()
    with pytest.raises(ValueError, match="budget"):
        prepare_pata_preview(tmp_path, execute=True, activate=True, max_output_bytes=1)
    assert json.loads(pointer.read_text())["version"] == "base"
    assert (original / "snapshot/records.parquet").read_bytes() == before


def test_dry_run_writes_nothing_and_reports_zero_downloads(tmp_path):
    from dataset_atlas.preparation.native_units import prepare_pata_preview
    workspace(tmp_path)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    result = prepare_pata_preview(tmp_path, max_output_bytes=1_000_000)
    assert result["status"] == "planned" and result["expected_download_bytes"] == 0
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


def test_multitrust_migration_retains_verified_preview_and_indexes_independent_images(tmp_path):
    from test_multitrust_inventory_units import SPECS, configured, records
    from dataset_atlas.preparation.native_units import prepare_multitrust_inventory
    from dataset_atlas.queries.parquet import ParquetSnapshot
    adapter = configured(tmp_path)
    original_records = records(adapter)
    directory = tmp_path / "work/prepared/multitrust/base"
    directory.mkdir(parents=True)
    fields = [FieldDescriptor(id="source.task", name="task", dtype="category", values=["query"])]
    build_parquet_snapshot(original_records, fields, directory / "snapshot", root=tmp_path,
                           dataset_id="multitrust", release_id="fixture", snapshot_id="fixture",
                           expected_count=1, population_scope="complete")
    media = directory / "pack/media/original"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"synthetic-original")
    preview = original_records[0].model_copy(deep=True)
    preview.assets[0].uri = "media/original"
    pack = Pack(dataset=adapter.dataset, fields=fields, records=[preview],
                sampling={"method": "synthetic_verified_fixture"},
                checksums={"media/original": hashlib.sha256(media.read_bytes()).hexdigest()})
    (directory / "pack/pack.json").write_text(pack.model_dump_json())
    (directory / "dataset.json").write_text(adapter.dataset.model_dump_json())
    pointer = directory.parent / "active.json"
    pointer.write_text(json.dumps({"version": "base"}))
    old_parquet = (directory / "snapshot/records.parquet").read_bytes()
    result = prepare_multitrust_inventory(tmp_path, execute=True, activate=True,
                                          max_output_bytes=1_000_000, inventory_tasks=SPECS)
    candidate = directory.parent / result["version"]
    snapshot = ParquetSnapshot(tmp_path, candidate / "snapshot")
    assert snapshot.record_count == 5
    assert result["query_records"] == 1 and result["inventory_records"] == 4
    assert result["image_only_records"] == 2
    assert result["downloaded_bytes"] == 0
    updated = Pack.model_validate_json((candidate / "pack/pack.json").read_text())
    assert updated.records[0].id == preview.id
    assert updated.records[0].assets == preview.assets
    assert updated.records[0].source["unit_kind"] == "query_row"
    assert updated.sampling["population_count"] == 1
    assert updated.sampling["current_complete_population_count"] == 5
    assert (candidate / "pack/media/original").read_bytes() == b"synthetic-original"
    assert (directory / "snapshot/records.parquet").read_bytes() == old_parquet
    migrated_dataset = Dataset.model_validate_json((candidate / "dataset.json").read_text())
    assert all(Path(entry["path"]).is_file() for entry in migrated_dataset.adapter_config["source_files"])
    fresh = __import__("dataset_atlas.adapters", fromlist=["get_adapter"]).get_adapter(migrated_dataset)
    assert len(records(fresh)) == 5
