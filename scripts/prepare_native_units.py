#!/usr/bin/env python3
"""Prepare retained PATA/MultiTrust native units with zero network transfer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dataset_atlas.preparation import atomic
from dataset_atlas.preparation.native_units import prepare_multitrust_inventory, prepare_pata_preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dataset", choices=["pata", "multitrust", "all"], default="all")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--max-output-bytes", type=int, default=1_500_000_000)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    if args.activate and not args.execute:
        parser.error("--activate requires --execute")
    if not 1 <= args.max_output_bytes <= 1_500_000_000:
        parser.error("output budget must be between 1 and 1500000000 bytes")
    names = ["pata", "multitrust"] if args.dataset == "all" else [args.dataset]
    ledger_path = args.ledger if args.ledger is None or args.ledger.is_absolute() else args.root / args.ledger
    previous = json.loads(ledger_path.read_text()) if ledger_path and ledger_path.is_file() else None
    ledger = {"lane": "native-units", "download_limit_bytes": 0,
              "output_limit_bytes": args.max_output_bytes, "downloaded_bytes": 0,
              "plans": [], "results": [], "status": "planning"}
    if previous:
        ledger["previous_runs"] = [*previous.get("previous_runs", []),
                                   {key: value for key, value in previous.items() if key != "previous_runs"}]
    historical_output = sum(sum(result.get("new_output_bytes", result.get("output_bytes", 0)) for result in run.get("results", []))
                            for run in ledger.get("previous_runs", []))
    ledger["historical_new_output_bytes"] = historical_output

    def save():
        if args.ledger:
            path = args.ledger if args.ledger.is_absolute() else args.root / args.ledger
            if not path.resolve().is_relative_to(args.root.resolve()):
                raise ValueError("Budget ledger must stay inside the workspace")
            atomic(path, ledger)

    remaining = args.max_output_bytes - historical_output
    for name in names:
        function = prepare_pata_preview if name == "pata" else prepare_multitrust_inventory
        budget = min(100_000_000, remaining) if name == "pata" and len(names) > 1 else remaining
        plan = function(args.root, max_output_bytes=budget)
        ledger["plans"].append({**plan, "output_limit_bytes": budget})
        save()
        if args.execute:
            ledger["status"] = "preparing"
            save()
            try:
                result = function(args.root, execute=True, activate=args.activate, max_output_bytes=budget)
            except Exception as error:
                ledger["status"] = "failed"
                # Exception text may include upstream paths/content; report only
                # its type here. The caller retains the local diagnostic trace.
                ledger["error_type"] = type(error).__name__
                save()
                raise
            ledger["results"].append(result)
            remaining -= result["new_output_bytes"]
            save()
    ledger["status"] = "completed" if args.execute else "planned"
    ledger["output_bytes"] = sum(item["output_bytes"] for item in ledger["results"])
    ledger["cumulative_new_output_bytes"] = historical_output + sum(item["new_output_bytes"] for item in ledger["results"])
    save()
    print(json.dumps(ledger, indent=2))


if __name__ == "__main__":
    main()
