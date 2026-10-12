"""The columnar embedding path: accounting, de-duplication and, where the pinned weights exist, parity with the legacy path."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from dataset_atlas.models import Asset, Record
from dataset_atlas.processors import embeddings

torch = pytest.importorskip("torch")
ROOT = Path(__file__).resolve().parents[2]
RECIPES = ROOT / "local-config/recipes.json"
WEIGHTS = ROOT / "work/models/siglip2-base-patch16-224/model.safetensors"
needs_weights = pytest.mark.skipif(not (RECIPES.is_file() and WEIGHTS.is_file()), reason="pinned local model weights are not installed")


def image_record(record_id: str, path: Path | None, *, extra: Path | None = None) -> Record:
    assets = [Asset(id=f"asset:{p.name}", dataset_id="d", release_id="v1", modality="image", uri=str(p)) for p in (path, extra) if p]
    return Record(id=record_id, dataset_id="d", release_id="v1", snapshot_id="s", assets=assets)


def jpeg(directory: Path, name: str, seed: int) -> Path:
    rng = np.random.default_rng(seed)
    path = directory / name
    Image.fromarray((rng.random((60, 80, 3)) * 255).astype(np.uint8)).save(path, quality=90)
    return path


@pytest.fixture
def fake_siglip(monkeypatch):
    """A stand-in model that records how many images it embeds, so de-duplication is observable."""
    calls = {"images": 0, "batches": 0}
    projection = torch.from_numpy(np.random.default_rng(0).normal(size=(3, 768)).astype(np.float32))

    class Model:
        def get_image_features(self, pixel_values):
            calls["images"] += len(pixel_values)
            calls["batches"] += 1
            return pixel_values.float().mean(dim=(2, 3)) @ projection

    extractor = SimpleNamespace(size={"width": 32, "height": 32}, image_mean=[0.5] * 3, image_std=[0.5] * 3, rescale_factor=1 / 255, resample=2)
    loaded = {"model": Model(), "processor": SimpleNamespace(image_processor=extractor), "torch": torch, "device": "cpu", "dtype": torch.float32}
    monkeypatch.setattr(embeddings, "_bulk_model", lambda processor_id, config: (loaded, {"precision": "fp32", "model_id": "fake"}))
    return calls


def test_every_record_is_a_row_or_a_skip_and_each_distinct_image_is_embedded_once(tmp_path, fake_siglip):
    shared, other, extra = jpeg(tmp_path, "a.jpg", 1), jpeg(tmp_path, "b.jpg", 2), jpeg(tmp_path, "c.jpg", 3)
    (tmp_path / "bad.jpg").write_bytes(b"not an image")
    records = [image_record("q1", shared), image_record("q2", shared), image_record("q3", other), image_record("none", None),
               image_record("two", shared, extra=extra), image_record("broken", tmp_path / "bad.jpg"),
               image_record("gone", tmp_path / "missing.jpg")]
    out, provenance = embeddings.run_embeddings_bulk("embed.siglip2", records, {"asset_roots": [str(tmp_path)], "batch_size": 2, "storage_dtype": "float16"})
    assert out.ids == ["q1", "q2", "q3"] and set(out.skipped) == {"none", "two", "broken", "gone"}
    assert out.skipped["none"]["status"] == "not_applicable" and out.skipped["two"]["status"] == "skipped"
    assert out.skipped["broken"]["status"] == out.skipped["gone"]["status"] == "failed" and "error" in out.skipped["broken"]
    vectors = out.arrays["vector"]
    assert vectors.dtype == np.float16 and vectors.shape == (3, 768)
    assert np.array_equal(vectors[0], vectors[1]) and not np.array_equal(vectors[0], vectors[2])
    assert np.allclose(np.linalg.norm(vectors.astype(np.float32), axis=1), 1, atol=2e-3)
    assert fake_siglip["images"] == 2, "records that share an image share one forward pass"
    out.check([record.id for record in records])
    assert provenance["storage_dtype"] == "float16" and provenance["preprocessing"]["resize"] == [32, 32]
    assert provenance["embedding_space_id"].startswith("space:")


def test_bad_options_are_refused_before_any_work(fake_siglip, tmp_path):
    with pytest.raises(ValueError, match="storage_dtype"):
        embeddings.run_embeddings_bulk("embed.siglip2", [], {"storage_dtype": "float8"})
    with pytest.raises(ValueError, match="representation"):
        embeddings.run_embeddings_bulk("embed.minilm", [], {"representation": "image"})


def test_text_embedding_skips_blank_questions(monkeypatch):
    class Sentences:
        def encode(self, texts, **kwargs):
            return np.array([[len(text), 1.0, 0.0] + [0.0] * 381 for text in texts], dtype=np.float32)

    loaded = {"model": Sentences(), "torch": torch, "device": "cpu", "dtype": torch.float32}
    monkeypatch.setattr(embeddings, "_bulk_model", lambda processor_id, config: (loaded, {"precision": "fp32"}))
    records = [Record(id=f"r{i}", dataset_id="d", release_id="v1", snapshot_id="s", question=question)
               for i, question in enumerate(["what is it", "  ", None, "how many"])]
    out, _ = embeddings.run_embeddings_bulk("embed.minilm", records, {"representation": "question", "batch_size": 2})
    assert out.ids == ["r0", "r3"] and set(out.skipped) == {"r1", "r2"} and out.arrays["vector"].shape == (2, 384)
    assert all(row["status"] == "not_applicable" for row in out.skipped.values())


@needs_weights
def test_columnar_fp32_matches_the_legacy_path_and_reduced_precision_stays_close(tmp_path):
    recipe = json.loads(RECIPES.read_text())["embed.siglip2"]
    config = {**recipe, "model_roots": [str(ROOT / "work/models")], "asset_roots": [str(tmp_path)], "representation": "image", "device": "cpu"}
    records = [image_record(f"r{i}", jpeg(tmp_path, f"i{i}.jpg", 10 + i)) for i in range(3)]
    items, legacy_provenance = embeddings.run_embeddings("embed.siglip2", records, config)
    legacy = np.array([item["output"]["vector"] for item in items])
    out, provenance = embeddings.run_embeddings_bulk("embed.siglip2", records, {**config, "precision": "fp32"})
    assert out.ids == [r.id for r in records]
    assert (out.arrays["vector"] * legacy).sum(1).min() > 0.99999, "the columnar preprocessing and the model processor give the same vectors"
    assert provenance["embedding_space_id"] == legacy_provenance["embedding_space_id"]


@needs_weights
def test_embedding_then_projection_and_clustering_through_the_job_manager(tmp_path):
    """The whole chain a user triggers: embed a selection into arrays, then analyse it by reference."""
    from dataset_atlas.jobs import JobManager
    from dataset_atlas.models import Selection
    from dataset_atlas.queries.embedding_space import embedding_source

    recipe = json.loads(RECIPES.read_text())["embed.siglip2"]
    images = tmp_path / "images"
    images.mkdir()
    records = [image_record(f"r{i:02d}", jpeg(images, f"i{i}.jpg", i)) for i in range(40)]
    selection = Selection(id="chain", ids=[r.id for r in records], unit="example", snapshot_ids=["s"], dataset_ids=["d"], created_at="2026-01-01T00:00:00Z")
    manager = JobManager(tmp_path / "work")

    def finish(run_id):
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            run = manager.get_run(run_id)
            if run.status not in ("queued", "running"):
                return run
            time.sleep(0.2)
        pytest.fail("run did not settle")

    config = {**recipe, "model_roots": [str(ROOT / "work/models")], "asset_roots": [str(images)], "representation": "image",
              "storage": "arrays", "device": "cuda" if torch.cuda.is_available() else "cpu", "batch_records": 16}
    embedded = finish(manager.create(selection, records, "embed.siglip2", config).id)
    assert embedded.status == "completed", embedded.errors
    artifact = manager.get_artifact(embedded.artifact_ids[0])
    assert artifact.data["bulk"]["arrays"]["vector"]["shape"] == [40, 768] and "items" not in artifact.data
    source, provenance, _ = embedding_source(artifact, manager.artifact_dir)
    analysis = {"storage": "arrays", "backend": "cpu", "vector_source": source, "embedding_space_id": provenance["embedding_space_id"],
                "embedding_run_id": embedded.id, "embedding_artifact_id": artifact.id}
    projected = finish(manager.create(selection, records, "project.pca", {**analysis, "dimensions": 3}).id)
    assert projected.status == "completed", projected.errors
    projection = manager.get_artifact(projected.artifact_ids[0])
    assert projection.data["bulk"]["arrays"]["coords"]["shape"] == [40, 3]
    assert projection.provenance["processor_provenance"]["embedding_artifact_id"] == artifact.id
    clustered = finish(manager.create(selection, records, "cluster.kmeans", {**analysis, "clusters": 4}).id)
    assert clustered.status == "completed", clustered.errors
    assert manager.get_artifact(clustered.artifact_ids[0]).data["summary"]["cluster_count"] == 4
