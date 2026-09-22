from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dataset_atlas.models import Asset, Record
from dataset_atlas.processors import describe_processors, encode_text_query, run_processor
from dataset_atlas.processors.analysis import exact_lancedb_search, knn_outlier, pca
from dataset_atlas.processors.vision import _normalize_coco, _normalize_nudenet


def record(item_id="r1", **kwargs):
    return Record(id=item_id, dataset_id="d", release_id="v1", snapshot_id="snap", **kwargs)


def asset(item_id, uri, sha256=None):
    return Asset(id=item_id, dataset_id="d", release_id="v1", modality="image", uri=uri, sha256=sha256)


def test_quality_duplicate_and_missing_asset_states(tmp_path: Path):
    Image.new("RGB", (16, 8), "red").save(tmp_path / "same.png")
    (tmp_path / "bad.png").write_bytes(b"not an image")
    selection = [record("one", assets=[asset("a", "same.png")]),
                 record("two", assets=[asset("b", "same.png")]),
                 record("three", assets=[asset("c", "bad.png")]),
                 record("four", asset_ids=["unhydrated"]), record("five")]
    body = run_processor("quality.basic", selection, {"asset_roots": [str(tmp_path)]})
    by_id = {item["id"]: item for item in body["items"]}
    assert body["coverage"]["statuses"] == {"completed": 2, "failed": 1, "skipped": 1, "not_applicable": 1}
    assert by_id["one"]["output"]["assets"][0]["aspect_ratio"] == 2
    assert by_id["one"]["output"]["assets"][0]["file_sha256"] == by_id["two"]["output"]["assets"][0]["file_sha256"]
    assert by_id["three"]["output"]["assets"][0]["status"] == "failed"


def test_quality_rejects_path_escape_and_hash_mismatch(tmp_path: Path):
    Image.new("RGB", (4, 4)).save(tmp_path / "image.png")
    escaped = run_processor("quality.basic", [record(assets=[asset("a", "../image.png")])], {"asset_roots": [str(tmp_path)]})
    assert escaped["items"][0]["status"] == "failed"
    mismatched = run_processor("quality.basic", [record(assets=[asset("a", "image.png", "0" * 64)])], {"asset_roots": [str(tmp_path)]})
    assert mismatched["items"][0]["status"] == "failed"


def test_quality_exif_orientation_and_symlink_rejection(tmp_path: Path):
    image = Image.new("RGB", (6, 4))
    exif = Image.Exif()
    exif[274] = 6
    image.save(tmp_path / "oriented.jpg", exif=exif)
    result = run_processor("quality.basic", [record(assets=[asset("a", "oriented.jpg")])], {"asset_roots": [str(tmp_path)]})
    output = result["items"][0]["output"]["assets"][0]
    assert (output["width"], output["height"]) == (4, 6)
    (tmp_path / "link.jpg").symlink_to(tmp_path / "oriented.jpg")
    rejected = run_processor("quality.basic", [record(assets=[asset("b", "link.jpg")])], {"asset_roots": [str(tmp_path)]})
    assert rejected["items"][0]["status"] == "failed"


def test_detector_box_geometry_and_zero_detections(tmp_path: Path, monkeypatch):
    import dataset_atlas.processors.vision as vision
    Image.new("RGB", (10, 20)).save(tmp_path / "image.png")

    class FakeNudeDetector:
        calls = 0

        def detect(self, path):
            self.calls += 1
            assert Path(path).exists()
            return [{"class": "FACE_FEMALE", "score": 0.9, "box": [8, 18, 8, 8]}]

    fake = FakeNudeDetector()
    monkeypatch.setattr(vision, "_model", lambda processor_id, config: (fake, {"model_sha256": "test-only"}))
    body = run_processor("detect.nudenet", [record("one", assets=[asset("a", "image.png")]),
                                             record("two", assets=[asset("b", "image.png")])],
                         {"asset_roots": [str(tmp_path)], "extraction_threshold": 0.95})
    assert fake.calls == 1  # identical bytes are detected once
    assert all(item["status"] == "completed" and item["output"]["assets"][0]["detections"] == [] for item in body["items"])
    assert _normalize_nudenet([{"class": "FACE_FEMALE", "score": 0.9, "box": [8, 18, 8, 8]}], 10, 20, 0.05)[0]["box"] == [8.0, 18.0, 10.0, 20.0]
    assert _normalize_coco({"labels": [1], "scores": [0.8], "boxes": [[-1, 2, 12, 30]]}, ["background", "person"], 10, 20, 0.1)[0]["box"] == [0.0, 2.0, 10.0, 20.0]
    with pytest.raises(ValueError, match="internal NMS threshold"):
        run_processor("detect.nudenet", [record("empty")], {"extraction_threshold": 0.1})


