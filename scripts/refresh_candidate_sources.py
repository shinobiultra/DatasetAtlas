#!/usr/bin/env python3
"""Refresh the source evidence of catalogue entries that still have no preview, without deciding anything on a researcher's behalf.

Selects entries with no preview (as the merged registry reports it, so prepared work is honoured) whose access is not
`unreleased`; probes every URL their registry record carries (`source_url` and `source_audit_*` evidence) with
`probe_sources`' bounded probe (HEAD, or a 1-byte ranged GET; nothing downloaded, no credentials); and appends ONE
`source_audit_refresh` evidence item per entry. Identity, release, preview, adapter, snapshot, access and every other
field stay as reviewed: only the evidence list grows, plus one dated blocker line when a URL newly answers 401/403.

Rules the dispositions follow (each has a test):
- A URL is *pinned* only when its latest probe is `reachable` AND it carries a digest, or a strong ETag together with a
  known length. Validators on any other outcome are never a pin.
- `now_public_pinnable` additionally needs that URL to be a data file or archive, not an HTML landing page or document.
- A reachable landing page says nothing about whether the files are public, so it never moves a gated entry.
- A timeout, 5xx, WAF challenge or Google Drive page is no information: the prior state stands and is never a gate.
- `released_after_audit` and `still_unreleased` come only from a dated reading of public pages by the implementing agent
  (a `disposition` key on a `source_audit_*` item; not human-reviewed, not a probe), never from a probe. The latest reading
  dated on or before the run stands until a pinned data file appears; a page that merely answers 200 does not relabel it.
- The entry's own record can contradict "public" (a login, a request or terms form, a licence agreement, a gate, a recipe, an
  in-house cohort, an outage). A keyword rule over that record lists such signals on the receipt row; the label is unchanged.

    python scripts/refresh_candidate_sources.py [--dry-run] [--dataset ID ...]
"""
import argparse
import copy
import json
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_sources  # noqa: E402  (entry_urls: which URLs a registry entry records)

from dataset_atlas.registry import Registry  # noqa: E402
from dataset_atlas.registry.source_probe import ProbeOutcome, probe_url  # noqa: E402
from dataset_atlas.registry.yaml_edit import append_list_items  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHECKED_ON = "2026-10-08"
EVIDENCE_KIND = "source_audit_refresh"
DISPOSITIONS = ("unchanged", "now_public_pinnable", "public_unpinned", "now_gated", "released_after_audit", "still_unreleased")
GATED_ACCESS = frozenset({"gated", "request_required", "author_request_required"})
DRIVE_HOSTS = frozenset({"drive.google.com", "drive.usercontent.google.com", "docs.google.com"})
NO_INFORMATION_STATUSES = frozenset({"unreachable", "server_error", "redirect_refused"})
NOT_DATA_TYPES = frozenset({"text/html", "application/xhtml+xml", "application/pdf"})
DATA_TYPES = frozenset({
    "application/zip", "application/x-zip-compressed", "application/x-tar", "application/gzip", "application/x-gzip",
    "application/x-bzip2", "application/x-xz", "application/x-7z-compressed", "application/vnd.rar", "application/x-rar-compressed",
    "application/octet-stream", "binary/octet-stream", "application/x-compressed", "application/x-compressed-tar",
    "application/x-gtar", "application/vnd.apache.parquet", "application/x-parquet", "application/parquet", "text/csv",
    "text/tab-separated-values", "application/x-ndjson", "application/jsonl", "application/x-hdf5", "application/x-hdf",
    "application/x-netcdf"})
DATA_EXTENSIONS = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".gz", ".bz2", ".xz", ".7z", ".rar", ".parquet",
                   ".csv", ".tsv", ".jsonl", ".ndjson", ".json", ".h5", ".hdf5", ".npz", ".npy", ".arrow", ".feather")
PIN_RULE = ("pinned = latest status `reachable` and (a digest, or a strong ETag that does not start with W/ together with a known "
            "content length); `now_public_pinnable` also needs a data file or archive content type, never an HTML page or document")
NOTE = ("Each URL was probed by HEAD (or a 1-byte ranged GET); no payload was downloaded and no credentials were sent. "
        "`unreachable`, a WAF challenge and a Google Drive page are no information and keep the prior state. A reachable landing "
        "page is not evidence that the data is public. `released_after_audit` and `still_unreleased` come only from a dated reading of "
        "public pages by the implementing agent (not human-reviewed, not a probe); the latest such reading stands unless a pinned data "
        "file appears.")
