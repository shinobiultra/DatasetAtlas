"""The 2026-10-08 gate-check receipt is dated evidence, not a claim about content and not a place for credentials.

Task 5 checked two Hugging Face gates (MultiTrust, BBQ-V) and two outage hosts (Broden's archive host and the First
Person Social Interactions video host) with read-only metadata calls. The receipt must hold no token, no header and no
local path, and every registry file the task touched may only have gained evidence (and, if text had to change,
appended blocker lines): identity, release, preview, adapter and snapshot_id stay as committed at the base.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "reports" / "gate-check-20261008.json"
BASE_COMMIT = "4a18626"
PROTECTED_FIELDS = ("identity", "release", "preview", "adapter", "snapshot_id")
MISSING = object()
# Entries the receipt must cover and may touch: the two gates and the two outage hosts.
REQUIRED_DATASETS = {"multitrust", "sbbench", "broden", "first-person-social-interactions-dataset"}
OUTAGE_ENTRIES = ("registry/datasets/broden.yaml", "registry/datasets/first-person-social-interactions-dataset.yaml")
TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{20,}")
UTC_STAMP = re.compile(r"^2026-10-08T\d{2}:\d{2}:\d{2}Z$")


def _receipt_text() -> str:
    return RECEIPT.read_text(encoding="utf-8")


def _receipt() -> dict:
    return json.loads(_receipt_text())


def _at_base(relative_path: str) -> dict:
    probe = subprocess.run(["git", "cat-file", "-e", f"{BASE_COMMIT}^{{commit}}"], cwd=ROOT, capture_output=True)
    if probe.returncode != 0:
        pytest.skip(f"base commit {BASE_COMMIT} is not available in this checkout (shallow clone or archive)")
    shown = subprocess.run(["git", "show", f"{BASE_COMMIT}:{relative_path}"], cwd=ROOT, capture_output=True, text=True,
                           check=True)
    return yaml.safe_load(shown.stdout)


def _protected(document: dict) -> dict:
    coverage = document.get("coverage") or {}
    return {
        f"{where}.{name}": source.get(name, MISSING)
        for where, source in (("top", document), ("coverage", coverage))
        for name in PROTECTED_FIELDS
    }


def _without_additions(document: dict) -> dict:
    """The entry with the two lists that may grow (evidence, coverage.blockers) removed."""
    stripped = {key: value for key, value in document.items() if key != "evidence"}
    stripped["coverage"] = {key: value for key, value in (document.get("coverage") or {}).items()
                            if key != "blockers"}
    return stripped


def test_the_receipt_is_valid_json_with_a_dated_entry_per_checked_url():
    receipt = _receipt()
    assert receipt["checked_on"] == "2026-10-08"
    assert receipt["base_commit"] == BASE_COMMIT
    checks = receipt["checks"]
    assert {check["dataset_id"] for check in checks} >= REQUIRED_DATASETS
    for check in checks:
        assert check["url"].startswith(("http://", "https://")), check
        assert check["call"], check
        assert check["observed"], check
        assert check["conclusion"], check
        assert UTC_STAMP.match(check["checked_at_utc"]), check


def test_the_receipt_holds_no_token_header_or_local_path():
    text = _receipt_text()
    assert not TOKEN_PATTERN.search(text), "a Hugging Face token pattern is present"
    assert "authorization" not in text.lower()
    assert "bearer" not in text.lower()
    assert "/home/" not in text


def test_the_receipt_lists_the_registry_files_it_touched_and_covers_both_outage_hosts():
    touched = _receipt()["registry_files_touched"]
    assert touched and all(path.startswith("registry/datasets/") and path.endswith(".yaml") for path in touched)
    assert set(OUTAGE_ENTRIES) <= set(touched)
    assert len(touched) == len(set(touched))


def test_every_touched_registry_file_only_gained_evidence_and_keeps_its_protected_fields():
    for relative_path in _receipt()["registry_files_touched"]:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert not TOKEN_PATTERN.search(text), f"{relative_path} carries a token pattern"
        now, base = yaml.safe_load(text), _at_base(relative_path)

        assert _protected(now) == _protected(base), f"{relative_path}: a protected field changed"
        assert _without_additions(now) == _without_additions(base), f"{relative_path}: a non-evidence field changed"

        added = now["evidence"][len(base["evidence"]):]
        assert now["evidence"][:len(base["evidence"])] == base["evidence"], f"{relative_path}: old evidence edited"
        assert added, f"{relative_path}: no evidence was appended"
        for item in added:
            assert item["checked_on"] == "2026-10-08", (relative_path, item)
            assert item["kind"] in {"source_audit_access", "source_audit_release"}, (relative_path, item)

        base_blockers = (base.get("coverage") or {}).get("blockers", [])
        blockers = (now.get("coverage") or {}).get("blockers", [])
        assert blockers[:len(base_blockers)] == base_blockers, f"{relative_path}: an existing blocker was edited"


def test_the_outage_entries_each_gained_an_access_observation_of_the_day():
    for relative_path in OUTAGE_ENTRIES:
        now, base = yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8")), _at_base(relative_path)
        added = now["evidence"][len(base["evidence"]):]
        assert any(item["kind"] == "source_audit_access" and item["checked_on"] == "2026-10-08" for item in added), (
            relative_path)
