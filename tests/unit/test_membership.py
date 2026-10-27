"""Synthetic coverage for artifact-aligned population membership, not native coverage."""
from pathlib import Path

import pytest

from dataset_atlas.models import Artifact, Asset, Dataset, FieldDescriptor, Pack, Query, Record
from dataset_atlas.queries import query_pack
from dataset_atlas.queries.membership import membership_mask
from dataset_atlas.queries.parquet import ParquetSnapshot, build_parquet_snapshot
from dataset_atlas.queries.results import attach_results


FIELDS = [
    FieldDescriptor(id="source.group", name="Group", dtype="category"),
    FieldDescriptor(id="source.score", name="Score", dtype="number", query_ops=["eq", "gt", "gte", "is_null"]),
]


def make_pack(count=31, *, scope="preview"):
    return Pack(
        dataset=Dataset(id="toy", name="Toy", release="r1", snapshot_id="s1"), fields=FIELDS,
        records=[Record(id=f"row-{index:06d}", dataset_id="toy", release_id="r1", snapshot_id="s1",
                        text=f"needle {index}" if index % 2 else f"record {index}",
                        source={"group": str(index % 3), "score": index}) for index in range(count)],
        population_scope=scope,
    )


def make_snapshot(tmp_path: Path, pack: Pack):
    path = tmp_path / "snapshot"
    build_parquet_snapshot(pack.records, pack.fields, path, root=tmp_path, dataset_id="toy", release_id="r1",
                           snapshot_id="s1", expected_count=len(pack.records), population_scope=pack.population_scope)
    return ParquetSnapshot(tmp_path, path)


def target(ids):
    return Artifact(id="map", kind="analysis.pca", snapshot_ids=["s1"], unit="example", ids=ids)


@pytest.mark.parametrize("scope", ["preview", "complete"])
def test_membership_includes_unloaded_rows_and_ignores_paging(tmp_path, scope):
    pack = make_pack(10_021, scope=scope)
    artifact = target(["row-010019", "row-000001", "missing", "row-010020"])
    query = Query(snapshot_id="s1", population_scope=scope, search="needle",
                  filter={"field_id": "source.score", "op": "gte", "value": 10_000}, limit=1, cursor="irrelevant-page")
    source = {"snapshot": make_snapshot(tmp_path, pack)} if scope == "complete" else {"pack": pack}
    assert membership_mask(query, artifact, **source) == bytes([1, 0, 0, 0])


@pytest.mark.parametrize("scope", ["preview", "complete"])
@pytest.mark.parametrize("sample", [
    {"method": "source", "size": 5},
    {"method": "random", "size": 9, "seed": 31},
    {"method": "stratified", "size": 8, "seed": 13, "field_id": "source.group"},
])
def test_sample_is_selected_from_full_population_before_artifact_intersection(tmp_path, scope, sample):
    pack = make_pack(scope=scope)
    query = Query(snapshot_id="s1", population_scope=scope, sample=sample,
                  sort=[{"field_id": "source.score", "direction": "desc"}], limit=1000)
    source = {"snapshot": make_snapshot(tmp_path, pack)} if scope == "complete" else {"pack": pack}
    selected = query_pack(pack, query).records
    selected_ids = {record.id for record in selected}
    # Deliberately omit selected rows and include non-selected rows: sampling the
    # artifact first would incorrectly fill the sample with these extra subjects.
    ids = [row.id for row in reversed(pack.records[::2])]
    artifact = target(ids)
    assert membership_mask(query, artifact, **source) == bytes(int(identity in selected_ids) for identity in ids)


@pytest.mark.parametrize("scope", ["preview", "complete"])
def test_selected_result_filter_and_stratification_apply_over_all_ids(tmp_path, scope):
    pack = make_pack(scope=scope)
    result = Artifact(id="labels", kind="import.research", snapshot_ids=["s1"], unit="example",
                      ids=[row.id for row in pack.records], data={"items": [
                          {"id": row.id, "status": "completed", "output": {"score": index, "label": str(index % 2)}}
                          for index, row in enumerate(pack.records)]})
    query = Query(snapshot_id="s1", population_scope=scope, result_snapshot_ids=["labels"], search="needle",
                  filter={"field_id": "prediction.labels.score", "op": "gt", "value": 5},
                  sample={"method": "stratified", "size": 4, "seed": 7, "field_id": "prediction.labels.label"}, limit=1000)
    expected = {row.id for row in query_pack(attach_results(pack, [result]), query).records}
    artifact = target([row.id for row in reversed(pack.records)])
    source = {"snapshot": make_snapshot(tmp_path, pack)} if scope == "complete" else {"pack": pack}
    assert membership_mask(query, artifact, artifacts=[result], **source) == bytes(int(identity in expected) for identity in artifact.ids)


