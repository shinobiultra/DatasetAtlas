"""Build local, provenance-pinned BeHonest and GVIL records without publishing content.

Run after bounded acquisition of the exact upstream files named in the receipts.
Original files are read-only; converted JSONL, previews and snapshots live in work/.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from dataset_atlas.adapters import build_preview, get_adapter
from dataset_atlas.queries.parquet import ParquetSnapshot, build_parquet_snapshot
from dataset_atlas.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
BEHONEST_REV = "fcdb24a2de2cd236bbd1b4484d99c23512ee7cc6"
BEHONEST_MANIFEST_SHA256 = "c0b199816c748e6e6f60f1257937cdca1d634a7001ef30641b5a463664db1f9c"
GVIL_REV = "cd04efb9d53c935c8194011d32b5a8b515c588bf"
GVIL_SHA256 = "1d717f5822ded7d3383d014eefd1fb17c0a46ab15ce0c104f0c0392365c8650b"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_rows(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return sha(path)


def finish(dataset_id: str, rows: list[dict], config: dict, receipt: dict,
           *, release: str, description: str, modalities: list[str], tasks: list[str]) -> None:
    path = ROOT / "registry/datasets" / f"{dataset_id}.yaml"
    manifest = yaml.safe_load(path.read_text())
    source = ROOT / "work/sources" / dataset_id / "records.jsonl"
    converted_sha = write_rows(source, rows)
    snapshot_id = f"{dataset_id}-sha256-{converted_sha}"
    manifest.update(
        description=description, release=release, snapshot_id=snapshot_id,
        adapter=config.pop("adapter"), modalities=modalities, tasks=tasks,
        source_url=receipt["source_url"],
        adapter_config={"path": str(source.relative_to(ROOT)), "format": "jsonl",
                        "sha256": converted_sha, **config},
    )
    manifest["coverage"].update(
        identity="resolved", source="verified", access="public", adapter="tested",
        preview="complete_target", complete_data="supported", publication="metadata_only",
        preview_count=min(100, len(rows)), total_count=len(rows),
        blockers=["Source content rights are not cleared for static publication; local inspection only."],
    )
    receipt.update(dataset_id=dataset_id, converted_sha256=converted_sha,
                   source_row_count=len(rows), snapshot_id=snapshot_id,
                   scope=description)
    source_evidence = {
        "kind": "verified_local_source_snapshot", "checked_on": "2026-09-22",
        "revision": release, "receipt": f"reports/{dataset_id}-source.json",
        "source_row_count": len(rows), "scope": description,
    }
    if source_evidence not in manifest.setdefault("evidence", []):
        manifest["evidence"].append(source_evidence)
    path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
    dataset = Registry(ROOT).dataset(dataset_id)
    pack = build_preview(dataset, ROOT / "work/packs" / dataset_id, limit=100,
                         max_bytes=100_000_000, distinct_assets=(dataset_id == "gvil"),
                         include_media=(dataset_id == "gvil"))
    adapter = get_adapter(dataset)
    snapshots = ROOT / "work/snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    destination = snapshots / dataset_id
    if destination.exists():
        existing = ParquetSnapshot(snapshots, destination)
        if (existing.manifest["snapshot_id"] != snapshot_id
                or existing.manifest["record_count"] != len(rows)
                or existing.manifest["population_scope"] != "complete"):
            raise ValueError("Existing immutable snapshot differs from pinned source")
    else:
        build_parquet_snapshot((adapter._record(row, index) for index, row in enumerate(adapter._rows())),
                               pack.fields, destination, root=snapshots,
                               dataset_id=dataset_id, release_id=dataset.release,
                               snapshot_id=snapshot_id, expected_count=len(rows),
                               population_scope="complete", max_bytes=500_000_000)
    receipt.update(preview_records=len(pack.records), preview_distinct_assets=len({
        asset.id for record in pack.records for asset in record.assets}),
        snapshot_manifest=str((snapshots / dataset_id / "manifest.json").relative_to(ROOT)))
    (ROOT / "reports" / f"{dataset_id}-source.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"dataset": dataset_id, "rows": len(rows),
                      "preview": len(pack.records), "snapshot": snapshot_id}), flush=True)


def behonest() -> None:
    source = ROOT / "work/sources/behonest/original"
    paths = sorted(source.rglob("*.json"))
    if len(paths) != 18 or sum(path.stat().st_size for path in paths) > 10_000_000:
        raise ValueError("BeHonest pinned 18-file source is missing or exceeds 10 MB")
    file_rows = []
    source_hashes = {}
    for path in paths:
        name = path.relative_to(source).as_posix()
        source_hashes[name] = sha(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            raise ValueError(f"Unexpected BeHonest source shape: {name}")
        seen = set()
        converted = []
        for row in data:
            upstream_id = row.get("id")
            if upstream_id is None or upstream_id in seen:
                raise ValueError(f"Missing or duplicate upstream ID in {name}")
            seen.add(upstream_id)
            prompt = row.get("prompt", row.get("prompt_1"))
            if not isinstance(prompt, str):
                raise ValueError(f"Missing prompt in {name}")
            converted.append({**row, "source_id": f"{name}::{upstream_id}",
                              "scenario": name.split("/")[0], "source_member": name,
                              "display_text": prompt})
        file_rows.append(converted)
    manifest_digest = hashlib.sha256(json.dumps(source_hashes, sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()
    if manifest_digest != BEHONEST_MANIFEST_SHA256:
        raise ValueError("BeHonest source files differ from reviewed pinned snapshot")
    # Source-order round robin across released files gives a useful local preview.
    rows = [row for offset in range(max(map(len, file_rows)))
            for group in file_rows if offset < len(group) for row in [group[offset]]]
    receipt = {"source_revision": BEHONEST_REV, "source_files_sha256": source_hashes,
               "source_bytes": sum(path.stat().st_size for path in paths),
               "counts_by_file": {path.relative_to(source).as_posix(): len(group)
                                  for path, group in zip(paths, file_rows, strict=True)},
               "source_url": f"https://huggingface.co/datasets/GAIR/BeHonest/tree/{BEHONEST_REV}"}
    config = {"adapter": "structured", "mapping": {"id": "source_id", "text": "display_text"},
              "fields": {"scenario": {"dtype": "category", "description": "Upstream scenario folder"},
                         "source_member": {"dtype": "category", "description": "Original JSON member"},
                         "id": {"dtype": "number", "description": "Original file-local ID"}},
              "population": "all 18 JSON files in pinned GAIR/BeHonest HF snapshot",
              "selection_note": "Source-order round robin across 18 files; this HF release omits a separately linked Demonstration Format source."}
    description = ("Local pinned GAIR/BeHonest release: all 18 JSON files (9 scenario directories), "
                   "with original IDs and source columns preserved. Corpus role is bibliography-only; "
                   "the separately linked Demonstration Format source is outside this snapshot.")
    finish("behonest", rows, config, receipt, release=f"hf-{BEHONEST_REV}",
           description=description, modalities=["text"], tasks=["honesty evaluation"])


def gvil() -> None:
    archive = ROOT / "work/sources/gvil/original/dataset.zip"
    if not archive.is_file() or archive.stat().st_size > 30_000_000 or sha(archive) != GVIL_SHA256:
        raise ValueError("GVIL archive missing, oversized or differs from pinned SHA-256")
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        if sum(item.file_size for item in members) > 50_000_000 or any(
            item.filename.startswith("/") or ".." in Path(item.filename).parts for item in members
        ):
            raise ValueError("GVIL archive size or member path is unsafe")
        vqa = json.loads(zipped.read("dataset/vqa_annotation.json"))
        vg = json.loads(zipped.read("dataset/vg_annotation.json"))
        pairs = json.loads(zipped.read("dataset/pair_info.json"))
        raw = json.loads(zipped.read("dataset/raw_annotations.json"))
        images = {item.filename for item in members if item.filename.startswith("dataset/images/")
                  and item.filename.lower().endswith(".jpg")}
    if len(vqa) != 2400 or len(vg) != 800 or len(images) != 204 or len(raw) != 102:
        raise ValueError("GVIL release structure differs from reviewed source")
    pair_index = {}
    for task, groups in pairs.items():
        if len(groups) != 400:
            raise ValueError(f"Unexpected GVIL pair count: {task}")
        for ordinal, pair in enumerate(groups):
            if len(pair) != 2:
                raise ValueError("GVIL pair must have two members")
            for member in pair:
                token = (task, member)
                if token in pair_index:
                    raise ValueError("Duplicate GVIL pair member")
                pair_index[token] = f"{task}:{ordinal}"
    rows = []
    for member_name, source in (("dataset/vqa_annotation.json", vqa),
                                ("dataset/vg_annotation.json", vg)):
        for source_key, row in source.items():
            task = row["type"]
            image_path = f"dataset/images/{row['img']}"
            if image_path not in images or (task, source_key) not in pair_index:
                raise ValueError(f"GVIL annotation lacks image or pair: {source_key}")
            rows.append({**row, "source_id": f"{task}:{source_key}",
                         "source_key": source_key, "source_member": member_name,
                         "pair_id": pair_index[(task, source_key)],
                         "media_path": image_path,
                         "display_question": row.get("question", row.get("query"))})
    if len(rows) != 3200 or len(pair_index) != 3200:
        raise ValueError("GVIL full task population does not match pairs")
    # Interleave four tasks and source questions so 100 preview records have 100 distinct images.
    by_image = defaultdict(list)
    for row in rows:
        by_image[row["media_path"]].append(row)
    rows = [group[offset] for offset in range(max(map(len, by_image.values())))
            for group in by_image.values() if offset < len(group)]
    counts = Counter(row["type"] for row in rows)
    receipt = {"source_revision": GVIL_REV, "archive_sha256": GVIL_SHA256,
               "archive_bytes": archive.stat().st_size,
               "annotation_counts": dict(counts), "pair_counts": {key: len(value) for key, value in pairs.items()},
               "source_images": len(images), "raw_annotation_rows": len(raw),
               "source_url": f"https://github.com/vl-illusion/GVIL/tree/{GVIL_REV}"}
    config = {"adapter": "structured_archive", "mapping": {
        "id": "source_id", "question": "display_question", "media": "media_path"},
        "media_archive": str(archive.relative_to(ROOT)), "media_archive_sha256": GVIL_SHA256,
        "fields": {
            "type": {"dtype": "category", "values": sorted(counts), "description": "Original GVIL task"},
            "pair_id": {"dtype": "category", "description": "Pair identifier within task"},
            "source_key": {"dtype": "category", "description": "Original annotation map key"},
            "img": {"dtype": "category", "description": "Original image filename"},
            "q_id": {"dtype": "number", "description": "Original question ID"},
        }, "population": "all 2,400 VQA and 800 VG annotation entries in author archive",
        "selection_note": "One first annotation per distinct image before further source questions; local media only."}
    description = ("Local author GVIL archive: 2,400 VQA and 800 visual grounding annotation rows, "
                   "1,600 explicit pairs, 204 JPEG files (200 referenced). Original annotations and "
                   "task-specific source keys are preserved. Corpus roles remain introduction/related-work mentions.")
    finish("gvil", rows, config, receipt, release=f"github-{GVIL_REV}",
           description=description, modalities=["image", "text"],
           tasks=["visual question answering", "visual grounding"])


if __name__ == "__main__":
    import sys
    for dataset_id in sys.argv[1:]:
        {"behonest": behonest, "gvil": gvil}[dataset_id]()
