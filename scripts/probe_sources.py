#!/usr/bin/env python3
"""Probe registry source URLs with bounded HEAD requests and record what each says.

Read-only: reads registry/datasets/*.yaml and never writes it. At most a HEAD (or a 1-byte ranged GET) per URL;
no payload is downloaded and no credentials are sent. `--blocked` selects entries whose access is gated or by
request, or whose blockers describe a gate, an outage or an empty response, and probes `source_url` plus every
URL in `source_audit_*` evidence once.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import yaml
from dataset_atlas.registry.source_probe import probe_url

GATED_ACCESS = {"gated", "request_required", "author_request_required"}
BLOCKER_PATTERN = re.compile(r"gated|outage|time[sd]? out|timeout|unreachable|did not answer|access request|"
                             r"publisher request|empty (?:html )?(?:body|response)|acceptance of|registration", re.I)
NOTE = ("Each probe is a HEAD, or a 1-byte ranged GET after 403/405/501; no payload was downloaded and no credentials "
        "were sent. `unreachable` is a transient observation, never a gate and never an implementation gap.")


def load_entries(root):
    entries = {}
    for path in sorted((Path(root) / "registry/datasets").glob("*.yaml")):
        entry = yaml.safe_load(path.read_text())
        entries[entry["id"]] = entry
    return entries


def blocked_ids(entries):
    def blocked(entry):
        coverage = entry.get("coverage") or {}
        return coverage.get("access") in GATED_ACCESS or any(BLOCKER_PATTERN.search(text) for text in coverage.get("blockers") or [])
    return sorted(dataset_id for dataset_id, entry in entries.items() if blocked(entry))


def entry_urls(entry):
    if entry.get("source_url"):
        yield entry["source_url"], "source_url"
    for item in entry.get("evidence") or []:
        if str(item.get("kind", "")).startswith("source_audit_"):
            for url in [item.get("url"), *(item.get("urls") or [])]:
                if url:
                    yield url, item["kind"]


def collect_targets(entries, dataset_ids, extras):
    found = {}

    def add(url, dataset_id, origin):
        target = found.setdefault(url, {"url": url, "dataset_ids": set(), "origins": set()})
        target["dataset_ids"].add(dataset_id)
        target["origins"].add(origin)
    for dataset_id in dataset_ids:
        if dataset_id not in entries:
            raise ValueError(f"No registry entry named {dataset_id}")
        for url, origin in entry_urls(entries[dataset_id]):
            add(url, dataset_id, origin)
    for dataset_id, url in extras:
        if dataset_id not in entries:
            raise ValueError(f"No registry entry named {dataset_id}")
        add(url, dataset_id, "--extra")
    return [{**target, "dataset_ids": sorted(target["dataset_ids"]), "origins": sorted(target["origins"])}
            for _, target in sorted(found.items())]


def run_probes(targets, *, timeout, attempts, workers):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        outcomes = list(executor.map(lambda target: probe_url(target["url"], timeout=timeout, attempts=attempts), targets))
    probes = []
    for target, outcome in zip(targets, outcomes):
        probes.append({**asdict(outcome), "dataset_ids": target["dataset_ids"], "origins": target["origins"]})
        print(f"{outcome.status:<18} {outcome.http_status or '-':>4}  {outcome.url}  [{', '.join(target['dataset_ids'])}]", flush=True)
    return probes


def repeated_probes(runs):
    history = {}
    for run in runs:
        for probe in run["probes"]:
            history.setdefault(probe["url"], []).append({key: probe[key] for key in ("checked_at_utc", "status", "http_status")})
    return [{"url": url, "probes": probes} for url, probes in sorted(history.items()) if len(probes) > 1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--dataset", nargs="+", default=[], metavar="ID", help="registry entries to probe")
    parser.add_argument("--blocked", action="store_true", help="probe every entry whose access or blockers indicate a gate, request or outage")
    parser.add_argument("--extra", nargs=2, action="append", default=[], metavar=("ID", "URL"),
                        help="also probe a URL the registry does not record, attached to entry ID")
    parser.add_argument("--output", type=Path, default=Path("reports/source-reprobe-20261008.json"))
    parser.add_argument("--append", action="store_true", help="add this run to an existing receipt instead of replacing it")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if not (args.dataset or args.blocked or args.extra):
        parser.error("choose --dataset ID ..., --blocked or --extra ID URL")
    entries = load_entries(args.root)
    selected = sorted({*args.dataset, *(blocked_ids(entries) if args.blocked else [])})
    try:
        targets = collect_targets(entries, selected, [tuple(pair) for pair in args.extra])
    except ValueError as error:
        parser.error(str(error))
    run = {"generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "mode": {"blocked": args.blocked, "datasets": args.dataset,
                    "extras": [{"dataset_id": dataset_id, "url": url} for dataset_id, url in args.extra]},
           "settings": {"timeout": args.timeout, "attempts": args.attempts},
           "dataset_ids": sorted({dataset_id for target in targets for dataset_id in target["dataset_ids"]}),
           "probes": run_probes(targets, timeout=args.timeout, attempts=args.attempts, workers=args.workers)}
    runs = json.loads(args.output.read_text())["runs"] if args.append and args.output.exists() else []
    runs.append(run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"tool": "scripts/probe_sources.py", "note": NOTE, "runs": runs,
                                       "repeated_probes": repeated_probes(runs)}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
