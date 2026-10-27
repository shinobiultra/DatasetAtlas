import json
import csv
from pathlib import Path

import yaml

from dataset_atlas.adapters.coverage import sync_curated_candidates, write_coverage_csv
from dataset_atlas.models import Dataset


def test_corpus_sync_preserves_source_research_on_unresolved_candidate(tmp_path: Path):
    registry = tmp_path / "registry"; registry.mkdir()
    existing = Dataset(
        id="example", name="Example", release="author-release", source_url="https://source.example/release",
        adapter="structured", adapter_config={"path": "work/example.jsonl"},
        coverage={"identity": "candidate", "source": "verified", "access": "public",
                  "adapter": "implemented", "preview": "none", "complete_data": "requires_preparation",
                  "publication": "metadata_only"},
        rights={"records": "not_reviewed", "source": "https://source.example/rights"},
        evidence=[{"kind": "source_release", "url": "https://source.example/release"}],
    )
    (registry / "example.yaml").write_text(yaml.safe_dump(existing.model_dump(mode="python")))
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps({"candidates": [{"proposed_id": "example", "name": "Example",
        "aliases_as_written": ["Example Set"], "paper_ids": ["paper-1"],
        "evidence_ids": ["evidence-1"]}, {"proposed_id": "unadmitted", "name": "Unadmitted candidate",
        "aliases_as_written": [], "paper_ids": [], "evidence_ids": []}]}))
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text(json.dumps({"evidence_id": "evidence-1", "paper_id": "paper-1",
        "source_file_hash": "abc", "page": 3, "mention_role": "bibliography-only reference",
        "supporting_excerpt": "Example Set (2020)",
        "review_scope": "full_text_mention_inventory_checked", "paper_full_review_complete": True}) + "\n")

    assert sync_curated_candidates(candidates, evidence, registry) == 1
    actual = Dataset.model_validate(yaml.safe_load((registry / "example.yaml").read_text()))
    assert actual.coverage.source == "verified"
    assert actual.coverage.adapter == "implemented"
    assert actual.source_url == "https://source.example/release"
    assert actual.rights == existing.rights
    assert actual.adapter_config == existing.adapter_config
    assert actual.paper_ids == ["paper-1"] and actual.aliases == ["Example Set"]
    assert actual.evidence[-1]["role"] == "bibliography-only reference"
    assert actual.evidence[-1]["paper_full_review_complete"] is True
    assert not (registry / "unadmitted.yaml").exists()
    assert sync_curated_candidates(candidates, evidence, registry) == 0


def test_new_candidates_require_explicit_supported_id_admission(tmp_path: Path):
    registry = tmp_path / "registry"
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps({"candidates": [
        {"proposed_id": dataset_id, "name": dataset_id, "aliases_as_written": [],
         "paper_ids": [], "evidence_ids": []}
        for dataset_id in ("supported", "unadmitted")
    ]}))
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text("")

    assert sync_curated_candidates(candidates, evidence, registry) == 0
    assert list(registry.glob("*.yaml")) == []
    assert sync_curated_candidates(candidates, evidence, registry, supported_ids={"supported"}) == 1
    assert not (registry / "unadmitted.yaml").exists()
    actual = Dataset.model_validate(yaml.safe_load((registry / "supported.yaml").read_text()))
    assert actual.coverage.identity == "candidate"
    assert actual.coverage.publication == "not_reviewed"
    assert actual.rights == {"records": "not_reviewed", "annotations": "not_reviewed", "images": "not_reviewed"}
    assert actual.evidence == []
    assert sync_curated_candidates(candidates, evidence, registry) == 0


def test_explicit_admission_cannot_write_outside_the_registry(tmp_path: Path):
    registry = tmp_path / "registry"
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps({"candidates": [
        {"proposed_id": "../outside", "name": "Invalid path", "aliases_as_written": [],
         "paper_ids": [], "evidence_ids": []}
    ]}))
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text("")
    import pytest
    with pytest.raises(ValueError, match="Invalid dataset ID"):
        sync_curated_candidates(candidates, evidence, registry, supported_ids={"../outside"})
    assert not (tmp_path / "outside.yaml").exists()


def test_coverage_distinguishes_access_gate_from_implementation_gap(tmp_path: Path):
    registry = tmp_path / "registry"; registry.mkdir()
    rows = {
        "gated": Dataset(id="gated", name="Gated", coverage={"identity": "resolved",
            "source": "verified", "access": "gated", "adapter": "not_started"}),
        "pending": Dataset(id="pending", name="Pending", coverage={"identity": "candidate",
            "source": "unverified", "access": "unverified", "adapter": "not_started"}),
    }
    for name, dataset in rows.items():
        (registry / f"{name}.yaml").write_text(yaml.safe_dump(dataset.model_dump(mode="python")))
    target = tmp_path / "coverage.csv"
    assert write_coverage_csv(registry, target) == 2
    with target.open(newline="") as stream:
        result = {row["dataset_id"]: row for row in csv.DictReader(stream)}
    assert "external_access_gate" in result["gated"]["blocker_type"]
    assert "implementation_gap" in result["gated"]["blocker_type"]
    assert "external_access_gate" not in result["pending"]["blocker_type"]
    assert "source_research" in result["pending"]["blocker_type"]
