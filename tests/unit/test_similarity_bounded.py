"""Exact synthetic retrieval stays bounded when its vectors are memory-mapped."""
from __future__ import annotations

import numpy as np
import pytest

from dataset_atlas.models import Artifact
from dataset_atlas.queries import similarity
from dataset_atlas.storage import arrays as store


def embedding(tmp_path, vectors, *, ids=None, metric="cosine", name="bounded"):
    ids = ids or [f"row-{i:05}" for i in range(len(vectors))]
    manifest = store.write_bundle(tmp_path / "arrays" / name, ids, {"vector": vectors})
    return Artifact(
        id=name, kind="embed.siglip2", run_id="synthetic", snapshot_ids=["synthetic-snapshot"],
        unit="example", ids=ids,
        provenance={"processor_provenance": {"embedding_space_id": "synthetic-space", "embedding_space": {"metric": metric}}},
        data={"bulk": {"dir": f"arrays/{name}", **manifest}},
    )


@pytest.mark.parametrize("metric", ["cosine", "euclidean"])
@pytest.mark.parametrize("dtype", [np.float16, np.float32, np.float64])
def test_memmap_search_matches_an_independent_float64_reference(tmp_path, monkeypatch, metric, dtype):
    # A random fixture with well-separated neighbours catches omitted/duplicated chunks,
    # wrong metric arithmetic, dtype conversion errors and eligibility leakage.
    vectors = np.random.default_rng(52).normal(size=(137, 11)).astype(dtype)
    artifact = embedding(tmp_path, vectors, metric=metric)
    monkeypatch.setattr(similarity, "_DISTANCE_BLOCK_BYTES", 11 * 8 * 7, raising=False)
    eligible = [*artifact.ids[2::3], artifact.ids[2], "absent", artifact.ids[7]]
    query = vectors[7].astype(np.float32)
    reference = []
    for item_id in set(eligible) - {"absent", artifact.ids[7]}:
        vector = vectors[artifact.ids.index(item_id)].astype(np.float32).astype(np.float64)
        query64 = query.astype(np.float64)
        distance = (max(0.0, 1 - np.dot(vector, query64) / (np.linalg.norm(vector) * np.linalg.norm(query64)))
                    if metric == "cosine" else np.linalg.norm(vector - query64))
        reference.append((distance, item_id))
    expected = sorted(reference)[:13]
    found = similarity.similar_records_bulk(artifact, artifact.ids[7], eligible, 13, tmp_path)
    assert found["eligible_count"] == len(reference)
    assert [result["id"] for result in found["results"]] == [item_id for _, item_id in expected]
    np.testing.assert_allclose([result["distance"] for result in found["results"]], [distance for distance, _ in expected], rtol=3e-6, atol=2e-7)


def test_every_gather_from_the_memmap_is_bounded(tmp_path, monkeypatch):
    # A return to matrix[all_eligible_rows] must fail even on this small fixture.
    vectors = np.arange(401 * 12, dtype=np.float32).reshape(401, 12)
    artifact = embedding(tmp_path, vectors)
    matrix = np.load(tmp_path / "arrays/bounded/vector.npy", mmap_mode="r")
    gathered_bytes = []

    class ObservedMemmap(np.memmap):
        def __getitem__(self, key):
            result = super().__getitem__(key)
            if isinstance(key, np.ndarray):
                gathered_bytes.append(result.nbytes)
            return result

    observed = matrix.view(ObservedMemmap)
    monkeypatch.setattr(similarity, "_bulk_matrix", lambda *args: (artifact.ids, {item_id: i for i, item_id in enumerate(artifact.ids)}, observed))
    block_bytes = 12 * 4 * 9
    monkeypatch.setattr(similarity, "_DISTANCE_BLOCK_BYTES", block_bytes, raising=False)
    answer = similarity.similar_records_bulk(artifact, artifact.ids[3], artifact.ids, 5, tmp_path)
    assert len(answer["results"]) == 5
    assert gathered_bytes and max(gathered_bytes) <= block_bytes


