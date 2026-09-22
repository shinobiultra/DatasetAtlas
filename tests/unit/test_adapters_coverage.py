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
        "evidence_ids": ["evidence-1"]}, {"proposed_id": "excluded", "name": "Not a dataset",
        "aliases_as_written": [], "paper_ids": [], "evidence_ids": []}]}))
    (tmp_path / "candidate_dispositions.yaml").write_text(yaml.safe_dump(
        {"excluded_from_dataset_catalogue": [{"id": "excluded", "reason": "verified non-dataset"}]}))
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
    assert not (registry / "excluded.yaml").exists()
    assert sync_curated_candidates(candidates, evidence, registry) == 0


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
