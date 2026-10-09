"""The 2026-10-08 gate-check receipt is dated evidence, not a claim about content and not a place for credentials.

Task 5 checked two Hugging Face gates (MultiTrust, BBQ-V) and two outage hosts (Broden's archive host and the First
Person Social Interactions video host) with read-only metadata calls. The receipt must hold no token, no header and no
local path, and must state its own method truthfully.

Two kinds of registry check, kept apart so that routine later work never turns this file red:

* A history check on the commit that introduced the receipt: against its parent, every touched registry file only
  gained evidence (and appended blocker lines), and identity, release, preview, adapter and snapshot_id are unchanged.
  History does not move, so a later refresh append or an adapter that legitimately changes those fields cannot break it.
* Live checks that look only at what this task owns: the evidence items whose `audit_file` is the receipt (and the
  MultiTrust blocker, only while the gate state this receipt documents still holds). Other evidence, other fields and
  other blockers are not examined.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = "reports/gate-check-20261008.json"
RECEIPT = ROOT / RECEIPT_PATH
PROTECTED_FIELDS = ("identity", "release", "preview", "adapter", "snapshot_id")
MISSING = object()
# Entries the receipt must cover and may touch: the two gates and the two outage hosts.
REQUIRED_DATASETS = {"multitrust", "sbbench", "broden", "first-person-social-interactions-dataset"}
OUTAGE_ENTRIES = ("registry/datasets/broden.yaml", "registry/datasets/first-person-social-interactions-dataset.yaml")
MULTITRUST = "registry/datasets/multitrust.yaml"
OWNED_KINDS = {"source_audit_access", "source_audit_release"}
TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{20,}")
UTC_STAMP = re.compile(r"^2026-10-08T\d{2}:\d{2}:\d{2}Z$")
AUTHOR_PAGE = "https://ai.stanford.edu/~alireza/Disney/"


def _here(relative_path: str) -> Path:
    """An entry removed from the catalogue on 2026-10-09 keeps its file under registry/excluded/."""
    path = ROOT / relative_path
    return path if path.exists() else ROOT / relative_path.replace("registry/datasets/", "registry/excluded/", 1)


def _receipt_text() -> str:
    return RECEIPT.read_text(encoding="utf-8")


def _receipt() -> dict:
    return json.loads(_receipt_text())


def _git(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    except OSError:
        pytest.skip("git is not available")


def _history_pair(relative_path: str) -> tuple[dict, dict]:
    """The entry at the parent of the commit that introduced the receipt, and as that commit left it.

    Before the receipt is committed the parent is HEAD and the introduced state is the working tree.
    """
    found = _git("log", "--diff-filter=A", "--format=%H", "--", RECEIPT_PATH)
    commits = found.stdout.split() if found.returncode == 0 else []
    if not commits:
        before = _git("show", f"HEAD:{relative_path}")
        if before.returncode != 0:
            pytest.skip("no git history is available in this checkout")
        return yaml.safe_load(before.stdout), yaml.safe_load(_here(relative_path).read_text(encoding="utf-8"))
    introduced_at = commits[-1]
    parent = f"{introduced_at}^"
    if _git("rev-parse", "--verify", "--quiet", parent).returncode != 0:
        pytest.skip("the receipt's parent commit is not in this checkout (shallow clone or archive)")
    before, after = _git("show", f"{parent}:{relative_path}"), _git("show", f"{introduced_at}:{relative_path}")
    assert before.returncode == 0 and after.returncode == 0, relative_path
    return yaml.safe_load(before.stdout), yaml.safe_load(after.stdout)


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


def _owned(document: dict) -> list[dict]:
    """The evidence items this task wrote: the ones whose audit_file is the receipt."""
    return [item for item in document.get("evidence", []) if item.get("audit_file") == RECEIPT_PATH]


def _live_problems(document: dict) -> list[str]:
    owned = _owned(document)
    problems = [] if owned else ["no evidence item cites the receipt"]
    for item in owned:
        if item.get("checked_on") != "2026-10-08":
            problems.append(f"item not dated 2026-10-08: {item.get('url')}")
        if item.get("kind") not in OWNED_KINDS:
            problems.append(f"unexpected kind {item.get('kind')}")
    return problems


def _load(relative_path: str) -> dict:
    return yaml.safe_load(_here(relative_path).read_text(encoding="utf-8"))


def test_the_receipt_is_valid_json_with_a_dated_entry_per_checked_url():
    receipt = _receipt()
    assert receipt["checked_on"] == "2026-10-08"
    assert receipt["base_commit"] == "4a18626"
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


def test_the_receipt_records_the_one_get_it_made_and_states_its_method_truthfully():
    receipt = _receipt()
    gets = [check for check in receipt["checks"] if check["call"].startswith("httpx.get(")]
    assert len(gets) == 1, "exactly one GET was made and it must be recorded"
    (get,) = gets
    assert get["dataset_id"] == "first-person-social-interactions-dataset"
    assert get["url"] == AUTHOR_PAGE
    assert get["observed"]["http_status"] == 200
    assert 0 < get["observed"]["bytes"] < 100_000, "an HTML page, never a README-or-larger body"
    assert get["observed"]["first_webshare_link"].startswith("http://webshare.ipat.gatech.edu/")
    assert UTC_STAMP.match(get["checked_at_utc"])
    note = receipt["note"]
    assert "metadata and HEAD only" not in note
    assert "plus one GET of the author's HTML page to read its links" in note
    # Every other call is metadata or HEAD: no further GET of any body.
    others = [check["call"] for check in receipt["checks"] if check is not get]
    assert not any(" GET" in call or call.startswith("httpx.get(") for call in others)


def test_the_receipt_lists_the_registry_files_it_touched_and_covers_both_outage_hosts():
    touched = _receipt()["registry_files_touched"]
    assert touched and all(path.startswith("registry/datasets/") and path.endswith(".yaml") for path in touched)
    assert set(OUTAGE_ENTRIES) <= set(touched)
    assert len(touched) == len(set(touched))


def test_the_commit_that_introduced_the_receipt_only_added_evidence_and_kept_the_protected_fields():
    for relative_path in _receipt()["registry_files_touched"]:
        before, after = _history_pair(relative_path)
        assert _protected(after) == _protected(before), f"{relative_path}: a protected field changed"
        assert _without_additions(after) == _without_additions(before), f"{relative_path}: a non-evidence field changed"

        kept = len(before["evidence"])
        assert after["evidence"][:kept] == before["evidence"], f"{relative_path}: old evidence edited"
        added = after["evidence"][kept:]
        assert added, f"{relative_path}: no evidence was appended"
        for item in added:
            assert item["audit_file"] == RECEIPT_PATH, (relative_path, item)
            assert item["checked_on"] == "2026-10-08", (relative_path, item)
            assert item["kind"] in OWNED_KINDS, (relative_path, item)

        base_blockers = (before.get("coverage") or {}).get("blockers", [])
        blockers = (after.get("coverage") or {}).get("blockers", [])
        assert blockers[:len(base_blockers)] == base_blockers, f"{relative_path}: an existing blocker was edited"


def test_every_touched_registry_file_still_parses_with_its_evidence_and_no_token():
    for relative_path in _receipt()["registry_files_touched"]:
        text = _here(relative_path).read_text(encoding="utf-8")
        assert not TOKEN_PATTERN.search(text), f"{relative_path} carries a token pattern"
        assert _live_problems(yaml.safe_load(text)) == [], relative_path


def test_the_outage_entries_each_carry_an_access_observation_of_the_day():
    for relative_path in OUTAGE_ENTRIES:
        assert any(item["kind"] == "source_audit_access" for item in _owned(_load(relative_path))), relative_path


def test_later_refresh_appends_and_coverage_progress_do_not_disturb_the_live_checks():
    document = _load("registry/datasets/broden.yaml")
    document["evidence"].append({"kind": "source_audit_refresh", "url": "https://example.org/x", "checked_on": "2026-11-02",
                                 "audit_file": "reports/candidate-source-refresh-20261102.json", "note": "later"})
    document["coverage"].update(preview="partial", adapter="implemented", access="public", preview_count=5)
    document["release"] = "later-release"
    assert _live_problems(document) == []
    document["evidence"] = [item for item in document["evidence"] if item.get("audit_file") != RECEIPT_PATH]
    assert _live_problems(document) == ["no evidence item cites the receipt"]


def test_the_multitrust_note_does_not_imply_that_access_was_ever_granted():
    """The 2026-10-06 note says the listing was read with an authorized account; the listing proves no access."""
    document = _load(MULTITRUST)
    (item,) = [item for item in _owned(document) if item["kind"] == "source_audit_access"]
    note = " ".join(item["note"].split())
    assert not re.search(r"\bstill\b", note), "no earlier refusal is recorded, so the gate cannot be 'still' closed"
    assert "2026-10-06" in note and "listing" in note
    assert "does not show that access was ever granted" in note
    assert "still" not in item["source_identity_status"]


def test_while_the_multitrust_gate_stands_its_blockers_carry_a_dated_observation():
    coverage = _load(MULTITRUST)["coverage"]
    if coverage["access"] != "gated":
        pytest.skip("the gate this receipt documents no longer stands for this entry")
    dated = [text for text in coverage["blockers"] if "2026-10-08" in text]
    assert len(dated) == 1, coverage["blockers"]
    assert "403" in dated[0] and "terms" in dated[0] and "2026-10-06" in dated[0]
