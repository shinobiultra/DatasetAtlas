"""The headline numbers must agree across the coverage matrix, the final status, the README, the roadmap and the guides."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def matrix() -> list[dict[str, str]]:
    with (ROOT / "reports/dataset_coverage.csv").open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def headline() -> dict[str, int]:
    rows = matrix()
    previews = [row for row in rows if row["preview"] != "none"]
    return {"entries": len(rows), "previews": len(previews), "without": len(rows) - len(previews),
            "records": sum(int(row["preview_count"] or 0) for row in previews)}


def test_final_status_equals_the_coverage_matrix():
    status = json.loads((ROOT / "reports/final-status.json").read_text())
    numbers = headline()
    assert (status["catalogue_entries"], status["tested_local_previews"], status["entries_without_preview"], status["verified_preview_records"]) == \
        (numbers["entries"], numbers["previews"], numbers["without"], numbers["records"])
    assert status["full_v1_complete"] is False


def test_the_matrix_lists_exactly_the_catalogue():
    ids = {path.stem for path in (ROOT / "registry/datasets").glob("*.yaml")}
    assert {row["dataset_id"] for row in matrix()} == ids


def test_readme_roadmap_and_guides_state_the_same_numbers():
    numbers = headline()
    readme = (ROOT / "README.md").read_text()
    roadmap = (ROOT / "ROADMAP.md").read_text()
    guide = (ROOT / "docs/getting-started.md").read_text()
    evidence = (ROOT / "reports/release_evidence.md").read_text()
    assert f"**{numbers['entries']} catalogue entries**" in readme and f"**{numbers['previews']} prepared previews**" in readme
    assert f"**{numbers['records']:,} preview records**" in readme and f"**{numbers['without']} entries still lack a prepared preview.**" in readme
    assert f"the {numbers['entries']}-entry catalogue" in readme
    assert re.search(rf"\*\*{numbers['entries']} catalogue entries, {numbers['previews']} prepared previews, {numbers['records']:,} real preview records", roadmap)
    assert f"{numbers['entries']} datasets and benchmarks" in guide
    assert f"**{numbers['entries']} catalogue entries, {numbers['previews']} native previews, {numbers['records']:,} preview records" in evidence.split("\n", 6)[2]
