"""scripts/probe_sources.py selects registry entries read-only and records one outcome per distinct URL."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from dataset_atlas.registry.source_probe import ProbeOutcome

spec = importlib.util.spec_from_file_location("probe_sources", Path(__file__).parents[2] / "scripts/probe_sources.py")
probe_sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_sources)


def _entry(dataset_id, access="public", blockers=(), source_url=None, evidence=()):
    return {"id": dataset_id, "name": dataset_id, "source_url": source_url, "evidence": list(evidence),
            "coverage": {"access": access, "blockers": list(blockers)}}


def _registry(tmp_path, *entries):
    directory = tmp_path / "registry/datasets"
    directory.mkdir(parents=True)
    for entry in entries:
        (directory / f"{entry['id']}.yaml").write_text(yaml.safe_dump(entry))
    return tmp_path


def _fake_probe(url, **kwargs):
    return ProbeOutcome(url=url, status="unreachable" if "slow" in url else "reachable", http_status=None if "slow" in url else 200,
                        content_length=None, content_type=None, etag=None, content_digest=None, final_host="h",
                        error=None, elapsed_s=0.01, checked_at_utc="2026-10-08T00:00:00Z")


def test_blocked_selects_by_gated_access_or_blocker_text_and_ignores_public_entries(tmp_path):
    root = _registry(
        tmp_path,
        _entry("gate", access="gated"), _entry("ask", access="request_required"), _entry("author", access="author_request_required"),
        _entry("slow", blockers=["The official HTTPS endpoints time out in the bounded probe."]),
        _entry("outage", blockers=["The host did not answer a HEAD request; an upstream outage."]),
        _entry("drive", blockers=["A request returned an empty HTML body."]),
        _entry("fine", blockers=["Rights are not reviewed."]), _entry("open"))
    entries = probe_sources.load_entries(root)
    assert probe_sources.blocked_ids(entries) == ["ask", "author", "drive", "gate", "outage", "slow"]


def test_urls_come_from_source_url_and_every_source_audit_url_deduplicated_across_entries():
    shared = "https://example.org/shared"
    a = _entry("a", source_url=shared, evidence=[
        {"kind": "source_audit_access", "url": shared}, {"kind": "source_audit_rights", "url": "https://example.org/rights"},
        {"kind": "source_audit_related_links", "urls": ["https://example.org/r1", "https://example.org/r2"]},
        {"kind": "source_access_probe", "url": "https://example.org/not-audit"}, {"kind": "derived_facet", "field": "modalities"},
        {"kind": "source_audit_access", "note": "no url"}])
    b = _entry("b", source_url="https://example.org/b", evidence=[{"kind": "source_audit_release", "url": shared}])
    targets = probe_sources.collect_targets({"a": a, "b": b}, ["a", "b"], extras=[])
    by_url = {item["url"]: item for item in targets}
    assert sorted(by_url) == ["https://example.org/b", "https://example.org/r1", "https://example.org/r2",
                              "https://example.org/rights", shared]
    assert by_url[shared]["dataset_ids"] == ["a", "b"]
    assert by_url[shared]["origins"] == ["source_audit_access", "source_audit_release", "source_url"]
    assert by_url["https://example.org/r1"]["origins"] == ["source_audit_related_links"]


def test_extra_urls_attach_to_a_registry_entry_and_unknown_ids_are_rejected():
    entries = {"broden": _entry("broden", source_url="https://example.org/b")}
    targets = probe_sources.collect_targets(entries, [], extras=[("broden", "https://example.org/data/x.zip")])
    assert targets == [{"url": "https://example.org/data/x.zip", "dataset_ids": ["broden"], "origins": ["--extra"]}]
    with pytest.raises(ValueError, match="nope"):
        probe_sources.collect_targets(entries, ["nope"], extras=[])
    with pytest.raises(ValueError, match="nope"):
        probe_sources.collect_targets(entries, [], extras=[("nope", "https://example.org/x")])


def test_run_writes_a_receipt_with_one_outcome_per_url_and_never_touches_the_registry(tmp_path, monkeypatch):
    shared = "https://example.org/shared"
    root = _registry(tmp_path,
                     _entry("a", access="gated", source_url=shared, evidence=[{"kind": "source_audit_access", "url": "https://slow.example.org/x"}]),
                     _entry("b", access="gated", source_url=shared))
    before = {path.name: path.read_bytes() for path in (root / "registry/datasets").iterdir()}
    monkeypatch.setattr(probe_sources, "probe_url", _fake_probe)
    output = root / "reports/source-reprobe.json"
    assert probe_sources.main(["--root", str(root), "--blocked", "--output", str(output)]) == 0
    assert {path.name: path.read_bytes() for path in (root / "registry/datasets").iterdir()} == before
    receipt = json.loads(output.read_text())
    (run,) = receipt["runs"]
    assert run["mode"] == {"blocked": True, "datasets": [], "extras": []} and run["dataset_ids"] == ["a", "b"]
    assert [probe["url"] for probe in run["probes"]] == [shared, "https://slow.example.org/x"]
    ok, slow = run["probes"]
    assert (slow["status"], slow["http_status"], slow["dataset_ids"], slow["origins"]) == ("unreachable", None, ["a"], ["source_audit_access"])
    assert ok["dataset_ids"] == ["a", "b"] and ok["checked_at_utc"] == "2026-10-08T00:00:00Z"
    assert str(root) not in output.read_text() and "/home/" not in output.read_text()


def test_append_adds_a_run_and_summarises_urls_probed_more_than_once(tmp_path, monkeypatch):
    root = _registry(tmp_path, _entry("a", source_url="https://slow.example.org/x"))
    monkeypatch.setattr(probe_sources, "probe_url", _fake_probe)
    output = root / "receipt.json"
    arguments = ["--root", str(root), "--dataset", "a", "--output", str(output)]
    assert probe_sources.main(arguments) == 0
    monkeypatch.setattr(probe_sources, "probe_url", lambda url, **kw: replace(_fake_probe(url), checked_at_utc="2026-10-08T00:10:00Z"))
    assert probe_sources.main(arguments + ["--append"]) == 0
    receipt = json.loads(output.read_text())
    assert len(receipt["runs"]) == 2
    (history,) = receipt["repeated_probes"]
    assert history["url"] == "https://slow.example.org/x"
    assert [(item["checked_at_utc"], item["status"]) for item in history["probes"]] == [
        ("2026-10-08T00:00:00Z", "unreachable"), ("2026-10-08T00:10:00Z", "unreachable")]
    assert probe_sources.main(arguments) == 0 and len(json.loads(output.read_text())["runs"]) == 1


def test_a_selection_is_required(tmp_path, capsys):
    with pytest.raises(SystemExit):
        probe_sources.main(["--root", str(tmp_path), "--output", str(tmp_path / "x.json")])


def test_note_is_recorded_on_the_run_only_when_given(tmp_path, monkeypatch):
    root = _registry(tmp_path, _entry("a", source_url="https://example.org/x"))
    monkeypatch.setattr(probe_sources, "probe_url", _fake_probe)
    output = root / "receipt.json"
    arguments = ["--root", str(root), "--dataset", "a", "--output", str(output)]
    assert probe_sources.main(arguments + ["--note", "supersedes the earlier probe"]) == 0
    assert json.loads(output.read_text())["runs"][0]["note"] == "supersedes the earlier probe"
    assert probe_sources.main(arguments) == 0
    assert "note" not in json.loads(output.read_text())["runs"][0]