LEGEND = {
    "unchanged": "the recorded state stands: no new information, or the answer says nothing about the files",
    "now_public_pinnable": "a data file answers without credentials and carries a pin; a candidate for integration only",
    "public_unpinned": "a recorded page answers without credentials and nothing on a data file is pinned; this does not establish that the data itself is public",
    "now_gated": "a source answered 401/403 (or an agent reading found a gate) on an entry not recorded as gated; unconfirmed",
    "released_after_audit": "an agent reading of public pages found a release; not human-reviewed, identity not verified",
    "still_unreleased": "an agent reading of public pages located no public release; not human-reviewed"}
RECORD_SIGNAL_RULE = ("case-insensitive keyword rule over the entry's own blockers, rights note and earlier source_audit_* notes "
                      "(never the refresh items); it lists what the record already says and never changes a disposition")
RECORD_SIGNALS = {name: re.compile(pattern, re.I) for name, pattern in {
    "login or registration": r"\blog[- ]?in\b|\bsign[- ]?in\b|\bregistration\b|\bregister(?:ed)?\b|account is required|credentials",
    "access request or terms": (r"\baccess (?:request|approval|agreement|application)|requires? (?:name|a request|an application|approval|a signed|agreement)"
                                r"|acceptance of|institutional email|\bapplication (?:form|process)|contact information|\bby request\b"
                                r"|request(?:ed)? (?:the )?(?:data|access|a copy|form)|author request|publisher request|request[- ]required"),
    "licence agreement": r"\bLDC\b|licen[cs]ed (?:web|download|subscription|access)|\blicen[cs]e agreement|\bdata (?:use )?agreement|\busage agreement|\bsubscription\b|\bagreement\b",
    "gated": r"(?<![Nn]ot )\bgated\b",
    "recipe, not a release": r"\brecipe\b|not a release|setup scripts|generated by",
    "in-house or no public release": r"in-house|\binternal\b|\bprivate\b|no public release|not publicly released|unreleased",
    "host outage": r"did not answer|no response|unresponsive|time[sd]? out|\btimeout\b|\boutage\b|\bunreachable\b"}.items()}


# --- reading one probe -------------------------------------------------------------------------------------------------

def _media_type(outcome: ProbeOutcome) -> str:
    return (outcome.content_type or "").split(";")[0].strip().lower()


def is_pinned(outcome: ProbeOutcome) -> bool:
    """Validators count only on a `reachable` answer: Task 2 also records them for error bodies."""
    if outcome.status != "reachable":
        return False
    if outcome.content_digest:
        return True
    etag = (outcome.etag or "").strip()
    return bool(etag.strip('"')) and not etag.startswith("W/") and outcome.content_length is not None


def is_data_file(outcome: ProbeOutcome) -> bool:
    """A reachable URL whose answer is a data container, not a landing page, document, image or unknown type."""
    kind = _media_type(outcome)
    if outcome.status != "reachable" or not kind or kind in NOT_DATA_TYPES or kind.startswith(("image/", "video/", "audio/")):
        return False
    return kind in DATA_TYPES or urlsplit(outcome.url).path.lower().endswith(DATA_EXTENSIONS)


def no_information_reason(outcome: ProbeOutcome) -> str | None:
    """Why this answer tells nothing about the source (and so keeps the prior state), or None when it does."""
    if "x-amzn-waf-action" in (outcome.error or ""):
        return "bot challenge"
    if outcome.status in NO_INFORMATION_STATUSES:
        return "transient failure" if outcome.status != "redirect_refused" else "redirect refused"
    hosts = {urlsplit(outcome.url).hostname, outcome.final_host}
    if outcome.status in ("reachable", "empty_response") and hosts & DRIVE_HOSTS:
        return "Google Drive page"
    return None


# --- one entry -------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Verdict:
    disposition: str
    basis: str
    deciding: ProbeOutcome | None
    reason: str
    blocker: str | None = None
    summary: str = ""
    reading: dict | None = None


@dataclass(frozen=True)
class RefreshResult:
    dataset_id: str
    disposition: str
    basis: str
    deciding_url: str | None
    evidence: dict
    appended: bool
    blockers_added: tuple[str, ...]
    summary: str = ""
    signals: tuple[str, ...] = ()
    reading: dict | None = None


