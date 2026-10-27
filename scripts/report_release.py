#!/usr/bin/env python3
"""Generate compact release reports from active catalogue metadata, without reading records.

A draft is the default. Only --verified can mark completion, and its proof must bind
both the current release sources and the current active catalogue. --fingerprint
prints the two bindings needed by that proof without writing reports.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import tomllib
from urllib.parse import urlsplit

import yaml

from dataset_atlas.registry import Registry, _pack_dataset

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CHECKS = (
    "python_tests", "frontend_tests", "browser_tests", "frontend_build",
    "publication_validation", "catalogue_validation", "native_index_checks",
    "preview_media_checks", "distribution_build", "clean_install",
    "portable_sample_bundle", "acceptance_traceability", "analysis_runtime",
    "cold_source_preparation", "storage_cleanup", "independent_review",
)
CSV_COLUMNS = (
    "dataset_id", "name", "release", "snapshot_id", "unit", "source_url",
    "identity", "access", "adapter", "preview", "preview_count", "declared_source_count",
    "complete_data", "local_index_scope", "local_index_count", "publication",
    "recipe_sha256", "preview_pack_sha256", "index_manifest_sha256",
)
JSON_STRING = re.compile(rb'"[^"\\]*(?:\\.[^"\\]*)*"')
JSON_TOKEN = re.compile(rb'"[^"\\]*(?:\\.[^"\\]*)*"|[][{}:,]')
LIMITATIONS = """# Source scope, rights and interpretation

The release's software verification applies to the supported catalogue and the declared
source populations. Each dataset's release, snapshot, local preview and local index
scope are listed in [dataset_coverage.csv](dataset_coverage.csv); source pins and
population descriptions are in [catalogue-sources.json](catalogue-sources.json).

- A source release identifies available data. Paper mentions do not prove the exact
  historical experiment subset, and automated checks do not confer human or scientific
  acceptance. The registry retains those qualifications separately.
- A preview is bounded and its sampling declaration remains attached. A complete local
  index means its declared native partition can be counted and queried; it does not
  promise that every referenced media file is available or licensed for redistribution.
- FineVision and the SmolLM2 training mixture use pinned whole-source sampling populations. Their bounded
  previews and explicitly budgeted additional samples do not create complete local
  query indices for their multi-terabyte sources. Global source totals describe the
  sampling population, never the number of locally indexed examples.
- PATA retains released labels, captions and third-party image URLs as native metadata.
  Its URL list does not establish availability or redistribution rights for the images.
  MultiTrust preserves heterogeneous native task units and linked conditions; a source
  unit is not automatically one image or one question.
- The activation collection retains each native neuron's ordered original activation
  strings. Column positions do not supply ImageNet image identities.
- Public media is limited to the exact approved CLEVR, EuroSAT and PAIRS previews.
  Other locally prepared data remains subject to its own publisher terms and access.
  Gated access is distinct from permission to publish.
- Optional analysis and model conversations require explicitly installed dependencies,
  weights or a configured local provider. Browsing requires no GPU. Context approval
  states what a model receives; no external model is connected automatically.

The catalogue preserves original source material. Browsing derivatives and analysis
outputs do not replace canonical originals. Release evidence reports the checks that
were actually run; source rights and paper-use qualifications are not software failures.
"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def preview_metadata(path: Path) -> tuple[int, str]:
    """Count record objects structurally, without decoding any native record value.

    Quoted payloads are skipped as opaque bytes. Only top-level JSON keys and
    container punctuation are examined; nested objects/arrays cannot inflate the
    number of records. Pack validation remains the responsibility of native checks.
    """
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        before = os.fstat(stream.fileno())
        if before.st_size > 100_000_000:
            raise ValueError("Preview pack exceeds the bounded metadata-count budget")
        depth, expect_key, records_key = 0, False, False
        start = None
        for token in JSON_TOKEN.finditer(mapped):
            value = token.group()
            if value in {b"{", b"["}:
                if depth == 1 and records_key:
                    if value != b"[":
                        raise ValueError("Preview records must be an array")
                    start = token.end()
                    break
                depth += 1
                if depth == 1:
                    expect_key = True
            elif value in {b"}", b"]"}:
                depth -= 1
            elif depth == 1 and value == b",":
                expect_key = True
                records_key = False
            elif depth == 1 and expect_key and value.startswith(b'"'):
                records_key = value == b'"records"'
                expect_key = False
        if start is None:
            raise ValueError("Preview pack has no records array")
        # Erasing strings in C avoids Python iterations over millions of native
        # activation strings; only structural braces/brackets reach the loop.
        structural = JSON_STRING.sub(b"", memoryview(mapped)[start:])
        count, depth = 0, 0
        for token in re.finditer(rb"[][{}]", structural):
            value = token.group()
            if depth == 0 and value == b"]":
                checksum = hashlib.sha256(mapped).hexdigest()
                after = os.fstat(stream.fileno())
                attributes = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
                if any(getattr(before, key) != getattr(after, key) for key in attributes):
                    raise ValueError("Preview pack changed during structural count and checksum")
                return count, checksum
            if depth == 0 and value == b"{":
                count += 1
            depth += 1 if value in {b"{", b"["} else -1
        raise ValueError("Preview records array is incomplete")