def test_bulk_ids_are_explicit_and_keep_registered_array_order():
    pack = make_pack(5)
    artifact = target([]).model_copy(update={"data": {"bulk": {"count": 3}}})
    query = Query(snapshot_id="s1", filter={"field_id": "source.score", "op": "gt", "value": 2})
    assert membership_mask(query, artifact, ids=["row-000004", "row-000001", "row-000003"], pack=pack) == bytes([1, 0, 1])
    with pytest.raises(ValueError, match="explicit.*IDs"):
        membership_mask(query, artifact, pack=pack)
    with pytest.raises(ValueError, match="count"):
        membership_mask(query, artifact, ids=["row-000004"], pack=pack)


@pytest.mark.parametrize("changes, message", [
    ({"snapshot_ids": ["other"]}, "snapshot"),
    ({"snapshot_ids": ["s1", "other"]}, "snapshot"),
    ({"unit": "asset"}, "unit"),
    ({"ids": ["row-000001", "row-000001"]}, "unique"),
])
def test_artifact_identity_is_bound_to_query(changes, message):
    with pytest.raises(ValueError, match=message):
        membership_mask(Query(snapshot_id="s1"), target(["row-000001"]).model_copy(update=changes), pack=make_pack())


def test_source_and_explicit_result_bindings_are_validated(tmp_path):
    pack = make_pack(scope="complete")
    snapshot = make_snapshot(tmp_path, pack)
    query = Query(snapshot_id="s1", population_scope="complete")
    artifact = target([pack.records[0].id])
    with pytest.raises(ValueError, match="exactly one"):
        membership_mask(query, artifact)
    with pytest.raises(ValueError, match="exactly one"):
        membership_mask(query, artifact, pack=pack, snapshot=snapshot)
    with pytest.raises(ValueError, match="scope"):
        membership_mask(query.model_copy(update={"population_scope": "preview"}), artifact, snapshot=snapshot)
    with pytest.raises(ValueError, match="Explicit result"):
        membership_mask(query.model_copy(update={"result_snapshot_ids": ["absent"]}), artifact, snapshot=snapshot)
    with pytest.raises(ValueError, match="registered artifact"):
        membership_mask(query, artifact, ids=["other"], snapshot=snapshot)


def test_membership_limits_fail_without_silent_partial_mask(monkeypatch):
    import dataset_atlas.queries.membership as module
    pack = make_pack(3)
    artifact = target([row.id for row in pack.records])
    monkeypatch.setattr(module, "MAX_MEMBERSHIP_ROWS", 2)
    with pytest.raises(ValueError, match="row budget"):
        membership_mask(Query(snapshot_id="s1"), artifact, pack=pack)
    monkeypatch.setattr(module, "MAX_MEMBERSHIP_ROWS", 10)
    monkeypatch.setattr(module, "MAX_MEMBERSHIP_ID_BYTES", 4)
    with pytest.raises(ValueError, match="ID byte budget"):
        membership_mask(Query(snapshot_id="s1"), artifact, pack=pack)


def test_snapshot_membership_uses_no_record_payload_fetch(tmp_path, monkeypatch):
    pack = make_pack(scope="complete")
    snapshot = make_snapshot(tmp_path, pack)
    def fail(*args, **kwargs):
        pytest.fail("Membership must not materialize record payloads")
    monkeypatch.setattr(snapshot, "records", fail)
    monkeypatch.setattr(snapshot, "query", fail)
    query = Query(snapshot_id="s1", population_scope="complete", sample={"method": "random", "size": 4, "seed": 5})
    expected = {row.id for row in query_pack(pack, query).records}
    artifact = target([row.id for row in pack.records])
    assert membership_mask(query, artifact, snapshot=snapshot) == bytes(int(identity in expected) for identity in artifact.ids)


