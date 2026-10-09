"""Run a bounded real COCO-2017-validation analysis from the local preview.

The source ZIPs and local model weights must already be prepared and pinned in
the registry. This command downloads nothing. It writes selected JPEG copies,
immutable job artifacts, and a receipt under work/demo-analysis-coco and
reports/analysis-demo-coco-100.json. It does not publish a public pack.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from dataset_atlas.adapters import resolve_dataset_asset
from dataset_atlas.jobs.manager import JobManager
from dataset_atlas.models import Pack, Record, Selection, content_id
from dataset_atlas.registry import Registry

from .demo import MODEL_HASHES, _run, _sha256


def _selection(root: Path, work: Path) -> tuple[Selection, list[Record], dict]:
    registry = Registry(root)
    dataset = registry.dataset("coco")
    if dataset.adapter != "coco" or dataset.release != "COCO-2017-val" or not dataset.snapshot_id:
        raise ValueError("Pinned COCO-2017-val registry entry is required")
    pack_path = root / "work/packs/coco/pack.json"
    if pack_path.stat().st_size > 100_000_000:
        raise ValueError("COCO preview exceeds 100 MB pack bound")
    pack = Pack.model_validate_json(pack_path.read_text(encoding="utf-8"))
    if (pack.dataset.id != dataset.id or pack.dataset.release != dataset.release
            or pack.dataset.snapshot_id != dataset.snapshot_id or pack.population_scope != "preview"
            or pack.sampling.get("method") != "first_per_asset_source_order"):
        raise ValueError("COCO preview and pinned registry differ")
    records = [record.model_copy(deep=True) for record in pack.records]
    if len(records) != 100 or len({r.id for r in records}) != 100:
        raise ValueError("Expected exactly 100 COCO caption examples")
    asset_ids = [r.asset_ids[0] for r in records if len(r.asset_ids) == 1 and len(r.assets) == 1]
    if len(asset_ids) != 100 or len(set(asset_ids)) != 100:
        raise ValueError("COCO analysis selection requires 100 distinct image assets")
    if any(r.dataset_id != "coco" or r.release_id != dataset.release or r.snapshot_id != dataset.snapshot_id
           or not r.text for r in records):
        raise ValueError("COCO preview contains inconsistent or captionless records")

    media = work / "media"
    media.mkdir(parents=True, exist_ok=True)
    image_receipts = []
    for record in records:
        asset = record.assets[0]
        source_ref = asset.uri
        if not source_ref or source_ref != "val2017/" + asset.metadata.get("source_file_name", ""):
            raise ValueError("COCO preview asset reference is inconsistent")
        handle = resolve_dataset_asset(dataset, source_ref, max_bytes=10_000_000, workspace_root=root)
        if handle.source_ref != source_ref or handle.media_type != "image/jpeg":
            raise ValueError("Resolved COCO image identity differs from preview")
        relative = Path(source_ref).name
        target = media / relative
        if target.exists():
            if _sha256(target) != handle.sha256:
                raise ValueError(f"Prepared COCO image hash mismatch: {relative}")
        else:
            staged = target.with_suffix(".jpg.part")
            staged.write_bytes(handle.data)
            if _sha256(staged) != handle.sha256:
                staged.unlink(missing_ok=True)
                raise ValueError(f"COCO source image hash mismatch: {relative}")
            staged.replace(target)
        asset.uri = relative
        asset.sha256 = handle.sha256
        asset.metadata["source_ref"] = source_ref
        record.source["analysis_source_ref"] = source_ref
        record.source["analysis_source_sha256"] = handle.sha256
        image_receipts.append({"record_id": record.id, "asset_id": asset.id,
                               "source_ref": source_ref, "sha256": handle.sha256,
                               "size_bytes": len(handle.data)})

    selection = Selection(id=content_id([record.id for record in records], "selection:"),
                          name="COCO 2017 val: first caption for 100 distinct preview images",
                          ids=[record.id for record in records], unit="example",
                          snapshot_ids=[dataset.snapshot_id], dataset_ids=[dataset.id],
                          method="first_caption_per_image_in_sorted_source_image_id_order",
                          created_at=datetime.now(timezone.utc).isoformat())
    (work / "selection.json").write_text(selection.model_dump_json(indent=2) + "\n")
    (work / "records.json").write_text(json.dumps([r.model_dump(mode="json") for r in records], indent=2) + "\n")
    source = {"source_registry": "registry/datasets/coco.yaml", "source_pack": "work/packs/coco/pack.json",
              "source_pack_sha256": _sha256(pack_path), "release": dataset.release,
              "snapshot_id": dataset.snapshot_id,
              "images_archive_sha256": dataset.adapter_config.get("images_sha256"),
              "annotations_archive_sha256": dataset.adapter_config.get("annotations_sha256"),
              "selection_method": selection.method, "source_images": image_receipts,
              "rights": dataset.rights}
    return selection, records, source


def _vectors(artifact) -> dict[str, list[float]]:
    items = artifact.data["items"]
    if any(item["status"] != "completed" for item in items):
        raise ValueError("Embedding analysis needs complete selected vectors")
    return {item["id"]: item["output"]["vector"] for item in items}


def _person_diagnostics(records: list[Record], artifact) -> dict:
    predicted = {item["id"]: item for item in artifact.data["items"]}
    rows = []
    for record in records:
        item = predicted[record.id]
        if item["status"] != "completed":
            raise ValueError("Person diagnostics require complete COCO detections")
        assets = item["output"]["assets"]
        if len(assets) != 1 or assets[0]["status"] != "completed":
            raise ValueError("Expected one completed image per COCO caption")
        detections = [d for d in assets[0]["detections"] if d["class"] == "person" and d["score"] >= 0.5]
        rows.append({"id": record.id, "source_image_id": record.source["image_id"],
                     "source_person_instance_count": record.source["person_count"],
                     "predicted_person_box_count_score_ge_0_5": len(detections),
                     "predicted_person_boxes_score_ge_0_5": detections})
    return {"threshold": 0.5, "rows": rows,
            "images_with_source_person_instances": sum(row["source_person_instance_count"] > 0 for row in rows),
            "images_with_predicted_person_boxes": sum(row["predicted_person_box_count_score_ge_0_5"] > 0 for row in rows),
            "total_source_person_instances": sum(row["source_person_instance_count"] for row in rows),
            "total_predicted_person_boxes": sum(row["predicted_person_box_count_score_ge_0_5"] for row in rows),
            "interpretation": "Descriptive count comparison on this 100-image selection; not COCO AP, recall, or official detection accuracy."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    work = root / "work/demo-analysis-coco"
    work.mkdir(parents=True, exist_ok=True)
    selection, records, source = _selection(root, work)
    models = root / "work/models"
    for relative, expected in MODEL_HASHES.items():
        if _sha256(models / relative) != expected:
            raise ValueError(f"Prepared model hash mismatch: {relative}")
    media = work / "media"
    base = {"asset_roots": [str(media)], "model_roots": [str(models)], "max_records": 100,
            "input_representation": "100 distinct COCO-2017-val preview images, first original caption per image"}
    model_configs = {
        "quality.basic": base,
        "detect.nudenet": {**base, "model_path": str(models / "nudenet-320n.onnx"),
                           "model_sha256": MODEL_HASHES["nudenet-320n.onnx"], "extraction_threshold": 0.25},
        "detect.coco_v1": {**base, "weights_path": str(models / "fasterrcnn_mobilenet_v3_large_320_fpn-907ea3f9.pth"),
                           "weights_sha256": MODEL_HASHES["fasterrcnn_mobilenet_v3_large_320_fpn-907ea3f9.pth"],
                           "extraction_threshold": 0.05},
        "embed.minilm": {**base, "model_path": str(models / "minilm-l6-v2"),
                         "model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                         "model_sha256": MODEL_HASHES["minilm-l6-v2/model.safetensors"], "representation": "text"},
        "embed.siglip2": {**base, "model_path": str(models / "siglip2-base-patch16-224"),
                          "model_revision": "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2",
                          "model_sha256": MODEL_HASHES["siglip2-base-patch16-224/model.safetensors"],
                          "representation": "image"},
    }
    receipt = {"schema_version": "1.0", "source": source,
               "population_scope": "100 distinct images selected from the complete COCO-2017-val source in sorted image-ID order; one source caption each",
               "selection_id": selection.id, "selection_ids": selection.ids,
               "model_sha256": MODEL_HASHES, "runs": {}, "links": {}}
    report_path = root / "reports/analysis-demo-coco-100.json"
    if report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get("selection_id") == selection.id:
            for key in ("main_work_import",):
                if key in previous:
                    receipt[key] = previous[key]

    def record_result(key, run, artifact):
        receipt["runs"][key] = {"run_id": run.id, "processor_id": run.processor_id,
                                "status": run.status, "coverage": artifact.coverage,
                                "artifact_id": artifact.id,
                                "artifact_manifest": str((work / "artifacts" / artifact.files["manifest"]).relative_to(root)),
                                "processor_provenance": artifact.provenance.get("processor_provenance", {})}
        report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    manager = JobManager(work)
    try:
        artifacts = {}
        for processor_id, config in model_configs.items():
            run, artifact = _run(manager, selection, records, processor_id, config)
            artifacts[processor_id] = artifact
            record_result(processor_id, run, artifact)
        receipt["links"]["person_diagnostics"] = _person_diagnostics(records, artifacts["detect.coco_v1"])
        source_people = {record.id: int(record.source["person_count"]) for record in records}
        predicted_people = {row["id"]: row["predicted_person_box_count_score_ge_0_5"]
                            for row in receipt["links"]["person_diagnostics"]["rows"]}
        for embedding_id, label in (("embed.minilm", "caption"), ("embed.siglip2", "image")):
            embedding = artifacts[embedding_id]
            vectors = _vectors(embedding)
            analysis_base = {"vectors": vectors,
                             "embedding_space_id": embedding.provenance["processor_provenance"]["embedding_space_id"],
                             "embedding_run_id": embedding.run_id, "max_records": 100,
                             "input_representation": f"{label} embedding from {embedding_id} on selected COCO examples"}
            for processor_id, details in {
                "project.pca": {}, "project.umap": {"seed": 42, "neighbors": 15, "metric": "cosine", "min_dist": 0.1},
                "cluster.kmeans": {"seed": 42, "clusters": 8}, "outlier.knn": {"neighbors": 5, "metric": "cosine"},
            }.items():
                run, artifact = _run(manager, selection, records, processor_id, {**analysis_base, **details})
                key = f"{label}.{processor_id}"
                artifacts[key] = artifact
                record_result(key, run, artifact)
            receipt["links"][f"{label}_umap_colored_by_source_person_count"] = [
                {"id": point["id"], "x": point["x"], "y": point["y"],
                 "source_person_instance_count": source_people[point["id"]],
                 "predicted_person_box_count_score_ge_0_5": predicted_people[point["id"]]}
                for point in artifacts[f"{label}.project.umap"].data["points"]]
            receipt["links"][f"{label}_outliers_top_10"] = sorted(
                artifacts[f"{label}.outlier.knn"].data["points"],
                key=lambda point: (-point["outlier_score"], point["id"]))[:10]
        compared = [record.model_copy(update={"prediction": {"coco_person_count_score_ge_0_5": predicted_people[record.id]}})
                    for record in records]
        compare_config = {"left_field": "source.person_count", "right_field": "prediction.coco_person_count_score_ge_0_5",
                          "kind": "correlation", "population_scope": "selected COCO-2017-val preview images",
                          "source_artifact_id": artifacts["detect.coco_v1"].id, "max_records": 100}
        run, artifact = _run(manager, selection, compared, "compare.fields", compare_config)
        record_result("compare.fields", run, artifact)
        from importlib.metadata import version
        receipt["packages"] = {name: version(name) for name in
                               ("numpy", "Pillow", "torch", "torchvision", "nudenet", "onnxruntime",
                                "sentence-transformers", "transformers", "sentencepiece", "umap-learn", "scikit-learn")}
        report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    finally:
        manager.close()
    print(f"receipt {report_path}", flush=True)


if __name__ == "__main__":
    main()
