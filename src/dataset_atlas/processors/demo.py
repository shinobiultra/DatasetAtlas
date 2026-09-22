"""Reproduce the bounded local CLEVR analysis receipt with prepared local models.

Run ``python -m dataset_atlas.processors.demo --root /path/to/DatasetAtlas``.
No model or dataset is downloaded by this command. It writes only to work/demo-analysis
and reports/analysis-demo-clevr-100.json.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import yaml

from dataset_atlas.jobs.manager import JobManager
from dataset_atlas.models import Asset, Record, Selection, content_id, stable_id


MODEL_HASHES = {
    "nudenet-320n.onnx": "c15d8273adad2d0a92f014cc69ab2d6c311a06777a55545f2c4eb46f51911f0f",
    "fasterrcnn_mobilenet_v3_large_320_fpn-907ea3f9.pth": "907ea3f91ff92242bc1baea8049276a3e76bca48ce7560bd268cc029f37977b5",
    "minilm-l6-v2/model.safetensors": "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db",
    "siglip2-base-patch16-224/model.safetensors": "612923381c76ec5a9bed335d1c48827e3f2e506ac31b044b63b2031fadee6a0b",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selection(root: Path) -> tuple[Selection, list[Record], Path, dict]:
    registry = yaml.safe_load((root / "registry/datasets/clevr.yaml").read_text())
    if registry["rights"]["images"] != "approved":
        raise ValueError("CLEVR image rights are not approved in registry")
    source_path = root / registry["adapter_config"]["path"]
    if _sha256(source_path) != registry["adapter_config"]["sha256"]:
        raise ValueError("Pinned CLEVR question source checksum mismatch")
    media_root = root / registry["adapter_config"]["media_root"]
    questions = json.loads(source_path.read_text())["questions"]
    first_by_image: dict[str, dict] = {}
    for question in questions:
        filename = question["image_filename"]
        if (media_root / filename).is_file():
            first_by_image.setdefault(filename, question)
    chosen = [first_by_image[name] for name in sorted(first_by_image)]
    if len(chosen) != 100:
        raise ValueError(f"Expected 100 locally prepared distinct CLEVR images; found {len(chosen)}")
    records = []
    for question in chosen:
        filename = question["image_filename"]
        asset_id = stable_id("clevr", registry["release"], "asset", filename)
        asset = Asset(id=asset_id, dataset_id="clevr", release_id=registry["release"], modality="image", uri=filename)
        records.append(Record(id=stable_id("clevr", registry["release"], "example", str(question["question_index"])),
                              dataset_id="clevr", release_id=registry["release"], snapshot_id=registry["snapshot_id"],
                              asset_ids=[asset_id], assets=[asset], question=question["question"],
                              source={"answer": question["answer"], "image_filename": filename}))
    selection = Selection(id=content_id([record.id for record in records], "selection:"),
                          name="CLEVR pinned subset: first question for each of 100 images",
                          ids=[record.id for record in records], unit="example",
                          snapshot_ids=[registry["snapshot_id"]], dataset_ids=["clevr"],
                          method="first_question_per_available_image",
                          created_at=datetime.now(timezone.utc).isoformat())
    return selection, records, media_root, registry


def _run(manager: JobManager, selection: Selection, records: list[Record], processor_id: str, config: dict):
    for prior in manager.list_runs():
        if (prior.processor_id == processor_id and prior.selection_id == selection.id and
                prior.config == config and prior.status == "completed" and prior.artifact_ids):
            artifact = manager.get_artifact(prior.artifact_ids[0])
            print(f"reused {processor_id} {prior.id} {artifact.id}", flush=True)
            return prior, artifact
    run = manager.create(selection, records, processor_id, config)
    print(f"started {processor_id} {run.id}", flush=True)
    last_notice = time.monotonic()
    while True:
        run = manager.get_run(run.id)
        if run.status in {"completed", "partial", "failed", "cancelled"}:
            break
        if time.monotonic() - last_notice >= 20:
            print(f"progress {processor_id} {run.progress}", flush=True)
            last_notice = time.monotonic()
        time.sleep(1)
    print(f"finished {processor_id} {run.status} {run.progress} artifacts={run.artifact_ids}", flush=True)
    if run.status != "completed" or not run.artifact_ids:
        raise RuntimeError(f"{processor_id} did not complete: {run.errors[:3]}")
    artifact = manager.get_artifact(run.artifact_ids[0])
    reloaded = type(artifact).model_validate_json(artifact.model_dump_json())
    if reloaded.id != artifact.id or len(reloaded.data["items"]) != len(records):
        raise RuntimeError("Artifact export/reload mismatch")
    return run, artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    selection, records, media_root, registry = _selection(root)
    models = root / "work/models"
    for relative, expected in MODEL_HASHES.items():
        if _sha256(models / relative) != expected:
            raise ValueError(f"Prepared model hash mismatch: {relative}")
    work = root / "work/demo-analysis"
    work.mkdir(parents=True, exist_ok=True)
    (work / "selection.json").write_text(selection.model_dump_json(indent=2) + "\n")
    (work / "records.json").write_text(json.dumps([r.model_dump(mode="json") for r in records], indent=2) + "\n")
    base = {"asset_roots": [str(media_root)], "model_roots": [str(models)], "max_records": 100,
            "input_representation": "pinned CLEVR validation first question per image"}
    model_configs = {
        "quality.basic": base,
        "detect.nudenet": {**base, "model_path": str(models / "nudenet-320n.onnx"),
                           "model_sha256": MODEL_HASHES["nudenet-320n.onnx"], "extraction_threshold": 0.25},
        "detect.coco_v1": {**base, "weights_path": str(models / "fasterrcnn_mobilenet_v3_large_320_fpn-907ea3f9.pth"),
                           "weights_sha256": MODEL_HASHES["fasterrcnn_mobilenet_v3_large_320_fpn-907ea3f9.pth"], "extraction_threshold": 0.05},
        "embed.minilm": {**base, "model_path": str(models / "minilm-l6-v2"),
                         "model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                         "model_sha256": MODEL_HASHES["minilm-l6-v2/model.safetensors"], "representation": "question"},
        "embed.siglip2": {**base, "model_path": str(models / "siglip2-base-patch16-224"),
                          "model_revision": "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2",
                          "model_sha256": MODEL_HASHES["siglip2-base-patch16-224/model.safetensors"], "representation": "image"},
    }
    manager = JobManager(work)
    receipt = {"schema_version": "1.0", "source_registry": "registry/datasets/clevr.yaml",
               "snapshot_id": registry["snapshot_id"], "source_question_sha256": registry["adapter_config"]["sha256"],
               "population_scope": "100 distinct images in pinned third-party CLEVR validation subset; one source question per image",
               "selection_id": selection.id, "selection_ids": selection.ids, "model_sha256": MODEL_HASHES,
               "runs": {}, "links": {}}
    report_path = root / "reports/analysis-demo-clevr-100.json"
    if report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get("selection_id") == selection.id:
            for key in ("retrieval", "main_work_import", "preparation_attempts", "query_encoding"):
                if key in previous:
                    receipt[key] = previous[key]

    def record_result(processor_id, run, artifact):
        receipt["runs"][processor_id] = {"run_id": run.id, "status": run.status,
                                         "coverage": artifact.coverage, "artifact_id": artifact.id,
                                         "artifact_manifest": str((work / "artifacts" / artifact.files["manifest"]).relative_to(root)),
                                         "processor_provenance": artifact.provenance.get("processor_provenance", {})}
        report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    try:
        artifacts = {}
        for processor_id, config in model_configs.items():
            run, artifact = _run(manager, selection, records, processor_id, config)
            artifacts[processor_id] = artifact
            record_result(processor_id, run, artifact)
        mini = artifacts["embed.minilm"]
        vectors = {item["id"]: item["output"]["vector"] for item in mini.data["items"]}
        space = mini.provenance["processor_provenance"]["embedding_space_id"]
        analysis_base = {"vectors": vectors, "embedding_space_id": space, "embedding_run_id": mini.run_id,
                         "max_records": 100, "input_representation": "MiniLM source question only"}
        for processor_id, details in {
            "project.pca": {}, "project.umap": {"seed": 42, "neighbors": 15, "metric": "cosine", "min_dist": 0.1},
            "cluster.kmeans": {"seed": 42, "clusters": 8}, "outlier.knn": {"neighbors": 5, "metric": "cosine"},
        }.items():
            run, artifact = _run(manager, selection, records, processor_id, {**analysis_base, **details})
            artifacts[processor_id] = artifact
            record_result(processor_id, run, artifact)
        coco_count = {item["id"]: item["output"]["derived"]["detection_count_v1"]
                      for item in artifacts["detect.coco_v1"].data["items"]}
        compared_records = [record.model_copy(update={"prediction": {"coco_detection_count_v1": coco_count[record.id]}})
                            for record in records]
        compare_config = {"left_field": "source.answer", "right_field": "prediction.coco_detection_count_v1",
                          "kind": "grouped_numeric", "population_scope": "pinned third-party CLEVR subset selection",
                          "source_artifact_id": artifacts["detect.coco_v1"].id, "max_records": 100}
        run, artifact = _run(manager, selection, compared_records, "compare.fields", compare_config)
        artifacts["compare.fields"] = artifact
        record_result("compare.fields", run, artifact)
        receipt["links"]["umap_colored_by_coco_detection_count"] = [
            {"id": point["id"], "x": point["x"], "y": point["y"], "detection_count_v1": coco_count[point["id"]]}
            for point in artifacts["project.umap"].data["points"]]
        receipt["links"]["outliers_top_10"] = sorted(artifacts["outlier.knn"].data["points"],
                                                       key=lambda point: (-point["outlier_score"], point["id"]))[:10]
        from importlib.metadata import version
        receipt["packages"] = {name: version(name) for name in
                               ("numpy", "Pillow", "torch", "torchvision", "nudenet", "onnxruntime",
                                "sentence-transformers", "transformers", "sentencepiece", "umap-learn",
                                "scikit-learn", "lancedb")}
        report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    finally:
        manager.close()
    print(f"receipt {report_path}", flush=True)


if __name__ == "__main__":
    main()