def _primary(entry: dict, outcomes: list[ProbeOutcome]) -> ProbeOutcome | None:
    return next((item for item in outcomes if item.url == entry.get("source_url")), outcomes[0] if outcomes else None)


def _readings(entry: dict) -> list[dict]:
    """Evidence items carrying a `disposition`: dated readings of public pages made by the implementing agent."""
    return [item for item in entry.get("evidence") or []
            if str(item.get("kind", "")).startswith("source_audit_") and item.get("kind") != EVIDENCE_KIND and item.get("disposition")]


def _reading(entry: dict, checked_on: str) -> dict | None:
    """The latest reading dated on or before this run; a later-dated one is not yet in effect."""
    readings = _readings(entry)
    for item in readings:
        if item["disposition"] == "now_public_pinnable":
            raise ValueError("now_public_pinnable can only come from a pinned probe, not from a reading")
        if item["disposition"] not in DISPOSITIONS:
            raise ValueError(f"unknown disposition {item['disposition']!r}")
    current = [item for item in readings if str(item.get("checked_on")) <= checked_on]
    return sorted(current, key=lambda item: str(item.get("checked_on")))[-1] if current else None


def _todays_readings(entry: dict, checked_on: str) -> list[dict]:
    return [{key: item.get(key) for key in ("kind", "url", "checked_on", "note")} for item in entry.get("evidence") or []
            if str(item.get("kind", "")).startswith("source_audit_") and item.get("kind") != EVIDENCE_KIND
            and str(item.get("checked_on")) == checked_on]


def record_signals(entry: dict) -> tuple[str, ...]:
    """What the entry's own record already says that contradicts a plain "public": a login, request, licence, gate, recipe, in-house cohort or outage."""
    texts = [*(entry["coverage"].get("blockers") or []), str((entry.get("rights") or {}).get("note") or "")]
    for item in entry.get("evidence") or []:
        if str(item.get("kind", "")).startswith("source_audit_") and item.get("kind") != EVIDENCE_KIND:
            texts += [str(item.get("note") or ""), str(item.get("observation") or "")]
    return tuple(name for name, pattern in RECORD_SIGNALS.items() if any(pattern.search(text) for text in texts))


def _is_gate_relevant(entry: dict, outcome: ProbeOutcome) -> bool:
    """A 401/403 on the entry's own source URL or on a data-file URL; a refused paper link says nothing about the dataset."""
    return outcome.url == entry.get("source_url") or urlsplit(outcome.url).path.lower().endswith(DATA_EXTENSIONS)