def test_pca_and_original_space_outlier():
    matrix = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    first, explained = pca(matrix)
    second, _ = pca(matrix)
    assert np.allclose(first, second)
    assert pytest.approx(sum(explained)) == 1.0
    assert knn_outlier(matrix, 1, "euclidean").tolist() == pytest.approx([1.0, 1.0, 2.0])


def test_projection_missing_vectors_and_population_identity():
    records = [record("a"), record("b"), record("c")]
    config = {"vectors": {"a": [0, 0], "b": [1, 0]}, "embedding_space_id": "space-a", "embedding_run_id": "run-a"}
    body = run_processor("project.pca", records, config)
    assert body["items"][2]["status"] == "not_applicable"
    assert body["provenance"]["population_ids"] == ["a", "b", "c"]
    assert body["provenance"]["fitted_ids"] == ["a", "b"]
    assert body["items"][0]["output"].keys() == {"x", "y"}
    assert run_processor("project.pca", records, config)["provenance"]["fit_id"] == body["provenance"]["fit_id"]
    with pytest.raises(ValueError, match="embedding_space_id"):
        run_processor("project.pca", records, {"vectors": config["vectors"]})


def test_umap_real_local_implementation_when_installed():
    pytest.importorskip("umap")
    records = [record(str(i)) for i in range(6)]
    config = {"vectors": {str(i): [float(i), float(i * i), float(i % 2)] for i in range(6)},
              "embedding_space_id": "test-explicit-numeric-space", "embedding_run_id": "test-input-run",
              "neighbors": 2, "seed": 7}
    body = run_processor("project.umap", records, config)
    assert body["coverage"]["statuses"] == {"completed": 6}
    assert body["provenance"]["parameters"]["n_jobs"] == 1
    assert all(np.isfinite(list(item["output"].values())).all() for item in body["items"])


def test_minilm_local_model_contract_and_recipe_identity(tmp_path: Path, monkeypatch):
    import hashlib
    import dataset_atlas.processors.embeddings as embeddings
    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"local test weights")
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="model_revision"):
        embeddings._snapshot("embed.minilm", {"model_path": str(tmp_path), "model_revision": "main", "model_sha256": digest})

    class FakeSentenceTransformer:
        def __init__(self, path, **kwargs):
            assert Path(path).name.startswith("atlas-model-snapshot-")
            assert (Path(path) / "model.safetensors").read_bytes() == b"local test weights"
            assert kwargs["local_files_only"] is True
            assert kwargs["trust_remote_code"] is False

        def encode(self, values, **kwargs):
            assert values == ["Which colour?"]
            return np.ones((1, 384))

    class FakeModule:
        SentenceTransformer = FakeSentenceTransformer

    real_import = embeddings.importlib.import_module
    monkeypatch.setattr(embeddings.importlib, "import_module", lambda name: FakeModule if name == "sentence_transformers" else real_import(name))
    config = {"model_path": str(tmp_path), "model_revision": embeddings.RECIPES["embed.minilm"]["revision"],
              "model_sha256": digest, "representation": "question"}
    result = run_processor("embed.minilm", [record(question="Which colour?", text="Ignored text")], config)
    assert result["items"][0]["status"] == "completed"
    assert len(result["items"][0]["output"]["vector"]) == 384
    assert pytest.approx(np.linalg.norm(result["items"][0]["output"]["vector"])) == 1
    assert result["provenance"]["recipe"]["representation"] == "question"
    (tmp_path / "tokenizer.json").symlink_to(weights)
    with pytest.raises(ValueError, match="symlinked file"):
        run_processor("embed.minilm", [record(question="Which colour?")], config)


