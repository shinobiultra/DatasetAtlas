"""scripts/refresh_candidate_sources.py refreshes source evidence and never touches identity, release, preview, adapter or snapshot."""
import copy
import importlib.util
import json
import threading
import time
from pathlib import Path

import pytest
import yaml

from dataset_atlas.registry.source_probe import ProbeOutcome

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/refresh_candidate_sources.py"
spec = importlib.util.spec_from_file_location("refresh_candidate_sources", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
refresh = module.refresh

TODAY = "2026-10-08"
DATA_URL = "https://example.org/files/demo.zip"
PAGE_URL = "https://example.org/demo"
HTTP = {"reachable": 200, "empty_response": 200, "gated_or_forbidden": 403, "gone": 404, "server_error": 503,
        "unreachable": None, "redirect_refused": None}


def outcome(url=DATA_URL, status="reachable", *, http_status="default", content_length=None, content_type="application/zip",
            etag=None, content_digest=None, error=None, final_host="example.org"):
    return ProbeOutcome(url=url, status=status, http_status=HTTP[status] if http_status == "default" else http_status,
                        content_length=content_length, content_type=content_type, etag=etag, content_digest=content_digest,
                        final_host=final_host, error=error, elapsed_s=0.1, checked_at_utc="2026-10-08T10:00:00Z")


def pinned(url=DATA_URL, **kwargs):
    return outcome(url, content_length=1234, etag='"abc123"', **kwargs)


def entry(access="public", source_url=DATA_URL, evidence=(), blockers=("Adapter and preview are not implemented.",), **coverage):
    return {
        "schema_version": "1.0", "id": "demo", "name": "Demo", "aliases": [], "description": "A demo candidate.",
        "paper_ids": ["paper-1"], "release": "unresolved", "adapter": "structured", "adapter_config": {},
        "coverage": {"identity": "candidate", "source": "verified", "access": access, "adapter": "not_started",
                     "preview": "none", "complete_data": "unimplemented", "publication": "not_reviewed", "preview_count": 0,
                     "unit": "example", "blockers": list(blockers), **coverage},
        "rights": {"records": "not_reviewed", "annotations": "not_reviewed", "images": "not_reviewed"},
        "evidence": [{"kind": "corpus_mention", "evidence_id": "evidence-1", "paper_id": "paper-1", "page": 3},
                     {"kind": "source_audit_access", "url": PAGE_URL, "checked_on": "2026-09-22", "note": "audited"}, *evidence],
        "source_url": source_url}


def protected(candidate):
    coverage = candidate["coverage"]
    return copy.deepcopy((coverage["identity"], coverage["preview"], coverage["adapter"], candidate["release"],
                          candidate.get("snapshot_id")))


def only_evidence_and_blockers_differ(before, after):
    def stripped(data):
        data = copy.deepcopy(data)
        data.pop("evidence")
        data["coverage"].pop("blockers")
        return data
    return stripped(before) == stripped(after)


def refreshed(candidate, *outcomes, **kwargs):
    return refresh(candidate, list(outcomes), checked_on=TODAY, **kwargs)


# --- the contract of the refresh itself ---------------------------------------------------------------------------

@pytest.mark.parametrize("probe", [pinned(), outcome(status="gated_or_forbidden"), outcome(status="gone"),
                                   outcome(status="unreachable", error="ConnectTimeout"), outcome(status="server_error"),
                                   outcome(url=PAGE_URL, content_type="text/html")])
def test_refresh_never_touches_identity_release_preview_or_snapshot(probe):  # Review Focus 2
    candidate = entry(snapshot_id="demo-snapshot")
    before, whole = protected(candidate), copy.deepcopy(candidate)
    refreshed(candidate, probe)
    assert protected(candidate) == before
    assert only_evidence_and_blockers_differ(whole, candidate)


def test_a_change_to_any_other_field_is_refused_by_the_refresh_itself(monkeypatch):
    candidate = entry()
    original = module.classify

    def meddling(entry_, outcomes, *args, **kwargs):
        entry_["coverage"]["identity"] = "resolved"
        return original(entry_, outcomes, *args, **kwargs)
    monkeypatch.setattr(module, "classify", meddling)
    with pytest.raises(RuntimeError, match="identity"):
        refreshed(candidate, outcome())


def test_the_appended_evidence_has_exactly_the_recorded_shape():
    candidate = entry()
    result = refreshed(candidate, outcome(url=PAGE_URL, content_type="text/html", etag='W/"x"'))
    item = candidate["evidence"][-1]
    assert list(item) == ["kind", "url", "probe_status", "http_status", "checked_on", "note"]
    assert item["kind"] == "source_audit_refresh" and item["checked_on"] == TODAY
    assert item == result.evidence and result.appended and len(candidate["evidence"]) == 3
    assert item["note"].startswith(result.disposition + ":")


def test_reachable_url_without_digest_or_etag_is_public_unpinned():  # Review Focus 3
    candidate = entry()
    result = refreshed(candidate, outcome())
    assert result.disposition == "public_unpinned"
    assert candidate["evidence"][-1]["probe_status"] == "reachable"


def test_unreachable_probe_adds_evidence_but_keeps_prior_disposition():
    candidate = entry()
    result = refreshed(candidate, outcome(status="unreachable", error="ConnectTimeout: timed out"))
    assert result.disposition == "unchanged"
    assert candidate["evidence"][-1]["probe_status"] == "unreachable" and candidate["evidence"][-1]["http_status"] is None
    assert candidate["coverage"]["blockers"] == ["Adapter and preview are not implemented."]
    assert candidate["coverage"]["access"] == "public"


@pytest.mark.parametrize("status", ["unreachable", "server_error", "redirect_refused"])
@pytest.mark.parametrize("access", ["public", "unverified", "gated", "request_required"])
def test_a_transient_failure_never_becomes_a_gate_or_a_blocker(status, access):  # Ruling D, Review Focus 1
    candidate = entry(access=access)
    result = refreshed(candidate, outcome(status=status, content_length=5, etag='"strong"', content_digest="d" * 32))
    assert result.disposition == "unchanged" and result.blockers_added == ()
    assert candidate["coverage"]["blockers"] == ["Adapter and preview are not implemented."]
    assert candidate["coverage"]["access"] == access


def test_refresh_is_idempotent_for_the_same_checked_on_date():
    candidate = entry()
    first = refreshed(candidate, outcome())
    snapshot = copy.deepcopy(candidate)
    second = refreshed(candidate, outcome())
    assert first.appended and not second.appended and candidate == snapshot
    assert [item for item in candidate["evidence"] if item["kind"] == "source_audit_refresh"] == [first.evidence]
    assert second.evidence == first.evidence


def test_a_later_date_appends_a_new_item_and_keeps_the_history():
    candidate = entry()
    refresh(candidate, [outcome()], checked_on="2026-10-08")
    refresh(candidate, [outcome(status="gone")], checked_on="2026-11-01")
    dated = [(item["checked_on"], item["probe_status"]) for item in candidate["evidence"] if item["kind"] == "source_audit_refresh"]
    assert dated == [("2026-10-08", "reachable"), ("2026-11-01", "gone")]


def test_an_entry_with_no_url_records_that_nothing_was_probed_and_changes_nothing_else():
    candidate = entry(source_url=None)
    candidate["evidence"] = [item for item in candidate["evidence"] if item["kind"] == "corpus_mention"]
    result = refresh(candidate, [], checked_on=TODAY)
    assert result.disposition == "unchanged"
    assert candidate["evidence"][-1]["probe_status"] == "not_probed" and candidate["evidence"][-1]["url"] is None


# --- what counts as pinned (Ruling A) and as a data file (Ruling B) -----------------------------------------------

@pytest.mark.parametrize("probe, expected", [
    (outcome(content_digest="a" * 32), True),
    (outcome(etag='"abc"', content_length=10), True),
    (outcome(etag="abc", content_length=10), True),
    (outcome(etag='W/"abc"', content_length=10), False),
    (outcome(etag='"abc"', content_length=None), False),
    (outcome(etag=None, content_length=10), False),
    (outcome(), False),
    (outcome(etag='""', content_length=10), False),
])
def test_pin_rule_is_a_digest_or_a_strong_etag_with_a_length(probe, expected):
    assert module.is_pinned(probe) is expected


@pytest.mark.parametrize("status", ["gated_or_forbidden", "gone", "unreachable", "server_error", "empty_response", "redirect_refused"])
def test_a_digest_or_etag_on_a_non_reachable_outcome_is_never_a_pin(status):  # Ruling A
    probe = outcome(status=status, content_digest="a" * 32, etag='"abc"', content_length=10)
    assert not module.is_pinned(probe)
    result = refreshed(entry(), probe)
    assert result.disposition != "now_public_pinnable"


@pytest.mark.parametrize("content_type", ["text/html", "text/html; charset=utf-8", "application/xhtml+xml", "application/pdf", None, "image/png"])
def test_a_pinned_landing_page_or_document_is_not_now_public_pinnable(content_type):  # Ruling B
    candidate = entry(source_url=PAGE_URL)
    result = refreshed(candidate, outcome(PAGE_URL, content_type=content_type, etag='"strong"', content_length=900, content_digest="d" * 32))
    assert result.disposition == "public_unpinned"


@pytest.mark.parametrize("url, content_type", [
    ("https://example.org/a.zip", "application/zip"), ("https://example.org/a.tar.gz", "application/gzip"),
    ("https://example.org/download", "application/octet-stream"), ("https://huggingface.co/x/resolve/abc/data.parquet", "application/octet-stream"),
    ("https://example.org/a.csv", "text/plain; charset=utf-8"), ("https://example.org/a.jsonl", "text/plain")])
def test_a_pinned_archive_or_data_file_is_now_public_pinnable(url, content_type):
    candidate = entry(source_url=url)
    result = refreshed(candidate, outcome(url, content_type=content_type, etag='"strong"', content_length=77))
    assert result.disposition == "now_public_pinnable"
    assert result.deciding_url == url and candidate["evidence"][-1]["url"] == url
    assert "pin" in candidate["evidence"][-1]["note"]


def test_a_public_data_file_without_a_pin_is_public_unpinned_never_pinnable():
    assert refreshed(entry(), outcome(content_type="application/zip", etag='W/"weak"', content_length=10)).disposition == "public_unpinned"


def test_a_pinned_data_file_beats_a_landing_page_on_the_same_entry():
    candidate = entry()
    result = refreshed(candidate, outcome(PAGE_URL, content_type="text/html"), pinned())
    assert result.disposition == "now_public_pinnable" and result.deciding_url == DATA_URL


def test_a_landing_page_of_a_gated_entry_says_nothing_about_the_gate():  # BBQ-V: tree page 200, parquet 401
    candidate = entry(access="gated")
    result = refreshed(candidate, outcome(PAGE_URL, content_type="text/html"), outcome(status="gated_or_forbidden", http_status=401))
    assert result.disposition == "unchanged" and result.blockers_added == ()
    assert candidate["coverage"]["access"] == "gated"


@pytest.mark.parametrize("access", ["gated", "request_required", "author_request_required"])
def test_a_reachable_landing_page_never_moves_a_gated_entry_toward_public(access):
    assert refreshed(entry(access=access), outcome(PAGE_URL, content_type="text/html")).disposition == "unchanged"


def test_a_reachable_landing_page_does_not_stand_in_for_a_data_url_that_gave_no_answer():  # Broden: GitHub page 200, archives time out
    candidate = entry(access="public")
    result = refreshed(candidate, outcome(PAGE_URL, content_type="text/html"),
                       outcome(DATA_URL, status="unreachable", error="ConnectTimeout: timed out"))
    assert result.disposition == "unchanged" and result.basis == "data_url_not_reachable"
    assert candidate["evidence"][-1]["url"] == DATA_URL and candidate["evidence"][-1]["probe_status"] == "unreachable"
    assert result.blockers_added == () and candidate["coverage"]["access"] == "public"


@pytest.mark.parametrize("data", [outcome(DATA_URL, status="gone"), outcome(DATA_URL, content_type="text/html"),
                                  outcome(DATA_URL, status="empty_response", content_length=0)])
def test_a_data_url_that_is_gone_empty_or_answers_with_a_page_keeps_the_prior_state(data):
    result = refreshed(entry(), outcome(PAGE_URL, content_type="text/html"), data)
    assert result.disposition == "unchanged" and result.basis == "data_url_not_reachable"


def test_a_data_file_that_answers_without_a_pin_beside_a_landing_page_is_public_unpinned():
    result = refreshed(entry(), outcome(PAGE_URL, content_type="text/html"), outcome(DATA_URL, content_type="application/zip"))
    assert result.disposition == "public_unpinned" and result.basis == "data_file_unpinned"


# --- gates, removals, and answers that carry no information (Rulings C and D) -------------------------------------------

def test_a_gate_answer_on_an_entry_not_recorded_as_gated_is_now_gated_with_one_dated_blocker():
    candidate = entry(access="unverified")
    result = refreshed(candidate, outcome(status="gated_or_forbidden", http_status=403))
    assert result.disposition == "now_gated"
    assert len(result.blockers_added) == 1 and TODAY in result.blockers_added[0] and "403" in result.blockers_added[0]
    assert candidate["coverage"]["blockers"][-1] == result.blockers_added[0]
    assert candidate["coverage"]["access"] == "unverified"  # access is a reviewed field; only blocker text is edited


def test_a_refusing_paper_or_project_link_is_not_a_gate_on_the_dataset():
    candidate = entry(access="unverified", source_url=DATA_URL)
    result = refreshed(candidate, outcome(DATA_URL, content_type="application/zip"),
                       outcome("https://publisher.example/paper", status="gated_or_forbidden", http_status=403, content_type="text/html"))
    assert result.disposition == "public_unpinned" and result.blockers_added == ()
    only = refreshed(entry(access="unverified"), outcome("https://publisher.example/paper", status="gated_or_forbidden", http_status=403))
    assert only.disposition == "unchanged" and only.basis == "gate_on_non_data_url" and only.blockers_added == ()


def test_a_refusing_data_file_url_is_a_gate_even_when_it_is_not_the_source_url():
    candidate = entry(access="unverified", source_url=PAGE_URL)
    result = refreshed(candidate, outcome(PAGE_URL, content_type="text/html"),
                       outcome("https://example.org/files/part-0.parquet", status="gated_or_forbidden", http_status=401))
    assert result.disposition == "now_gated" and result.deciding_url.endswith("part-0.parquet")


def test_a_gate_answer_on_an_entry_already_recorded_as_gated_is_unchanged():
    candidate = entry(access="gated", blockers=["Access approval is not present."])
    result = refreshed(candidate, outcome(status="gated_or_forbidden", http_status=401))
    assert result.disposition == "unchanged" and candidate["coverage"]["blockers"] == ["Access approval is not present."]


def test_a_blocker_is_not_added_twice_for_the_same_date():
    candidate = entry(access="unverified")
    refreshed(candidate, outcome(status="gated_or_forbidden", http_status=403))
    again = refreshed(candidate, outcome(status="gated_or_forbidden", http_status=403))
    assert not again.appended and again.blockers_added == () and len(candidate["coverage"]["blockers"]) == 2


def test_the_reported_probe_of_a_gated_entry_is_the_reachable_page_the_note_speaks_about():
    candidate = entry(access="gated", source_url="https://example.org/gone")
    refreshed(candidate, outcome("https://example.org/gone", status="gone"), outcome(PAGE_URL, content_type="text/html"))
    item = candidate["evidence"][-1]
    assert (item["url"], item["probe_status"]) == (PAGE_URL, "reachable") and "1 gone" in item["note"]


@pytest.mark.parametrize("status", ["gone", "empty_response"])
def test_a_removed_or_empty_url_is_recorded_but_is_neither_a_gate_nor_a_gap(status):
    candidate = entry(access="gated")
    result = refreshed(candidate, outcome(status=status, http_status=404 if status == "gone" else 200, content_length=0 if status == "empty_response" else None))
    assert result.disposition == "unchanged" and result.blockers_added == ()
    assert candidate["evidence"][-1]["probe_status"] == status


def test_a_figshare_waf_challenge_is_no_information_and_keeps_the_prior_disposition():  # Ruling C
    waf = outcome("https://figshare.com/articles/media/Training_data/5483668", status="unreachable", http_status=202,
                  content_length=0, content_type="text/html", error="unexpected HTTP 202 (x-amzn-waf-action: challenge, a bot challenge, not an answer about the source)")
    candidate = entry(access="request_required", source_url=waf.url)
    result = refreshed(candidate, waf)
    assert result.disposition == "unchanged" and "no information" in candidate["evidence"][-1]["note"]
    assert "bot challenge" in candidate["evidence"][-1]["note"] and candidate["evidence"][-1]["http_status"] == 202


@pytest.mark.parametrize("host", ["drive.google.com", "drive.usercontent.google.com", "docs.google.com"])
def test_a_google_drive_page_is_no_information_even_when_it_answers_200(host):  # Ruling C
    url = f"https://{host}/uc?export=download&id=abc"
    candidate = entry(access="unverified", source_url=url)
    result = refreshed(candidate, outcome(url, content_type="text/html", content_length=2467, final_host=host))
    assert result.disposition == "unchanged" and "no information" in candidate["evidence"][-1]["note"]


def test_a_drive_page_that_carries_a_digest_is_still_not_a_pin():
    url = "https://drive.google.com/uc?export=download&id=abc"
    result = refreshed(entry(source_url=url), outcome(url, content_type="application/zip", etag='"x"', content_length=9, final_host="drive.usercontent.google.com"))
    assert result.disposition == "unchanged"


def test_the_deciding_probe_is_reported_but_every_url_is_tallied_in_the_note():
    candidate = entry(access="unverified")
    result = refreshed(candidate, outcome(PAGE_URL, content_type="text/html"), outcome("https://example.org/b", status="gone"),
                       outcome("https://example.org/c", status="unreachable", error="ConnectTimeout"))
    note = candidate["evidence"][-1]["note"]
    assert result.disposition == "public_unpinned"
    assert "3 URLs" in note and "1 reachable" in note and "1 gone" in note and "1 unreachable" in note


def test_the_primary_source_url_is_the_reported_probe_when_no_url_gave_information():
    candidate = entry(source_url=DATA_URL)
    refreshed(candidate, outcome(PAGE_URL, status="unreachable", error="ConnectTimeout"), outcome(DATA_URL, status="unreachable", error="timeout"))
    assert candidate["evidence"][-1]["url"] == DATA_URL and candidate["evidence"][-1]["probe_status"] == "unreachable"


def test_the_url_that_answered_is_the_reported_probe_when_the_primary_one_timed_out():
    candidate = entry(source_url=DATA_URL)
    refreshed(candidate, outcome(PAGE_URL, status="gone"), outcome(DATA_URL, status="unreachable", error="timeout"))
    assert candidate["evidence"][-1]["url"] == PAGE_URL and candidate["evidence"][-1]["probe_status"] == "gone"


# --- probes alone never decide a release (Step 5 is human reading) -------------------------------------------------------

@pytest.mark.parametrize("status", sorted(HTTP))
@pytest.mark.parametrize("access", ["public", "unverified", "gated"])
def test_probes_alone_never_produce_released_after_audit_or_still_unreleased(status, access):
    result = refreshed(entry(access=access), outcome(status=status, content_digest="d" * 32, etag='"e"', content_length=5))
    assert result.disposition in {"unchanged", "now_public_pinnable", "public_unpinned", "now_gated"}


def test_a_researched_disposition_recorded_today_is_honoured():
    audit = {"kind": "source_audit_release", "url": PAGE_URL, "checked_on": TODAY, "disposition": "still_unreleased",
             "note": "No public release located on the author's pages."}
    candidate = entry(evidence=[audit], source_url=None)
    result = refreshed(candidate, outcome(PAGE_URL, content_type="text/html"))
    assert result.disposition == "still_unreleased"
    assert candidate["evidence"][-1]["note"].startswith("still_unreleased:")
    assert candidate["coverage"]["access"] == "public"


def test_a_researched_disposition_from_an_earlier_date_is_not_reapplied():
    audit = {"kind": "source_audit_release", "url": PAGE_URL, "checked_on": "2026-09-22", "disposition": "still_unreleased"}
    assert refreshed(entry(evidence=[audit]), outcome()).disposition == "public_unpinned"


def test_a_researched_disposition_cannot_claim_a_pin():
    audit = {"kind": "source_audit_release", "url": PAGE_URL, "checked_on": TODAY, "disposition": "now_public_pinnable"}
    with pytest.raises(ValueError, match="now_public_pinnable"):
        refreshed(entry(evidence=[audit]), outcome())


def test_an_unknown_researched_disposition_is_refused():
    audit = {"kind": "source_audit_release", "url": PAGE_URL, "checked_on": TODAY, "disposition": "resolved"}
    with pytest.raises(ValueError, match="resolved"):
        refreshed(entry(evidence=[audit]), outcome())


# --- selection, observations, probing ---------------------------------------------------------------------------------------

class Fake:
    def __init__(self, dataset_id, preview_count, access, preview="none"):
        self.id = dataset_id
        self.coverage = type("Coverage", (), {"preview_count": preview_count, "access": access, "preview": preview})()


def test_selection_is_every_entry_without_a_preview_that_is_not_unreleased():
    datasets = [Fake("a", 0, "public"), Fake("b", 100, "public", "complete_target"), Fake("c", 0, "unreleased"),
                Fake("d", 0, "gated"), Fake("e", 5, "unverified", "local_only"), Fake("f", 3, "public", "none"),
                Fake("g", 0, "public", "local_only")]
    assert module.select_entries(datasets) == ["a", "d"]


def _receipt(tmp_path, runs):
    path = tmp_path / "reprobe.json"
    path.write_text(json.dumps({"runs": runs}))
    return path


def _probe_row(url, status, at, dataset_ids=("demo",), origins=("--extra",), http_status=200):
    return {**outcome(url, status=status, http_status=http_status).__dict__, "checked_at_utc": at,
            "dataset_ids": list(dataset_ids), "origins": list(origins)}


def test_the_latest_observation_per_extra_url_wins_and_older_runs_are_history(tmp_path):  # Ruling C
    url = "https://example.org/extra.zip"
    path = _receipt(tmp_path, [
        {"probes": [_probe_row(url, "empty_response", "2026-10-08T03:40:38Z"), _probe_row("https://example.org/own", "reachable", "2026-10-08T03:40:38Z", origins=("source_url",))]},
        {"probes": [_probe_row(url, "unreachable", "2026-10-08T04:14:40Z", http_status=None),
                    _probe_row("https://example.org/other", "reachable", "2026-10-08T04:14:40Z", dataset_ids=("unselected",))]}])
    observed = module.load_extra_observations(path, {"demo"})
    assert {item.url: item.status for item in observed["demo"]} == {url: "unreachable"}
    assert "unselected" not in observed


def test_missing_receipt_means_no_extra_observations(tmp_path):
    assert module.load_extra_observations(tmp_path / "absent.json", {"demo"}) == {}


def test_each_url_is_probed_once_and_a_host_never_has_two_requests_in_flight():
    urls = [f"https://one.example/{index}" for index in range(6)] + [f"https://two.example/{index}" for index in range(6)]
    urls += [urls[0], urls[1]]
    lock, active, worst, seen = threading.Lock(), {}, {"value": 0}, []

    def fake(url, **kwargs):
        host = url.split("/")[2]
        with lock:
            active[host] = active.get(host, 0) + 1
            worst["value"] = max(worst["value"], active[host])
            seen.append(url)
        time.sleep(0.01)
        with lock:
            active[host] -= 1
        return outcome(url)
    results = module.probe_all(urls, probe=fake, workers=4, host_delay=0.0)
    assert sorted(results) == sorted(set(urls)) and sorted(seen) == sorted(set(urls)) and worst["value"] == 1


# --- the driver ----------------------------------------------------------------------------------------------------------------

def _registry(tmp_path, *entries):
    directory = tmp_path / "registry/datasets"
    directory.mkdir(parents=True)
    for item in entries:
        (directory / f"{item['id']}.yaml").write_text(yaml.safe_dump(item, sort_keys=False, width=100))
    return tmp_path


def _named(dataset_id, **kwargs):
    item = entry(**kwargs)
    item["id"], item["name"] = dataset_id, dataset_id
    item["evidence"][1]["url"] = item["source_url"]  # the audited URL is the entry's own, so one fake answer decides
    return item


def _fake_probe(url, **kwargs):
    if "gone" in url:
        return outcome(url, status="gone")
    if "slow" in url:
        return outcome(url, status="unreachable", error="ConnectTimeout: timed out")
    if url.endswith(".zip"):
        return pinned(url)
    return outcome(url, content_type="text/html")


def _drive(tmp_path, **kwargs):
    return module.run(tmp_path, checked_on=TODAY, probe=_fake_probe, workers=2, host_delay=0.0,
                      json_path=tmp_path / "out.json", md_path=tmp_path / "out.md",
                      extra_path=tmp_path / "none.json", **kwargs)


def _tmp_catalogue(tmp_path):
    skipped = _named("unreleased-one", access="unreleased", source_url="https://example.org/unr")
    return _registry(
        tmp_path,
        _named("pinnable", source_url="https://example.org/pin.zip"),
        _named("landing", access="unverified", source_url="https://example.org/landing"),
        _named("dead", access="gated", source_url="https://example.org/gone"),
        _named("stalled", source_url="https://example.org/slow"),
        skipped)


def test_the_driver_edits_only_the_appended_lines_and_reports_every_selected_entry(tmp_path):
    root = _tmp_catalogue(tmp_path)
    before = {path.name: path.read_text() for path in (root / "registry/datasets").glob("*.yaml")}
    receipt = _drive(root)
    assert [item["dataset_id"] for item in receipt["entries"]] == ["dead", "landing", "pinnable", "stalled"]
    assert {item["dataset_id"]: item["disposition"] for item in receipt["entries"]} == {
        "dead": "unchanged", "landing": "public_unpinned", "pinnable": "now_public_pinnable", "stalled": "unchanged"}
    assert receipt["disposition_counts"] == {"unchanged": 2, "now_public_pinnable": 1, "public_unpinned": 1, "now_gated": 0,
                                             "released_after_audit": 0, "still_unreleased": 0}
    for path in (root / "registry/datasets").glob("*.yaml"):
        after = path.read_text()
        if path.stem == "unreleased-one":
            assert after == before[path.name]
            continue
        old, new = before[path.name].splitlines(), after.splitlines()
        assert [line for line in old if line not in new] == []
        data = yaml.safe_load(after)
        assert data["evidence"][-1]["kind"] == "source_audit_refresh" and data["coverage"]["identity"] == "candidate"
    assert receipt["now_public_pinnable"] == [{"dataset_id": "pinnable", "url": "https://example.org/pin.zip",
                                               "content_type": "application/zip", "content_length": 1234, "etag": '"abc123"',
                                               "content_digest": None}]


def test_rerunning_the_driver_for_the_same_date_changes_no_registry_file(tmp_path):
    root = _tmp_catalogue(tmp_path)
    _drive(root)
    once = {path.name: path.read_text() for path in (root / "registry/datasets").glob("*.yaml")}
    receipt = _drive(root)
    assert {path.name: path.read_text() for path in (root / "registry/datasets").glob("*.yaml")} == once
    assert not any(item["evidence_appended"] for item in receipt["entries"])


def test_a_dry_run_writes_neither_registry_files_nor_receipts(tmp_path):
    root = _tmp_catalogue(tmp_path)
    before = {path.name: path.read_text() for path in (root / "registry/datasets").glob("*.yaml")}
    receipt = _drive(root, dry_run=True)
    assert {path.name: path.read_text() for path in (root / "registry/datasets").glob("*.yaml")} == before
    assert not (root / "out.json").exists() and not (root / "out.md").exists()
    assert all(item["evidence_appended"] is False for item in receipt["entries"]) and receipt["dry_run"] is True


def test_the_receipts_hold_every_url_outcome_and_no_local_path_or_secret(tmp_path):
    root = _tmp_catalogue(tmp_path)
    _drive(root)
    written = json.loads((root / "out.json").read_text())
    stalled = next(item for item in written["entries"] if item["dataset_id"] == "stalled")
    assert stalled["urls"][0]["status"] == "unreachable" and stalled["urls"][0]["error"] == "ConnectTimeout: timed out"
    text = (root / "out.json").read_text() + (root / "out.md").read_text()
    assert str(tmp_path) not in text and "/home/" not in text and "token" not in text.lower()


def test_the_markdown_is_counts_then_one_table_of_entries(tmp_path):
    root = _tmp_catalogue(tmp_path)
    _drive(root)
    lines = (root / "out.md").read_text().splitlines()
    assert any("now_public_pinnable" in line and "1" in line for line in lines)
    rows = [line for line in lines if line.startswith("| `")]
    assert [row.split("|")[1].strip() for row in rows[-4:]] == ["`dead`", "`landing`", "`pinnable`", "`stalled`"]
    assert all(row.count("|") >= 5 for row in rows[-4:])
    by_entry = {row.split("|")[1].strip(): row for row in rows[-4:]}
    assert "no information" in by_entry["`stalled`"] and "pin" in by_entry["`pinnable`"] and "landing page" in by_entry["`landing`"]


def test_dataset_option_limits_the_entries_but_the_selection_rule_still_applies(tmp_path):
    root = _tmp_catalogue(tmp_path)
    receipt = _drive(root, dataset_ids=["landing", "unreleased-one"])
    assert [item["dataset_id"] for item in receipt["entries"]] == ["landing"]