def classify(entry: dict, outcomes: list[ProbeOutcome], checked_on: str = CHECKED_ON) -> Verdict:
    recorded_gated = entry["coverage"].get("access") in GATED_ACCESS
    primary = _primary(entry, outcomes)
    informative = [item for item in outcomes if no_information_reason(item) is None]
    reading = _reading(entry, checked_on)  # validated even when a pin makes it moot
    for item in informative:
        if is_pinned(item) and is_data_file(item):
            return Verdict("now_public_pinnable", "pinned_data_file", item,
                           "a data file answers without credentials and carries a pin (digest, or strong ETag with a length); "
                           "a candidate for integration only: identity of the data and rights are not verified.",
                           summary="data file with a pin (digest, or strong ETag and length).")
    if reading:
        today = str(reading.get("checked_on")) == checked_on
        note = str(reading.get("note") or "").strip()
        return Verdict(reading["disposition"], "researched" if today else "researched_earlier", None,
                       (f"read from public pages on {checked_on} by the implementing agent (the {reading['kind']} item of that date); "
                        "not human-reviewed and not a probe." if today else
                        f"carried from the {reading['kind']} reading of {reading.get('checked_on')} by the implementing agent (not human-reviewed); "
                        "this run's probes add no pinned data file."),
                       summary=f"Agent reading, not human-reviewed: " + ((note[:277] + "...") if len(note) > 280 else note),
                       reading={key: reading.get(key) for key in ("kind", "url", "checked_on", "note")})
    if not outcomes:
        return Verdict("unchanged", "no_url", None, "no URL is recorded for this entry, so nothing was probed.",
                       summary="no URL recorded, nothing probed.")
    gates = [item for item in informative if item.status == "gated_or_forbidden"]
    relevant = [item for item in gates if _is_gate_relevant(entry, item)]
    if relevant and not recorded_gated:
        item = relevant[0]
        return Verdict("now_gated", "gate_answer", item,
                       f"the source answered HTTP {item.http_status} without credentials (a single observation); whether the release is gated, "
                       "and on what terms, is unconfirmed.",
                       f"{checked_on} source probe: {item.url} answered HTTP {item.http_status} without credentials (single observation); "
                       "whether the release is gated is unconfirmed.",
                       f"HTTP {item.http_status} without credentials (single observation).")
    if gates and recorded_gated:
        return Verdict("unchanged", "gate_already_recorded", gates[0],
                       "a gate answer is already recorded for this entry, so the prior state stands.",
                       summary=f"HTTP {gates[0].http_status} re-observed; the recorded gate stands.")
    reachable = [item for item in informative if item.status == "reachable"]
    if gates and not reachable:  # only refusals that are not the source or a data file (those were handled above)
        return Verdict("unchanged", "gate_on_non_data_url", gates[0],
                       "the refusing URL is not the entry's source or a data file, so no gate is inferred and the prior state stands.",
                       summary=f"a non-data URL answered HTTP {gates[0].http_status}; no gate inferred.")
    if reachable and recorded_gated:
        return Verdict("unchanged", "landing_page_of_gated_entry", next((item for item in reachable if item is primary), reachable[0]),
                       "a reachable page says nothing about whether the files are public, so the prior state stands.",
                       summary="recorded gate unchanged; a reachable page says nothing about the files.")
    if reachable:
        data_probed = [item for item in outcomes if urlsplit(item.url).path.lower().endswith(DATA_EXTENSIONS)]
        if data_probed and not any(is_data_file(item) for item in informative):
            return Verdict("unchanged", "data_url_not_reachable", data_probed[0],
                           "a data-file URL did not answer as a data file (no answer, removed, empty or a page) and a reachable landing page "
                           "says nothing about the files, so the prior state stands.",
                           summary=f"data-file URL {data_probed[0].status.replace('_', ' ')}; the reachable page says nothing about the files.")
        chosen = next((item for item in reachable if item.url == entry.get("source_url")), reachable[0])
        basis = "data_file_unpinned" if is_data_file(chosen) else "landing_page"
        return Verdict("public_unpinned", basis, chosen,
                       "reachable without credentials, but nothing carries a pin (digest, or strong ETag with a length) on a data file, so no "
                       "release is pinned and public availability of the data itself is not established.",
                       summary="data file reachable but not pinned." if basis == "data_file_unpinned" else "landing page reachable; no data file, no pin.")
    if informative:
        answered = next((item for item in informative if item is primary), informative[0])
        return Verdict("unchanged", "gone_or_empty", answered,
                       "the URL answered as removed or empty (a single observation, neither a gate nor an implementation gap), so the prior state stands.",
                       summary=f"{answered.status.replace('_', ' ')} (HTTP {answered.http_status}), a single observation; prior state kept.")
    reasons = sorted({no_information_reason(item) or "" for item in outcomes})
    return Verdict("unchanged", "no_information", primary,
                   f"no information ({', '.join(reasons)}), which is never a gate and never an implementation gap by itself, so the prior state stands.",
                   summary=f"no information ({', '.join(reasons)}); prior state kept.")


def _tally(outcomes: list[ProbeOutcome]) -> str:
    if not outcomes:
        return ""
    counts = Counter(item.status for item in outcomes)
    parts = ", ".join(f"{count} {status.replace('_', ' ')}" for status, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))
    silent = sum(no_information_reason(item) is not None for item in outcomes)
    plural = "URL" if len(outcomes) == 1 else "URLs"
    return f" {len(outcomes)} {plural} probed (HEAD only): {parts}." + (f" {silent} of them gave no information." if silent else "")


def _changed_fields(before: dict, after: dict) -> list[str]:
    changed = [key for key in {*before, *after} if key not in ("evidence", "coverage") and before.get(key) != after.get(key)]
    for key in {*before["coverage"], *after["coverage"]} - {"blockers"}:
        if before["coverage"].get(key) != after["coverage"].get(key):
            changed.append(f"coverage.{key}")
    for key, extended in (("evidence", after.get("evidence") or []), ("blockers", after["coverage"].get("blockers") or [])):
        original = (before.get("evidence") if key == "evidence" else before["coverage"].get("blockers")) or []
        if extended[:len(original)] != original:
            changed.append(key)
    return sorted(changed)