def preview_record_count(path: Path) -> int:
    return preview_metadata(path)[0]


def release_tree_sha256(root: Path) -> str:
    """Bind release inputs, including untracked new sources, without generated outputs."""
    paths = set()
    patterns = (
        "src/**/*.py", "apps/web/src/**/*", "apps/web/e2e/**/*", "apps/web/scripts/**/*",
        "apps/web/*.json", "apps/web/*.ts", "apps/web/index.html", "apps/web/public/licenses/**/*",
        "scripts/*.py", "scripts/*.sh", "tests/**/*.py", "tests/fixtures/**/*",
        "registry/**/*", "schemas/**/*", "examples/approved-packs/**/*", "examples/public-schema/**/*",
        "docs/**/*", ".github/workflows/*", ".pre-commit-config.yaml",
        "README.md", "ROADMAP.md", "SPEC.md", "pyproject.toml", "uv.lock", "requirements-analysis.txt",
        "start.sh", "LICENSE", "licenses/**/*",
    )
    for pattern in patterns:
        paths.update(path for path in root.glob(pattern) if path.is_file() and "__pycache__" not in path.parts)
    entries = [(path.relative_to(root).as_posix(), digest(path)) for path in sorted(paths)]
    return json_hash(entries)


def public_text(value: object) -> str:
    text = str(value or "")
    if any(marker in text for marker in ("/home/", "/Users/", "work/prepared/", "file://")):
        raise ValueError("Public release metadata contains a private machine path")
    return text


def public_url(value: object) -> str:
    text = public_text(value)
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.query:
        return ""
    return text