@pytest.mark.parametrize("metric", ["cosine", "euclidean"])
def test_cutoff_ties_choose_smallest_ids_across_every_chunk(tmp_path, monkeypatch, metric):
    ids = ["query", *[f"tie-{i:03}" for i in range(93, -1, -1)]]
    vectors = np.tile(np.array([1.0, 0.0], dtype=np.float32), (len(ids), 1))
    artifact = embedding(tmp_path, vectors, ids=ids, metric=metric)
    monkeypatch.setattr(similarity, "_DISTANCE_BLOCK_BYTES", 2 * 4 * 7, raising=False)
    found = similarity.similar_records_bulk(artifact, "query", ids, 9, tmp_path)
    assert [item["id"] for item in found["results"]] == [f"tie-{i:03}" for i in range(9)]
    assert [item["distance"] for item in found["results"]] == [0.0] * 9


def test_zero_candidates_have_cosine_distance_one_and_query_is_excluded(tmp_path):
    artifact = embedding(tmp_path, np.array([[1, 0], [0, 0], [0, 1], [-1, 0]], dtype=np.float32), ids=["q", "zero", "orthogonal", "opposite"])
    found = similarity.similar_records_bulk(artifact, "q", ["zero", "zero", "missing", "q", "opposite", "orthogonal"], 10, tmp_path)
    assert found["eligible_count"] == 3
    assert found["results"] == [{"id": "orthogonal", "distance": 1.0}, {"id": "zero", "distance": 1.0}, {"id": "opposite", "distance": 2.0}]


@pytest.mark.parametrize("query", [[0.0, 0.0], [float("nan"), 1.0], [float("inf"), 1.0], [1.0]])
def test_invalid_query_is_rejected_before_scoring(tmp_path, query):
    artifact = embedding(tmp_path, np.array([[1, 0], [0, 1]], dtype=np.float32))
    with pytest.raises(ValueError, match="nonzero|invalid dimensions or values"):
        similarity.similar_records_bulk(artifact, None, artifact.ids, 1, tmp_path, query_vector=query)


def test_oversize_matrix_is_not_retained_in_the_cache(tmp_path, monkeypatch):
    # Entry-count eviction alone cannot bound retained storage of large spaces.
    artifact = embedding(tmp_path, np.ones((101, 17), dtype=np.float32))
    monkeypatch.setattr(similarity, "_MATRIX_CACHE_BYTES", 1, raising=False)
    similarity._matrices.clear()
    reads = []
    read_array = store.read_array

    def observed_read(*args, **kwargs):
        value = read_array(*args, **kwargs)
        reads.append(value)
        return value

    monkeypatch.setattr(store, "read_array", observed_read)
    for _ in range(2):
        similarity.similar_records_bulk(artifact, artifact.ids[0], artifact.ids, 1, tmp_path)
    assert len(reads) == 2
    assert all(isinstance(value, np.memmap) for value in reads)
    assert not similarity._matrices


def test_nonfinite_candidates_are_refused_without_returning_nan_json(tmp_path):
    artifact = embedding(tmp_path, np.array([[1, 0], [0, 1]], dtype=np.float32))
    path = tmp_path / "arrays/bounded/vector.npy"
    values = np.load(path, mmap_mode="r+")
    values[1, 0] = np.nan
    values.flush()
    artifact.data["bulk"]["arrays"]["vector"]["sha256"] = store.sha256_file(path)
    with pytest.raises(ValueError, match="invalid dimensions or values"):
        similarity.similar_records_bulk(artifact, artifact.ids[0], artifact.ids, 1, tmp_path)


@pytest.mark.parametrize("dtype", [np.float16, np.float32, np.float64])
def test_loading_a_space_retains_its_memmap_without_an_eager_dtype_copy(tmp_path, dtype):
    artifact = embedding(tmp_path, np.ones((101, 17), dtype=dtype))
    _, _, matrix = similarity._bulk_matrix(artifact, tmp_path)
    assert isinstance(matrix, np.memmap)
    assert matrix.dtype == np.dtype(dtype)


def test_byte_cap_evicts_a_second_space_even_when_both_fit_individually(tmp_path, monkeypatch):
    artifacts = [embedding(tmp_path, np.ones((4, 1024), dtype=np.float32), name=name) for name in ("first", "second")]
    monkeypatch.setattr(similarity, "_MATRIX_CACHE_BYTES", 30_000)
    similarity._matrices.clear()
    reads = []
    read_array = store.read_array

    def observed_read(*args, **kwargs):
        reads.append(args[0].name)
        return read_array(*args, **kwargs)

    monkeypatch.setattr(store, "read_array", observed_read)
    for index in (0, 0, 1, 1, 0):
        similarity._bulk_matrix(artifacts[index], tmp_path)
    assert reads == ["first", "second", "first"]