def refresh(entry: dict, outcomes: list[ProbeOutcome], *, checked_on: str = CHECKED_ON) -> RefreshResult:
    """Append this date's `source_audit_refresh` item (and a dated blocker when a URL newly refuses) to `entry`, in place.

    Idempotent per `checked_on`: an entry that already holds an item for the date is left exactly as it is.
    """
    before = copy.deepcopy(entry)
    verdict = classify(entry, outcomes, checked_on)
    existing = next((item for item in entry.get("evidence") or [] if item.get("kind") == EVIDENCE_KIND and str(item.get("checked_on")) == checked_on), None)
    shown = verdict.deciding or _primary(entry, outcomes)
    item = existing or {
        "kind": EVIDENCE_KIND, "url": shown.url if shown else None, "probe_status": shown.status if shown else "not_probed",
        "http_status": shown.http_status if shown else None, "checked_on": checked_on,
        "note": f"{verdict.disposition}: {verdict.reason}{_tally(outcomes)}"}
    if existing is None:
        entry.setdefault("evidence", []).append(item)
        if verdict.blocker:
            entry["coverage"].setdefault("blockers", []).append(verdict.blocker)
    changed = _changed_fields(before, entry)
    if changed:
        raise RuntimeError(f"refresh changed fields it must not touch: {', '.join(changed)}")
    return RefreshResult(entry["id"], verdict.disposition, verdict.basis, verdict.deciding.url if verdict.deciding else (shown.url if shown else None),
                         item, existing is None, (verdict.blocker,) if verdict.blocker and existing is None else (), verdict.summary,
                         record_signals(before), verdict.reading)


# --- selection, observations, probing --------------------------------------------------------------------------------------

def select_entries(datasets) -> list[str]:
    """Entries with no preview in the merged view (prepared work counts) whose release is not paper-private."""
    return sorted(item.id for item in datasets
                  if item.coverage.preview_count == 0 and item.coverage.preview == "none" and item.coverage.access != "unreleased")


def load_extra_observations(path: Path, dataset_ids) -> dict[str, list[ProbeOutcome]]:
    """Latest observation of each URL that `probe_sources --extra` attached to a selected entry (older runs are history)."""
    path = Path(path)
    if not path.is_file():
        return {}
    latest: dict[tuple[str, str], dict] = {}
    for run in json.loads(path.read_text()).get("runs", []):
        for probe in run.get("probes", []):
            if "--extra" not in probe.get("origins", []):
                continue
            for dataset_id in probe.get("dataset_ids", []):
                key = (dataset_id, probe["url"])
                if dataset_id in dataset_ids and (key not in latest or probe["checked_at_utc"] >= latest[key]["checked_at_utc"]):
                    latest[key] = probe
    fields = ProbeOutcome.__dataclass_fields__
    observed: dict[str, list[ProbeOutcome]] = {}
    for (dataset_id, _), probe in sorted(latest.items()):
        observed.setdefault(dataset_id, []).append(ProbeOutcome(**{name: probe[name] for name in fields}))
    return observed