def test_snapshot_membership_timeout_and_cleanup(tmp_path):
    pack = make_pack(10_021, scope="complete")
    snapshot = make_snapshot(tmp_path, pack)
    snapshot.timeout_seconds = 0.000001
    with pytest.raises(ValueError, match="time budget"):
        membership_mask(Query(snapshot_id="s1", population_scope="complete"), target([pack.records[-1].id]), snapshot=snapshot)
    assert not snapshot._active


def test_preview_asset_population_is_not_capped_by_example_count():
    pack = make_pack(1)
    pack.records[0].assets = [Asset(id=f"asset-{index}", dataset_id="toy", release_id="r1", modality="image") for index in range(4)]
    artifact = target(["asset-3", "asset-0"]).model_copy(update={"unit": "asset"})
    assert membership_mask(Query(snapshot_id="s1", unit="asset", limit=1), artifact, pack=pack) == bytes([1, 1])


@pytest.mark.parametrize("values,dtype", [
    ([1, 1.0, "1", True, None, 2, "2", False] * 3, "category"),
    ([{"z": 1, "a": [2]}, {"a": [2], "z": 1}, None, {"a": [1]}] * 6, "object"),
    ([1, 1.0, 2, 2.0, None, 4.5] * 4, "number"),
])
def test_strata_preserve_original_json_types_and_canonical_structure(tmp_path, values, dtype):
    pack = make_pack(len(values), scope="complete")
    pack.fields = [FieldDescriptor(id="source.stratum", name="Stratum", dtype=dtype)]
    for row, value in zip(pack.records, values, strict=True):
        row.source = {"stratum": value}
    snapshot = make_snapshot(tmp_path, pack)
    query = Query(snapshot_id="s1", population_scope="complete", sample={"method": "stratified", "size": 13, "seed": 8, "field_id": "source.stratum"})
    expected = {row.id for row in snapshot.query(query).records}
    artifact = target([row.id for row in reversed(pack.records)])
    assert membership_mask(query, artifact, snapshot=snapshot) == bytes(int(identity in expected) for identity in artifact.ids)


def test_selected_bulk_scalar_results_are_available_to_membership(tmp_path):
    import numpy as np
    from dataset_atlas.storage.arrays import write_bundle
    pack = make_pack(scope="complete")
    snapshot = make_snapshot(tmp_path, pack)
    ordered = [row.id for row in reversed(pack.records)]
    root = tmp_path / "results"
    bulk = write_bundle(root / "arrays" / "labels", ordered, {"score": np.arange(len(ordered), dtype="float32")})
    bulk["dir"] = "arrays/labels"
    result = Artifact(id="labels", kind="analysis.outlier", snapshot_ids=["s1"], unit="example", ids=[], data={"bulk": bulk})
    result._store_root = root
    # Result registrations normally hydrate their row identities on load.
    result.ids = ordered
    query = Query(snapshot_id="s1", population_scope="complete", result_snapshot_ids=["labels"],
                  filter={"field_id": "prediction.labels.score", "op": "gt", "value": 27},
                  sample={"method": "source", "size": 2})
    expected = {row.id for row in snapshot.query(query, [result]).records}
    assert membership_mask(query, target(ordered), artifacts=[result], snapshot=snapshot) == bytes(int(identity in expected) for identity in ordered)


@pytest.mark.parametrize("scope", ["preview", "complete"])
@pytest.mark.parametrize("sample", [
    {"method": []}, {"method": "stratified", "field_id": []},
    {"method": "random", "seed": True}, {"size": True},
])
def test_malformed_sample_options_fail_explicitly(tmp_path, sample, scope):
    pack = make_pack(scope=scope)
    source = {"snapshot": make_snapshot(tmp_path, pack)} if scope == "complete" else {"pack": pack}
    with pytest.raises(ValueError, match="sampl|seed|field"):
        membership_mask(Query(snapshot_id="s1", population_scope=scope, sample=sample), target([pack.records[0].id]), **source)
