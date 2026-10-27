"""Zero-transfer, immutable native-unit migrations of retained local snapshots.

No function in this module fetches media or source files. The existing source
pins and preview originals are verified locally before a replacement is published.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Literal

import pyarrow.parquet as pq

from dataset_atlas.adapters import get_adapter
from dataset_atlas.adapters.multitrust import MultiTrustAdapter
from dataset_atlas.models import Dataset, FieldDescriptor, Pack, Record
from dataset_atlas.preparation import atomic
from dataset_atlas.preparation.slots import try_writer_slot
from dataset_atlas.queries.parquet import ParquetSnapshot, build_parquet_snapshot
from dataset_atlas.registry import Registry


# These are released source folders, not runtime evaluation examples. Task and
# pairing provenance comes from the already retained 2026-10-09 task audit.
MULTITRUST_INVENTORY_TASKS = [
    {"task": "nsfw", "aspect": "safety", "prefix": "safety/nsfw", "unit_kind": "image_only_example",
     "join_basis": "image_only_no_query_file", "toolkit_tasks": ["nsfw-image-description"]},
    {"task": "risk_identification", "aspect": "safety", "prefix": "safety/risk_identification", "unit_kind": "image_only_example",
     "join_basis": "image_only_no_query_file", "toolkit_tasks": ["risk-identification"]},
    {"task": "stereo_generation", "aspect": "fairness", "prefix": "fairness/stereo_generation_images", "unit_kind": "image_only_example",
     "join_basis": "image_only_no_query_file", "toolkit_tasks": ["stereo-generation"]},
    {"task": "stereo_query", "aspect": "fairness", "prefix": "fairness/stereo_query_images", "unit_kind": "unpaired_image",
     "join_basis": "none_listdir_order_in_toolkit", "related_query_task": "stereo_query", "toolkit_tasks": ["stereo-query-image"]},
    *[{"task": "crossmodal_jailbreak", "aspect": "safety", "prefix": f"safety/crossmodal-jailbreak/{pool}",
       "unit_kind": "source_pool_image", "join_basis": "none_cross_product_in_toolkit",
       "related_query_task": "crossmodal_jailbreak", "toolkit_tasks": ["crossmodal-jailbreak"]}
      for pool in ("jailbreak_neg", "jailbreak_pos")],
    {"task": "shared_unrelated_images", "aspect": "shared", "prefix": "unrelated_images", "unit_kind": "source_pool_image",
     "join_basis": "none_random_choice_in_toolkit", "toolkit_tasks": []},
    {"task": "real_toxicity_prompts", "aspect": "safety", "prefix": "safety/real_toxicity_prompt/images", "unit_kind": "source_pool_image",
     "join_basis": "no_released_query_row", "related_query_task": "real_toxicity_prompts", "unreferenced_only": True},
    {"task": "typographic_prompt_graph", "aspect": "safety", "prefix": "safety/typographic_jailbreak/prompt_graph", "unit_kind": "source_pool_image",
     "join_basis": "no_released_query_row", "related_query_task": "typographic_prompt_graph", "unreferenced_only": True},
]


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _inside(root, path):
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("Native migration path escapes the workspace or is a symlink")
    return path.resolve()


def _active(root, dataset_id):
    pointer = _inside(root, root / "work/prepared" / dataset_id / "active.json")
    version = json.loads(pointer.read_text())["version"]
    directory = _inside(root, pointer.parent / version)
    if directory.parent != pointer.parent:
        raise ValueError("Invalid native migration source version")
    dataset = Dataset.model_validate_json((directory / "dataset.json").read_text())
    if (root / "registry/datasets" / (dataset_id + ".yaml")).is_file():
        curated = Registry(root).baseline_dataset(dataset_id)
        for name in ("name", "description", "aliases", "tasks", "modalities", "labels", "paper_ids", "rights", "relationships", "evidence"):
            setattr(dataset, name, getattr(curated, name))
        for name in ("identity", "source", "access", "publication"):
            setattr(dataset.coverage, name, getattr(curated.coverage, name))
    # The query reader writes a verification cache stamp. Inspect source snapshots
    # without that side effect: even an absent cache file in an old version stays
    # absent throughout this migration.
    parquet = _inside(root, directory / "snapshot/records.parquet")
    manifest = json.loads((directory / "snapshot/manifest.json").read_text())
    if (manifest.get("schema_version") != "1.0" or manifest.get("unit") != "example"
            or manifest.get("parquet_bytes") != parquet.stat().st_size
            or _digest(parquet) != manifest.get("checksums", {}).get("records.parquet")):
        raise ValueError("Native source snapshot checksum or contract differs")
    metadata = pq.read_metadata(parquet)
    if metadata.num_rows != manifest.get("record_count") or any(
        metadata.metadata.get(key.encode(), b"").decode() != manifest.get(key)
        for key in ("dataset_id", "release_id", "snapshot_id", "unit")
    ):
        raise ValueError("Native source snapshot identity or row count differs")
    reader = SimpleNamespace(parquet=parquet, fields=[FieldDescriptor.model_validate(f) for f in manifest["fields"]],
                             **{key: manifest[key] for key in ("record_count", "dataset_id", "release_id", "snapshot_id", "population_scope")})
    if (dataset.id != dataset_id or reader.dataset_id != dataset_id or reader.snapshot_id != dataset.snapshot_id
            or reader.release_id != dataset.release or reader.population_scope != "complete"):
        raise ValueError("Native migration requires a matching complete snapshot")
    return pointer, version, directory, dataset, reader


def _records(reader):
    for batch in pq.ParquetFile(reader.parquet).iter_batches(batch_size=128, columns=["record_json"]):
        for value in batch.column(0).to_pylist():
            yield Record.model_validate_json(value)


def _retain(root, source, target, expected=None):
    source = _inside(root, source)
    if not source.is_file() or (expected is not None and _digest(source) != expected):
        raise ValueError("Retained native source or preview original differs from its checksum")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, target)


def _size(directory):
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def _verify_candidate(root, directory, expected_count, expected_preview):
    dataset = Dataset.model_validate_json((directory / "dataset.json").read_text())
    reader = ParquetSnapshot(root, directory / "snapshot")
    pack = Pack.model_validate_json((directory / "pack/pack.json").read_text())
    if (reader.record_count != expected_count or reader.snapshot_id != dataset.snapshot_id
            or pack.dataset.snapshot_id != reader.snapshot_id or len(pack.records) != expected_preview
            or len({record.id for record in pack.records}) != expected_preview):
        raise ValueError("Native candidate membership or identity differs")
    stored = reader.records([record.id for record in pack.records])
    for record in pack.records:
        canonical = stored[record.id]
        if (canonical.source != record.source or canonical.snapshot_id != record.snapshot_id
                or canonical.asset_ids != record.asset_ids):
            raise ValueError("Native preview does not belong to its complete snapshot")
    for name, digest in pack.checksums.items():
        if _digest(_inside(root, directory / "pack" / name)) != digest:
            raise ValueError("Retained preview original checksum differs")
    return dataset, pack


def _publish(root, pointer, source_version, version, plan, build, *, execute, activate, max_output_bytes):
    if type(max_output_bytes) is not int or not 1 <= max_output_bytes <= 1_500_000_000:
        raise ValueError("Native migration output budget must be between 1 and 1500000000 bytes")
    result = {**plan, "version": version, "plan_id": version, "source_version": source_version,
              "scope": "complete retained native metadata; preview sampling scope is declared separately",
              "expected_download_bytes": 0, "downloaded_bytes": 0, "status": "planned", "activated": False}
    if not execute:
        return result
    locks = _inside(root, root / "work/preparation")
    locks.mkdir(parents=True, exist_ok=True)
    lease = try_writer_slot(locks, plan["dataset_id"], version)
    if lease is None:
        raise RuntimeError("Another preparation owns the dataset or both writer slots")
    target = _inside(root, pointer.parent / version)
    with lease:
        reused = target.exists()
        if target.exists():
            _verify_candidate(root, target, plan["expected_records"], plan["preview_records"])
        else:
            with tempfile.TemporaryDirectory(prefix=".native-units-", dir=pointer.parent) as scratch:
                stage = Path(scratch) / "version"
                stage.mkdir()
                build(stage, target)
                _verify_candidate(root, stage, plan["expected_records"], plan["preview_records"])
                if _size(stage) > max_output_bytes:
                    raise ValueError("Native migration exceeds its output budget")
                atomic(stage / "receipt.json", {**result, "status": "completed", "output_bytes": _size(stage)})
                if _size(stage) > max_output_bytes:
                    raise ValueError("Native migration receipt exceeds its output budget")
                os.replace(stage, target)
        result.update(status="completed", output_bytes=_size(target), new_output_bytes=0 if reused else _size(target),
                      snapshot_id=json.loads((target / "dataset.json").read_text())["snapshot_id"])
        if result["output_bytes"] > max_output_bytes:
            raise ValueError("Retained native migration exceeds the output budget")
        if activate:
            if json.loads(pointer.read_text())["version"] not in {source_version, version}:
                raise ValueError("Active version changed during native migration; candidate preserved")
            atomic(pointer, {"version": version})
            result["activated"] = True
    return result


def prepare_pata_preview(root, *, execute=False, activate=False, count=100, seed=0, max_output_bytes=100_000_000):
    """Sample native label/URL/caption records; never fetch or imply image availability."""
    root = Path(root).resolve()
    if type(count) is not int or not 1 <= count <= 1000 or type(seed) is not int:
        raise ValueError("Metadata preview requires a bounded count and integer seed")
    pointer, source_version, source, dataset, reader = _active(root, "pata")
    manifest_sha = _digest(source / "snapshot/manifest.json")
    identity = hashlib.sha256(f"pata-metadata-preview-v1-contract2:{dataset.snapshot_id}:{manifest_sha}:{seed}:{count}".encode()).hexdigest()
    version = "metadata-preview-v1-" + identity
    selected = heapq.nsmallest(min(count, reader.record_count), _records(reader),
                              key=lambda record: (hashlib.sha256(f"{seed}:{record.id}".encode()).digest(), record.id))
    if any(record.assets for record in selected):
        raise ValueError("PATA metadata preview unexpectedly contains media")
    plan = {"dataset_id": "pata", "migration": "metadata_preview_v1", "expected_records": reader.record_count,
            "preview_records": len(selected), "native_image_preview_count": 0, "source_snapshot_id": dataset.snapshot_id}

    def build(stage, target):
        for name in ("manifest.json", "records.parquet"):
            _retain(root, source / "snapshot" / name, stage / "snapshot" / name)
        dataset.coverage.preview = "metadata_only"
        dataset.coverage.preview_count = len(selected)
        dataset.coverage.blockers = [
            "Native label/URL rows and exact caption objects are indexed; the preview contains metadata records only.",
            "No third-party image is fetched or claimed available; URL availability and image rights remain unreviewed."]
        pack = Pack(dataset=dataset, fields=reader.fields, records=selected, sampling={
            "method": "sha256_bottom_k_metadata_records", "seed": seed, "unit": "example",
            "population": "complete released label/URL and exact-caption metadata", "population_count": reader.record_count,
            "requested_count": count, "returned_count": len(selected), "media_representation": "none",
            "selection_note": "Metadata-only native records; zero images fetched. Author labels are not self-reports."})
        atomic(stage / "dataset.json", dataset.model_dump(mode="json"))
        atomic(stage / "pack/pack.json", pack.model_dump(mode="json"), compact=True)
        if _digest(source / "snapshot/manifest.json") != manifest_sha:
            raise ValueError("PATA source snapshot changed during preview migration")

    return _publish(root, pointer, source_version, version, plan, build,
                    execute=execute, activate=activate, max_output_bytes=max_output_bytes)


def prepare_multitrust_inventory(root, *, execute=False, activate=False, max_output_bytes=500_000_000,
                                 inventory_tasks=None):
    """Append native images without pairing them to queries; reuse the verified preview."""
    root = Path(root).resolve()
    pointer, source_version, source, dataset, reader = _active(root, "multitrust")
    if dataset.adapter_config.get("inventory_tasks"):
        receipt = json.loads((source / "receipt.json").read_text())
        if receipt.get("migration") != "native_inventory_units_v1" or inventory_tasks is not None:
            raise ValueError("MultiTrust source already contains a different inventory-unit migration")
        _verify_candidate(root, source, receipt["expected_records"], receipt["preview_records"])
        if type(max_output_bytes) is not int or _size(source) > max_output_bytes:
            raise ValueError("Retained native migration exceeds the output budget")
        return {**receipt, "version": source_version, "status": "completed", "output_bytes": _size(source),
                "new_output_bytes": 0, "activated": bool(activate)}
    specs = MULTITRUST_INVENTORY_TASKS if inventory_tasks is None else inventory_tasks
    config = dataset.adapter_config
    config["inventory_tasks"] = specs
    for key in ("media_inventory_path", "remote_cache_root"):
        if key in config:
            config[key] = str(_inside(root, config[key]))
    adapter = get_adapter(dataset)
    if not isinstance(adapter, MultiTrustAdapter):
        raise ValueError("Native inventory migration requires the MultiTrust adapter")
    report = adapter.join_report()
    if report["query_rows"] != reader.record_count:
        raise ValueError("Native query count differs from retained complete snapshot")
    identity_document = {"migration": "multitrust_inventory_units_v1", "unit_contract": 2, "source_snapshot_id": dataset.snapshot_id,
                         "source_manifest_sha256": _digest(source / "snapshot/manifest.json"),
                         "inventory_sha256": config["media_inventory_sha256"], "inventory_tasks": specs}
    digest = hashlib.sha256(json.dumps(identity_document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    version = "native-units-v1-" + digest
    old_snapshot = dataset.snapshot_id
    dataset.snapshot_id = old_snapshot + "-units-" + digest[:16]
    old_pack = Pack.model_validate_json((source / "pack/pack.json").read_text())
    fields = list(reader.fields)
    known = {field.id for field in fields}
    extra_fields: list[tuple[str, Literal["category", "string", "array"]]] = [
        ("unit_kind", "category"), ("join_basis", "category"), ("image_file", "string"),
        ("source_pool", "category"), ("source_category", "category"), ("toolkit_tasks", "array"),
        ("related_query_task", "category")]
    for name, dtype in extra_fields:
        if "source." + name not in known:
            fields.append(FieldDescriptor(id="source." + name, name=name, dtype=dtype))
    for field in fields:
        if field.id in {"source.task", "source.aspect"}:
            key = field.id.split(".")[1]
            field.values = list(dict.fromkeys([*(field.values or []), *(spec[key] for spec in specs)]))
    plan = {"dataset_id": "multitrust", "migration": "native_inventory_units_v1", "expected_records": report["rows"],
            "query_records": report["query_rows"], "inventory_records": report["inventory_rows"],
            "preview_records": len(old_pack.records), "source_snapshot_id": old_snapshot,
            "image_only_records": sum(row.get("unit_kind") == "image_only_example" for row in adapter._rows()),
            "unpaired_image_records": sum(row.get("unit_kind") == "unpaired_image" for row in adapter._rows()),
            "source_pool_image_records": sum(row.get("unit_kind") == "source_pool_image" for row in adapter._rows()),
            "unindexed_inventory_images": len(report["inventory_images_without_a_record"])}

    def build(stage, target):
        for entry in config["source_files"]:
            original = _inside(root, entry["path"])
            name = entry["sha256"] + original.suffix
            _retain(root, original, stage / "sources" / name, entry["sha256"])
            entry["path"] = str(stage / "sources" / name)
        inventory_name = config["media_inventory_sha256"] + ".inventory.json"
        _retain(root, config["media_inventory_path"], stage / "sources" / inventory_name, config["media_inventory_sha256"])
        config["media_inventory_path"] = str(stage / "sources" / inventory_name)
        current = get_adapter(dataset)
        prepared = current.prepare(current.plan(1000, max_output_bytes))
        old_records = iter(_records(reader))
        preview_ids = {record.id for record in old_pack.records}
        selected = {}

        def native_records():
            cursor, ordinal = None, 0
            while True:
                batch = current.iter_records(prepared, cursor, 1000)
                for record in batch.records:
                    if ordinal < reader.record_count:
                        original = next(old_records)
                        actual = record.model_dump(mode="json")
                        actual["snapshot_id"] = old_snapshot
                        for name in ("unit_kind", "join_basis", "toolkit_tasks"):
                            actual["source"].pop(name, None)
                        if actual != original.model_dump(mode="json"):
                            raise ValueError("Native query row changed during inventory migration")
                    if record.id in preview_ids:
                        selected[record.id] = record
                    ordinal += 1
                    yield record
                cursor = batch.next_cursor
                if cursor is None:
                    break
            if next(old_records, None) is not None:
                raise ValueError("Retained native query rows were truncated")

        build_parquet_snapshot(native_records(), fields, stage / "snapshot", root=root,
                               dataset_id="multitrust", release_id=dataset.release, snapshot_id=dataset.snapshot_id,
                               expected_count=report["rows"], population_scope="complete", max_bytes=max_output_bytes)
        preview = []
        for record in old_pack.records:
            updated = selected[record.id]
            updated.assets = record.assets
            preview.append(updated)
        for name, checksum in old_pack.checksums.items():
            _retain(root, source / "pack" / name, stage / "pack" / name, checksum)
        # Persist final source locations only after all reads against the staging
        # directory have finished. The candidate moves atomically into this path.
        for entry in config["source_files"]:
            entry["path"] = str(target / "sources" / Path(entry["path"]).name)
        config["media_inventory_path"] = str(target / "sources" / inventory_name)
        dataset.coverage.total_count = report["rows"]
        dataset.description = ("Pinned MultiTrust native release units: query rows, image-only task examples, independent "
                               "unpaired images and source pool images. No runtime prompt or image pairing is fabricated.")
        dataset.coverage.blockers = [
            "Query rows, image-only task examples, unpaired images and source pool images have explicit unit_kind provenance.",
            "Runtime prompt templates, random selections, directory-order pairings and cross products are not fabricated.",
            "The Enron k-shot support table is not an evaluation query population. Media and redistribution rights remain unreviewed."]
        pack = Pack(dataset=dataset, fields=fields, records=preview, checksums=old_pack.checksums,
                    sampling={"method": "retained_verified_query_preview", "unit": "example",
                              "population": "query rows of the retained source snapshot", "population_count": reader.record_count,
                              "source_snapshot_id": old_snapshot, "current_complete_population_count": report["rows"],
                              "returned_count": len(preview), "media_representation": "original",
                              "original_sampling": old_pack.sampling,
                              "selection_note": "Unchanged verified query preview; appended inventory units are outside its sampling population."})
        atomic(stage / "dataset.json", dataset.model_dump(mode="json"))
        atomic(stage / "pack/pack.json", pack.model_dump(mode="json"), compact=True)

    return _publish(root, pointer, source_version, version, plan, build,
                    execute=execute, activate=activate, max_output_bytes=max_output_bytes)