def _failed(url: str, error: Exception) -> ProbeOutcome:
    return ProbeOutcome(url=url, status="unreachable", http_status=None, content_length=None, content_type=None, etag=None,
                        content_digest=None, final_host=None, error=f"{type(error).__name__}: {error}", elapsed_s=0.0,
                        checked_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def probe_all(urls, *, probe=probe_url, workers: int = 4, host_delay: float = 1.0, timeout: float = 15.0,
              attempts: int = 2) -> dict[str, ProbeOutcome]:
    """One probe per distinct URL, at most one request in flight per host and `host_delay` seconds between a host's requests."""
    distinct = sorted(set(urls))
    host_of = {url: (urlsplit(url).hostname or "").lower() for url in distinct}
    locks = {host: threading.Lock() for host in set(host_of.values())}
    last = dict.fromkeys(locks, 0.0)
    position: Counter = Counter()
    order = []
    for url in distinct:  # interleave hosts so the workers are not all queued behind one host
        order.append((position[host_of[url]], host_of[url], url))
        position[host_of[url]] += 1

    def work(url: str) -> tuple[str, ProbeOutcome]:
        host = host_of[url]
        with locks[host]:
            pause = host_delay - (time.monotonic() - last[host])
            if pause > 0:
                time.sleep(pause)
            try:
                outcome = probe(url, timeout=timeout, attempts=attempts)
            except Exception as error:  # one malformed URL must not stop the other hundred
                outcome = _failed(url, error)
            last[host] = time.monotonic()
        return url, outcome
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return dict(executor.map(work, [url for *_, url in sorted(order)]))


# --- receipts --------------------------------------------------------------------------------------------------------------------

def _scrub(value, root: Path):
    if isinstance(value, str):
        return value.replace(str(root), "<repo>").replace(str(Path.home()), "<home>")
    return value


def _url_record(outcome: ProbeOutcome, origin: str, root: Path) -> dict:
    reason = no_information_reason(outcome)
    return {"url": outcome.url, "origin": origin, "status": outcome.status, "http_status": outcome.http_status,
            "content_type": outcome.content_type, "content_length": outcome.content_length, "etag": outcome.etag,
            "content_digest": outcome.content_digest, "final_host": outcome.final_host, "error": _scrub(outcome.error, root),
            "checked_at_utc": outcome.checked_at_utc, "pinned": is_pinned(outcome), "data_file": is_data_file(outcome),
            "no_information": reason}


def _markdown(receipt: dict) -> str:
    counts = receipt["disposition_counts"]
    lines = [f"# Candidate-source refresh, {receipt['checked_on']}", "",
             f"{len(receipt['entries'])} catalogue entries with no preview and a release that is not paper-private. "
             f"{NOTE}", "",
             "Dispositions: " + "; ".join(f"`{name}` {counts[name]}" for name in DISPOSITIONS) + ".", "",
             "Legend: " + "; ".join(f"`{name}` {LEGEND[name]}" for name in DISPOSITIONS) + ".", "",
             f"`Record also says` lists what the entry's own blockers, rights note and earlier audit notes already record (a login, a request or "
             f"terms form, a licence agreement, a gate, a recipe, an in-house cohort, an outage), found by a keyword rule; it never changes a "
             "disposition.", "",
             "| Entry | Recorded access | Disposition | Latest probe | Record also says | Note |", "| --- | --- | --- | --- | --- | --- |"]
    for item in receipt["entries"]:
        probe = "not probed" if item["probe_status"] == "not_probed" else f"{item['probe_status']} {item['http_status'] or '-'}"
        more = f" (+{len(item['urls']) - 1} URL{'s' if len(item['urls']) > 2 else ''})" if len(item["urls"]) > 1 else ""
        summary = item["summary"]
        if item["agent_readings"] and item["basis"] not in ("researched", "researched_earlier"):
            summary += " An agent reading of public pages is recorded on the entry (not human-reviewed)."
        signals = "; ".join(item["record_signals"]) or "-"
        lines.append(f"| `{item['dataset_id']}` | {item['access']} | {item['disposition']} | {probe}{more} | {signals} | {summary.replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def run(root: Path, *, checked_on: str = CHECKED_ON, probe=probe_url, workers: int = 4, host_delay: float = 1.0,
        timeout: float = 15.0, attempts: int = 2, dry_run: bool = False, dataset_ids=None, json_path: Path | None = None,
        md_path: Path | None = None, extra_path: Path | None = None) -> dict:
    root = Path(root).resolve()
    registry = Registry(root)
    selected = select_entries(registry.datasets())
    if dataset_ids:
        unknown = sorted(set(dataset_ids) - set(registry.ids()))
        if unknown:
            raise ValueError(f"No registry entry named {', '.join(unknown)}")
        selected = [dataset_id for dataset_id in selected if dataset_id in set(dataset_ids)]
    entries = probe_sources.load_entries(root)
    extras = load_extra_observations(extra_path, set(selected)) if extra_path else {}
    recorded: dict[str, list[tuple[str, str]]] = {}
    for dataset_id in selected:
        seen: dict[str, str] = {}
        for url, origin in probe_sources.entry_urls(entries[dataset_id]):
            seen.setdefault(url, origin)
        recorded[dataset_id] = list(seen.items())
    outcomes = probe_all([url for pairs in recorded.values() for url, _ in pairs], probe=probe, workers=workers,
                         host_delay=host_delay, timeout=timeout, attempts=attempts)
    records: list[dict] = []
    for dataset_id in selected:
        entry = entries[dataset_id]
        observed = [(outcomes[url], origin) for url, origin in recorded[dataset_id]]
        observed += [(item, "source-reprobe --extra") for item in extras.get(dataset_id, []) if item.url not in {url for url, _ in recorded[dataset_id]}]
        path = root / f"registry/datasets/{dataset_id}.yaml"
        original = path.read_text()
        result = refresh(entry, [item for item, _ in observed], checked_on=checked_on)
        if result.appended and not dry_run:
            edited = append_list_items(original, ("evidence",), [result.evidence])
            if result.blockers_added:
                edited = append_list_items(edited, ("coverage", "blockers"), list(result.blockers_added))
            if yaml.safe_load(edited) != entry:
                raise RuntimeError(f"{dataset_id}: the edited file does not match the refreshed entry")
            path.write_text(edited)
        records.append({
            "dataset_id": dataset_id, "access": entry["coverage"].get("access"), "disposition": result.disposition, "basis": result.basis,
            "evidence_appended": result.appended and not dry_run, "blockers_added": list(result.blockers_added),
            "deciding_url": result.deciding_url, "probe_status": result.evidence["probe_status"], "http_status": result.evidence["http_status"],
            "summary": result.summary, "note": result.evidence["note"], "record_signals": list(result.signals),
            "agent_readings": _todays_readings(entry, checked_on), "reading": result.reading, "urls": [_url_record(item, origin, root) for item, origin in observed]})
    pinnable: list[dict] = []
    for record in records:
        if record["disposition"] == "now_public_pinnable":
            hit = next(item for item in record["urls"] if item["url"] == record["deciding_url"])
            pinnable.append({"dataset_id": record["dataset_id"], "url": hit["url"], "content_type": hit["content_type"],
                             "content_length": hit["content_length"], "etag": hit["etag"], "content_digest": hit["content_digest"]})
    released = [{"dataset_id": record["dataset_id"], "url": record["reading"]["url"], "note": record["note"],
                 "caveat": f"{record['reading']['note']} (Agent reading of {record['reading']['checked_on']}; not human-reviewed; "
                           "the identity of the release is not verified.)"}
                for record in records if record["disposition"] == "released_after_audit" and record["reading"]]
    receipt = {
        "tool": "scripts/refresh_candidate_sources.py", "checked_on": checked_on,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "dry_run": dry_run,
        "note": NOTE, "pin_rule": PIN_RULE, "legend": LEGEND, "record_signal_rule": RECORD_SIGNAL_RULE,
        "selection": {"rule": "merged coverage preview_count == 0 and preview == none and access != unreleased", "count": len(selected)},
        "settings": {"timeout": timeout, "attempts": attempts, "workers": workers, "host_delay_s": host_delay},
        "disposition_counts": {name: sum(record["disposition"] == name for record in records) for name in DISPOSITIONS},
        "now_public_pinnable": pinnable, "released_after_audit": released, "entries": records}
    if not dry_run:
        for path, text in ((json_path, json.dumps(receipt, indent=2) + "\n"), (md_path, _markdown(receipt))):
            if path:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(text)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--checked-on", default=CHECKED_ON)
    parser.add_argument("--dataset", nargs="+", metavar="ID", help="limit to these entries (the selection rule still applies)")
    parser.add_argument("--dry-run", action="store_true", help="probe and classify, but write no registry file and no receipt")
    parser.add_argument("--output-json", type=Path, default=Path("reports/candidate-source-refresh-20261008.json"))
    parser.add_argument("--output-md", type=Path, default=Path("reports/candidate-source-refresh-20261008.md"))
    parser.add_argument("--extra-observations", type=Path, default=Path("reports/source-reprobe-20261008.json"),
                        help="receipt whose --extra URLs (not recorded in the registry) are read as the latest observation")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--host-delay", type=float, default=1.0, help="seconds between two requests to the same host")
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    root = args.root.resolve()
    try:
        receipt = run(root, checked_on=args.checked_on, workers=args.workers, host_delay=args.host_delay, timeout=args.timeout,
                      attempts=args.attempts, dry_run=args.dry_run, dataset_ids=args.dataset, json_path=root / args.output_json,
                      md_path=root / args.output_md, extra_path=root / args.extra_observations)
    except ValueError as error:
        parser.error(str(error))
    for record in receipt["entries"]:
        print(f"{record['disposition']:<20} {record['probe_status']:<18} {record['dataset_id']}", flush=True)
    print(json.dumps(receipt["disposition_counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