def source_pins(value: object) -> list[dict[str, object]]:
    """Publish only source locations and immutable identifiers, never adapter paths."""
    found = []
    if isinstance(value, dict):
        urls = {key: public_url(item) for key, item in value.items() if key in {"url", "source_url"}}
        urls = {key: item for key, item in urls.items() if item}
        pins: dict[str, object] = {key: item for key, item in value.items() if isinstance(item, str) and key in {"sha256", "revision", "commit", "etag", "source_sha256", "prepared_receipt_sha256"}}
        pins = {key: public_text(item) for key, item in pins.items()}
        shard_hashes = value.get("source_shards_sha256")
        if isinstance(shard_hashes, list) and shard_hashes and all(isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item) for item in shard_hashes):
            pins["source_shards_sha256"] = shard_hashes
        if urls and pins:
            found.append({**urls, **pins})
        for item in value.values():
            if isinstance(item, (dict, list)):
                found.extend(source_pins(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(source_pins(item))
    return sorted({json.dumps(item, sort_keys=True): item for item in found}.values(), key=lambda item: json.dumps(item, sort_keys=True))


def collect_release(root: Path) -> dict:
    registry = Registry(root)
    datasets = sorted((dataset for dataset in registry.datasets() if dataset.origin == "catalogue"), key=lambda item: item.id)
    rows, sources = [], []
    for dataset in datasets:
        active = registry.active_directory(dataset.id)
        pack_path = active / "pack/pack.json" if active else root / "work/packs" / dataset.id / "pack.json"
        preview_count = 0
        pack_sha256 = ""
        if pack_path.is_file():
            header = _pack_dataset(pack_path)
            if header.id != dataset.id:
                raise ValueError(f"{dataset.id}: preview header identifies a different dataset")
            for field in ("release", "snapshot_id"):
                if getattr(header, field) != getattr(dataset, field):
                    raise ValueError(f"{dataset.id}: preview header {field} disagrees with active registry")
            if header.coverage.unit != dataset.coverage.unit:
                raise ValueError(f"{dataset.id}: preview header unit disagrees with active registry")
            preview_count, pack_sha256 = preview_metadata(pack_path)
            if preview_count != dataset.coverage.preview_count:
                raise ValueError(f"{dataset.id}: actual preview count disagrees with active registry")
        manifest_path = registry.snapshot_path(dataset.id) / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        if manifest and (manifest.get("dataset_id"), manifest.get("snapshot_id")) != (dataset.id, dataset.snapshot_id):
            raise ValueError(f"{dataset.id}: complete index metadata disagrees with active registry")
        recipe_path = root / "registry/recipes" / f"{dataset.id}.yaml"
        recipe = (yaml.safe_load(recipe_path.read_text()) or {}) if recipe_path.is_file() else {}
        resolutions = [item for item in dataset.evidence if item.get("kind") == "source_release_resolution"]
        acquired_scope = next((item.get("scope") for item in reversed(dataset.evidence)
                               if item.get("kind") in {"verified_source_acquisition", "source_release_resolution"} and item.get("scope")), None)
        scope = (recipe.get("scope")
                 or next((item.get("population") for item in reversed(resolutions) if item.get("population")), None)
                 or acquired_scope or dataset.adapter_config.get("population")
                 or "Declared pinned source population; see the source registry metadata.")
        row = {
            "dataset_id": dataset.id, "name": dataset.name, "release": dataset.release,
            "snapshot_id": dataset.snapshot_id, "unit": dataset.coverage.unit,
            "source_url": public_url(dataset.source_url), "identity": dataset.coverage.identity,
            "access": dataset.coverage.access, "adapter": dataset.coverage.adapter,
            "preview": dataset.coverage.preview if preview_count else "none", "preview_count": preview_count,
            "declared_source_count": dataset.coverage.total_count,
            "complete_data": dataset.coverage.complete_data,
            "local_index_scope": manifest.get("population_scope", "none"),
            "local_index_count": manifest.get("record_count"), "publication": dataset.coverage.publication,
            "recipe_sha256": digest(recipe_path) if recipe_path.is_file() else "",
            "preview_pack_sha256": pack_sha256,
            "index_manifest_sha256": digest(manifest_path) if manifest_path.is_file() else "",
        }
        rows.append(row)
        remote_files = dataset.adapter_config.get("remote_files") or []
        source_sampler = bool(remote_files and recipe.get("sample_footers") == "all"
                              and dataset.release not in {"", "unresolved"}
                              and all(isinstance(item, dict) and re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", "")))
                                      and public_url(item.get("url")) and item.get("etag")
                                      and not str(item["etag"]).startswith("W/") for item in remote_files))
        sources.append({
            **{key: row[key] for key in ("dataset_id", "name", "release", "snapshot_id", "source_url", "unit", "declared_source_count", "local_index_scope", "local_index_count", "preview_count", "recipe_sha256", "index_manifest_sha256", "preview_pack_sha256")},
            "source_scope": public_text(scope),
            "native_source_sampling": source_sampler,
            "native_sampling_source_files": len(remote_files) if source_sampler else 0,
            "native_source_manifest_sha256": json_hash(remote_files) if source_sampler else "",
            "source_pins": source_pins(recipe) + source_pins(dataset.evidence),
            "rights": {key: public_text(value) for key, value in dataset.rights.items() if key in {"records", "annotations", "images", "derived_artifacts"}},
            "historical_paper_use": "Paper mentions and source-release identity do not establish exact historical experiment membership or human acceptance.",
        })
    catalogue_sha256 = json_hash({"rows": rows, "sources": sources})
    return {"rows": rows, "sources": sources, "catalogue_sha256": catalogue_sha256, "release_tree_sha256": release_tree_sha256(root)}


def validate_inventory(current: dict) -> None:
    sources = {source["dataset_id"]: source for source in current["sources"]}
    for row in current["rows"]:
        population = row["declared_source_count"]
        target = min(100, population) if isinstance(population, int) and population > 0 else 100
        if not row["preview_pack_sha256"] or row["preview_count"] < target:
            raise ValueError(f"{row['dataset_id']}: retained population lacks its required real preview")
        if row["local_index_scope"] == "complete":
            if not row["index_manifest_sha256"] or row["local_index_count"] != population:
                raise ValueError(f"{row['dataset_id']}: complete index count does not match declared population")
        elif not sources[row["dataset_id"]]["native_source_sampling"]:
            raise ValueError(f"{row['dataset_id']}: retained population lacks a complete index or pinned native source sampler")


def validate_verification(proof: dict, current: dict, version: str) -> None:
    if proof.get("schema_version") != "1.0" or proof.get("release_version") != version:
        raise ValueError("Verification proof schema_version/release_version does not match this release")
    for key in ("catalogue_sha256", "release_tree_sha256"):
        if proof.get(key) != current[key]:
            raise ValueError(f"Verification proof {key} is stale or does not match this release")
    checks = proof.get("checks", {})
    if any(checks.get(name, {}).get("status") != "passed" for name in REQUIRED_CHECKS):
        raise ValueError("Verification proof must pass all required checks: " + ", ".join(REQUIRED_CHECKS))
    for name in REQUIRED_CHECKS:
        check = checks[name]
        for field in ("command", "checked_at_utc", "summary"):
            if not isinstance(check.get(field), str) or not check[field].strip():
                raise ValueError(f"Verification check {name} needs {field}")
            public_text(check[field])
        try:
            stamp = datetime.fromisoformat(check["checked_at_utc"].replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"Verification check {name} has invalid checked_at_utc") from error
        if stamp.tzinfo is None:
            raise ValueError(f"Verification check {name} needs a timezone")


def evidence_markdown(status: dict) -> str:
    lines = ["# Dataset Atlas release evidence", "", f"Release {status['release_version']}; full_v1_complete: {str(status['full_v1_complete']).lower()}.", "",
             f"**{status['catalogue_entries']} catalogue entries, {status['prepared_previews']} prepared previews, {status['preview_records']:,} preview records, {status['local_complete_indices']} complete local indices.**", "",
             "Counts come from the active runtime registry, structural preview counts and index metadata. No dataset record values are decoded or inspected by this report generator. A source's total population is distinct from its locally indexed population.", "",
             f"Catalogue SHA-256: `{status['catalogue_sha256']}`.", f"Release source SHA-256: `{status['release_tree_sha256']}`.", ""]
    if status["full_v1_complete"]:
        lines.extend(["The current verification proof passed every required software release gate. Its checksum is " + f"`{status['verification']['proof_sha256']}`. Automated verification does not confer human, scientific or publication acceptance.", "", "| Check | Result | Evidence |", "| --- | --- | --- |"])
        for name in REQUIRED_CHECKS:
            check = status["verification"]["checks"][name]
            lines.append(f"| {name.replace('_', ' ')} | passed | {check['summary'].replace('|', '/')} |")
    else:
        lines.extend(["Release verification is pending. This draft does not claim v1 completion; supply a current proof with every required check to finalize it.", ""])
    lines.extend(["", "[Coverage](dataset_coverage.csv) · [Pinned sources](catalogue-sources.json) · [Source and rights qualifications](limitations.md).", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--verified", type=Path, help="current, completed verification proof")
    parser.add_argument("--fingerprint", action="store_true", help="print current release bindings without writing reports")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    current = collect_release(root)
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    fingerprints = {key: current[key] for key in ("catalogue_sha256", "release_tree_sha256")}
    if args.fingerprint:
        print(json.dumps({"schema_version": "1.0", "release_version": version, **fingerprints}, indent=2))
        return 0
    verification = {"status": "pending", "checks": {}}
    if args.verified:
        proof = json.loads(args.verified.read_text())
        validate_inventory(current)
        validate_verification(proof, current, version)
        verification = {"schema_version": "1.0", "status": "verified", **fingerprints,
                        "proof_sha256": digest(args.verified),
                        "checks": {name: {key: proof["checks"][name][key]
                                          for key in ("status", "command", "checked_at_utc", "summary")}
                                   for name in REQUIRED_CHECKS}}
    rows = current["rows"]
    status = {"schema_version": "1.0", "release_version": version,
              "generated_at_utc": datetime.now(timezone.utc).isoformat(), **fingerprints,
              "full_v1_complete": verification["status"] == "verified",
              "catalogue_entries": len(rows), "prepared_previews": sum(row["preview_count"] > 0 for row in rows),
              "preview_records": sum(row["preview_count"] for row in rows),
              "entries_without_preview": sum(row["preview_count"] == 0 for row in rows),
              "local_complete_indices": sum(row["local_index_scope"] == "complete" for row in rows),
              "public_media_datasets": ["clevr", "eurosat", "pairs"],
              "verification": verification,
              "scope_note": "Software release verification for the declared native source populations. Source rights and historical paper-use evidence are documented; automated tests do not confer human or scientific acceptance."}
    output = root / "reports"
    output.mkdir(exist_ok=True)
    with (output / "dataset_coverage.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for name, document in (("final-status.json", status), ("catalogue-sources.json", {"schema_version": "1.0", "catalogue_sha256": current["catalogue_sha256"], "datasets": current["sources"]})):
        text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        public_text(text)
        (output / name).write_text(text)
    (output / "release_evidence.md").write_text(evidence_markdown(status))
    (output / "limitations.md").write_text(LIMITATIONS)
    print(json.dumps({key: status[key] for key in ("release_version", "full_v1_complete", "catalogue_entries", "prepared_previews", "preview_records", "local_complete_indices")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
