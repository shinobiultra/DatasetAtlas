"""Release claims follow the live catalogue and current, explicit verification proof."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def report_module():
    spec = importlib.util.spec_from_file_location("atlas_release_report", ROOT / "scripts/report_release.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def matrix() -> list[dict[str, str]]:
    with (ROOT / "reports/dataset_coverage.csv").open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_final_status_matches_runtime_catalogue_and_coverage_matrix():
    from dataset_atlas.registry import Registry

    status = json.loads((ROOT / "reports/final-status.json").read_text())
    rows = matrix()
    registry = Registry(ROOT)
    datasets = [dataset for dataset in registry.datasets() if dataset.origin == "catalogue"]
    assert status["schema_version"] == "1.0"
    assert status["release_version"] == "1.0.0"
    assert {row["dataset_id"] for row in rows} == {dataset.id for dataset in datasets}
    assert status["catalogue_entries"] == len(rows) == len(datasets)
    assert status["prepared_previews"] == sum(int(row["preview_count"]) > 0 for row in rows)
    assert status["preview_records"] == sum(int(row["preview_count"]) for row in rows)
    assert status["entries_without_preview"] == sum(int(row["preview_count"]) == 0 for row in rows)
    assert status["local_complete_indices"] == sum(row["local_index_scope"] == "complete" for row in rows)
    sources = json.loads((ROOT / "reports/catalogue-sources.json").read_text())
    normalized = [{**row,
                   "preview_count": int(row["preview_count"]),
                   "declared_source_count": int(row["declared_source_count"]) if row["declared_source_count"] else None,
                   "local_index_count": int(row["local_index_count"]) if row["local_index_count"] else None}
                  for row in rows]
    assert sources["schema_version"] == "1.0"
    assert status["catalogue_sha256"] == sources["catalogue_sha256"] == report_module().json_hash({"rows": normalized, "sources": sources["datasets"]})
    # CI has the catalogue metadata and report, not the maintainer's private data.
    # Where active local versions exist, also compare their declared record counts.
    local = {dataset.id: dataset for dataset in datasets if registry.active_directory(dataset.id)}
    for row in rows:
        if row["dataset_id"] in local:
            assert int(row["preview_count"]) == local[row["dataset_id"]].coverage.preview_count


def test_completion_is_bound_to_verified_current_release_evidence():
    module = report_module()
    status = json.loads((ROOT / "reports/final-status.json").read_text())
    verification = status["verification"]
    checks = verification["checks"]
    ready = bool(checks) and all(checks.get(name, {}).get("status") == "passed" for name in module.REQUIRED_CHECKS)
    assert status["full_v1_complete"] is (verification["status"] == "verified" and ready)
    if status["full_v1_complete"]:
        assert verification["schema_version"] == "1.0"
        assert verification["catalogue_sha256"] == status["catalogue_sha256"]
        assert verification["release_tree_sha256"] == status["release_tree_sha256"] == module.release_tree_sha256(ROOT)
        assert verification["proof_sha256"]
    evidence = (ROOT / "reports/release_evidence.md").read_text()
    assert status["catalogue_sha256"] in evidence
    assert f"full_v1_complete: {str(status['full_v1_complete']).lower()}" in evidence


def test_verification_rejects_missing_or_stale_checks():
    module = report_module()
    current = {"catalogue_sha256": "a" * 64, "release_tree_sha256": "b" * 64}
    proof = {"schema_version": "1.0", "release_version": "1.0.0", **current, "checks": {}}
    with pytest.raises(ValueError, match="required checks"):
        module.validate_verification(proof, current, "1.0.0")
    proof["checks"] = {name: {"status": "passed", "command": "bounded check", "checked_at_utc": "2026-10-27T00:00:00+00:00", "summary": "passed"} for name in module.REQUIRED_CHECKS}
    module.validate_verification(proof, current, "1.0.0")
    proof["catalogue_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="catalogue_sha256"):
        module.validate_verification(proof, current, "1.0.0")
    proof["catalogue_sha256"] = current["catalogue_sha256"]
    proof["release_tree_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="release_tree_sha256"):
        module.validate_verification(proof, current, "1.0.0")


def test_structural_preview_count_ignores_native_values(tmp_path):
    module = report_module()
    path = tmp_path / "preview.json"
    path.write_text(json.dumps({"dataset": {"adapter_config": {"records": [1, 2, 3]}},
                                "records": [{"text": 'braces [{ and escaped "records": [', "source": {"nested": [1, 2]}},
                                            {"source": {"array": [{"key": "value"}]}}],
                                "sampling": {"count": 999}}))
    assert module.preview_record_count(path) == 2


def test_release_inventory_requires_real_preview_and_native_representation():
    module = report_module()
    row = {"dataset_id": "toy", "declared_source_count": 3, "preview_pack_sha256": "a" * 64,
           "preview_count": 3, "local_index_scope": "complete", "local_index_count": 3,
           "index_manifest_sha256": "b" * 64}
    current = {"rows": [row], "sources": [{"dataset_id": "toy", "native_source_sampling": False}]}
    module.validate_inventory(current)
    row["preview_count"] = 2
    with pytest.raises(ValueError, match="required real preview"):
        module.validate_inventory(current)
    row["preview_count"] = 3
    row["local_index_scope"] = "none"
    with pytest.raises(ValueError, match="pinned native source sampler"):
        module.validate_inventory(current)
    current["sources"][0]["native_source_sampling"] = True
    module.validate_inventory(current)


@pytest.mark.parametrize("field,value", [("release", "release-old"), ("snapshot_id", "snapshot-old"), ("unit", "entity")])
def test_release_report_rejects_stale_preview_identity(tmp_path, field, value):
    import yaml
    from dataset_atlas.models import Dataset, Pack, Record

    module = report_module()
    dataset = Dataset(id="toy", name="Toy", release="release-current", snapshot_id="snapshot-current",
                      coverage={"preview_count": 1, "total_count": 1, "unit": "example"})
    registry_path = tmp_path / "registry/datasets"
    registry_path.mkdir(parents=True)
    (registry_path / "toy.yaml").write_text(yaml.safe_dump(dataset.model_dump()))
    pack_path = tmp_path / "work/packs/toy/pack.json"
    pack_path.parent.mkdir(parents=True)
    record = Record(id="toy:example:1", dataset_id="toy", release_id=dataset.release, snapshot_id=dataset.snapshot_id)
    pack = Pack(dataset=dataset.model_copy(deep=True), fields=[], records=[record])
    pack_path.write_text(pack.model_dump_json())
    manifest_path = tmp_path / "work/snapshots/toy/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"dataset_id": "toy", "snapshot_id": dataset.snapshot_id,
                                         "population_scope": "complete", "record_count": 1}))
    module.validate_inventory(module.collect_release(tmp_path))
    if field == "unit":
        pack.dataset.coverage.unit = value
    else:
        setattr(pack.dataset, field, value)
    pack_path.write_text(pack.model_dump_json())
    with pytest.raises(ValueError, match="preview header.*" + field):
        module.collect_release(tmp_path)


def test_public_release_reports_exclude_private_machine_paths():
    for name in ("final-status.json", "catalogue-sources.json", "dataset_coverage.csv", "release_evidence.md", "limitations.md"):
        text = (ROOT / "reports" / name).read_text()
        assert "/home/" not in text
        assert "/Users/" not in text
        assert "work/prepared/" not in text