def test_siglip_cross_modal_pairing_checks_recipe_not_just_dimension():
    from dataset_atlas.processors.embeddings import RECIPES, compatible_siglip2_spaces
    recipe = {**RECIPES["embed.siglip2"], "normalization": "L2", "distance_metric": "cosine"}
    image = {"model_id": recipe["model_id"], "model_revision": recipe["revision"], "model_sha256": "a" * 64,
             "recipe": {**recipe, "representation": "image"}}
    text = {**image, "recipe": {**recipe, "representation": "question"}}
    assert compatible_siglip2_spaces(image, text)
    assert not compatible_siglip2_spaces(image, {**text, "model_sha256": "b" * 64})
    assert not compatible_siglip2_spaces(image, {**text, "recipe": {**text["recipe"], "dimension": 384}})


def test_text_query_requires_matching_registered_recipe(monkeypatch):
    import dataset_atlas.processors.queries as queries
    from dataset_atlas.models import Artifact
    from dataset_atlas.processors.embeddings import RECIPES
    recipe = {**RECIPES["embed.minilm"], "representation": "question", "normalization": "L2", "distance_metric": "cosine"}
    saved = {"model_id": recipe["model_id"], "model_revision": recipe["revision"],
             "model_sha256": "a" * 64, "recipe": recipe, "embedding_space_id": "space-test"}
    artifact = Artifact(id="artifact", kind="embed.minilm", snapshot_ids=["s"], unit="example", ids=["r"],
                        provenance={"processor_provenance": saved})
    config = {"model_path": "/local/model", "model_revision": recipe["revision"], "model_sha256": "a" * 64}

    def fake_run(processor_id, records, actual_config):
        assert processor_id == "embed.minilm"
        assert records[0].question == "A question?" and records[0].text is None
        assert actual_config["representation"] == "question"
        return [{"id": records[0].id, "status": "completed", "output": {"vector": [0.0] * 383 + [1.0]}}], {"embedding_space_id": "space-test"}

    monkeypatch.setattr(queries, "run_embeddings", fake_run)
    assert len(encode_text_query(artifact, config, "A question?")) == 384
    with pytest.raises(ValueError, match="model_sha256"):
        encode_text_query(artifact, {**config, "model_sha256": "b" * 64}, "A question?")
    with pytest.raises(ValueError, match="4000"):
        encode_text_query(artifact, config, "x" * 4001)
    monkeypatch.setattr(queries, "run_embeddings", lambda *args: (fake_run(*args)[0], {"embedding_space_id": "other"}))
    with pytest.raises(ValueError, match="recipe"):
        encode_text_query(artifact, config, "A question?")


def test_comparison_and_import_coverage():
    records = [record("a", source={"group": "A", "score": 1}),
               record("b", source={"group": "A", "score": 3}),
               record("c", source={"group": "B"})]
    result = run_processor("compare.fields", records, {"left_field": "source.group", "right_field": "source.score", "kind": "grouped_numeric", "population_scope": "preview"})
    summary = result["provenance"]["comparison"]
    assert summary["selected"] == 3 and summary["paired"] == 2 and summary["missing_right"] == 1
    assert summary["groups"][0]["mean"] == 2
    imported = run_processor("import.research", records, {"rows": [{"id": "a", "value": 0.3}], "field_id": "prediction.probe", "kind": "scalar", "source_reference": "local paper output 1", "rights": "private"})
    assert [item["status"] for item in imported["items"]] == ["completed", "not_applicable", "not_applicable"]
    with pytest.raises(ValueError, match="Duplicate"):
        run_processor("import.research", records, {"rows": [{"id": "a", "value": 0.3}, {"id": "a", "value": 0.4}], "field_id": "prediction.probe", "kind": "scalar", "source_reference": "local paper output 1", "rights": "private"})


def test_lancedb_contract_prefilters_before_exact_search():
    operations = []

    class Search:
        def where(self, sql, prefilter):
            operations.append(("where", sql, prefilter)); return self
        def distance_type(self, metric):
            operations.append(("distance", metric)); return self
        def bypass_vector_index(self):
            operations.append(("exact",)); return self
        def limit(self, count):
            operations.append(("limit", count)); return self
        def to_list(self):
            return [{"id": "a'b", "_distance": 0.1}]

    class Table:
        def search(self, vector, vector_column_name):
            operations.append(("search", vector, vector_column_name)); return Search()

    rows = exact_lancedb_search(Table(), [1, 0], ["a'b"], 2)
    assert rows[0]["id"] == "a'b"
    assert operations[1] == ("where", "id IN ('a''b')", True)
    assert ("exact",) in operations
    assert describe_processors()[0]["id"] == "quality.basic"
