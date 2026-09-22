import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dataset_atlas.models import Artifact, Dataset, FieldDescriptor, Pack, Query, Record
from dataset_atlas.queries import query_pack
from dataset_atlas.queries.parquet import ParquetSnapshot, build_parquet_snapshot
from dataset_atlas.queries.results import attach_results


FIELDS = [
    FieldDescriptor(id="source.group", name="Group", dtype="category", query_ops=["eq", "ne", "in", "contains", "is_null"]),
    FieldDescriptor(id="source.score", name="Score", dtype="number", query_ops=["eq", "ne", "in", "gt", "gte", "lt", "lte", "is_null"]),
]


def rows(count):
    for index in range(count):
        yield Record(
            id=f"toy:example:{index:06d}", dataset_id="toy", release_id="r1", snapshot_id="s1",
            text=f"record {index}", source={"group": str(index % 10), "score": index},
        )


def make_snapshot(tmp_path: Path, count=100, *, scope="complete"):
    path = tmp_path / "snapshot"
    build_parquet_snapshot(rows(count), FIELDS, path, root=tmp_path, dataset_id="toy", release_id="r1", snapshot_id="s1", expected_count=count, population_scope=scope)
    return ParquetSnapshot(tmp_path, path)


def test_large_snapshot_filter_sort_pagination_and_timing(tmp_path, capsys):
    started = time.perf_counter()
    snapshot = make_snapshot(tmp_path, count=10_050)
    build_seconds = time.perf_counter() - started
    query = Query(
        snapshot_id="s1", population_scope="complete", unit="example", filter={"field_id": "source.group", "op": "eq", "value": "3"},
        sort=[{"field_id": "source.score", "direction": "desc"}], limit=500,
    )
    started = time.perf_counter()
    pages = []
    while True:
        result = snapshot.query(query)
        pages.extend(record.id for record in result.records)
        assert result.matched_count == 1005
        assert result.coverage["available_count"] == 10_050
        assert result.population_scope == "complete"
        if not result.cursor:
            break
        query = query.model_copy(update={"cursor": result.cursor})
    query_seconds = time.perf_counter() - started
    print(f"Parquet fixture=10050 build_s={build_seconds:.3f} three_pages_s={query_seconds:.3f}")
    assert len(pages) == len(set(pages)) == 1005
    assert pages[0] == "toy:example:010043"
    assert pages[-1] == "toy:example:000003"
    assert query_seconds < 30


def test_typed_boolean_filter_and_static_parity(tmp_path):
    records = list(rows(100))
    snapshot = make_snapshot(tmp_path)
    query = Query(
        snapshot_id="s1", population_scope="complete", filter={"and": [
            {"field_id": "source.group", "op": "in", "value": ["3", "7"]},
            {"not": {"field_id": "source.score", "op": "lt", "value": 40}},
        ]}, sort=[{"field_id": "source.score", "direction": "desc"}], limit=100,
    )
    parquet_result = snapshot.query(query)
    pack = Pack(dataset=Dataset(id="toy", name="Toy", release="r1", snapshot_id="s1"), fields=FIELDS, records=records, population_scope="complete")
    static_result = query_pack(pack, query)
    assert [row.id for row in parquet_result.records] == [row.id for row in static_result.records]
    assert parquet_result.matched_count == static_result.matched_count
    sampled = snapshot.query(query.model_copy(update={"sample": {"method": "source", "size": 5}, "cursor": None}))
    assert sampled.matched_count == static_result.matched_count
    assert sampled.coverage["sampled_count"] == 5
    assert len(sampled.records) == 5


def test_sql_injection_and_unknown_fields_rejected(tmp_path):
    snapshot = make_snapshot(tmp_path)
    literal = "' OR 1=1 --"
    assert snapshot.query(Query(snapshot_id="s1", population_scope="complete", filter={"field_id": "source.group", "op": "eq", "value": literal})).matched_count == 0
    assert snapshot.query(Query(snapshot_id="s1", population_scope="complete", search=literal)).matched_count == 0
    with pytest.raises(ValueError, match="Unknown field"):
        snapshot.query(Query(snapshot_id="s1", population_scope="complete", filter={"field_id": "source.group); DROP TABLE x;--", "op": "eq", "value": "3"}))
    with pytest.raises(ValueError, match="Invalid sort"):
        snapshot.query(Query(snapshot_id="s1", population_scope="complete", sort=[{"field_id": "source.score", "direction": "desc; DROP TABLE x"}]))
    with pytest.raises(ValueError, match="type"):
        snapshot.query(Query(snapshot_id="s1", population_scope="complete", filter={"field_id": "source.score", "op": "gt", "value": "0 OR TRUE"}))
    with pytest.raises(ValueError, match="Invalid sampling"):
        snapshot.query(Query(snapshot_id="s1", population_scope="complete", sample={"method": "unsupported", "size": 5}))


def test_snapshot_identity_checksum_root_and_count_enforced(tmp_path):
    with pytest.raises(ValueError, match="expected"):
        build_parquet_snapshot(rows(3), FIELDS, tmp_path / "short", root=tmp_path, dataset_id="toy", release_id="r1", snapshot_id="s1", expected_count=4, population_scope="complete")
    assert not (tmp_path / "short").exists()
    with pytest.raises(ValueError, match="outside"):
        build_parquet_snapshot(rows(1), FIELDS, tmp_path.parent / "escape", root=tmp_path, dataset_id="toy", release_id="r1", snapshot_id="s1", expected_count=1)
    snapshot = make_snapshot(tmp_path, count=3, scope="preview")
    assert snapshot.dataset_id == "toy" and snapshot.snapshot_id == "s1"
    assert snapshot.fields[0].id == "source.group"
    assert snapshot.query(Query(snapshot_id="s1")).warnings
    with pytest.raises(ValueError, match="Snapshot mismatch"):
        snapshot.query(Query(snapshot_id="other"))
    manifest_path = tmp_path / "snapshot" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dataset_id"] = "forged"
    manifest_path.chmod(0o644)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="identity"):
        ParquetSnapshot(tmp_path, tmp_path / "snapshot")


def test_interrupt_hook_reaches_active_connection(tmp_path):
    snapshot = make_snapshot(tmp_path, count=1)
    class Active:
        called = False
        def interrupt(self):
            self.called = True
    active = Active()
    snapshot._active.add(active)
    snapshot.interrupt()
    assert active.called

def test_query_time_budget_cancels_and_reader_remains_usable(tmp_path):
    snapshot=make_snapshot(tmp_path,count=10_050)
    snapshot.timeout_seconds=0.000001
    with pytest.raises(ValueError,match="time budget"):
        snapshot.query(Query(snapshot_id="s1",population_scope="complete",sample={"method":"stratified","field_id":"source.group","size":100}))
    assert not snapshot._active
    snapshot.timeout_seconds=30
    assert snapshot.query(Query(snapshot_id="s1",population_scope="complete",limit=1)).matched_count==10_050


def test_numeric_category_keeps_source_type_and_numeric_order(tmp_path):
    numeric = FieldDescriptor(id="source.label", name="Label", dtype="category", query_ops=["eq", "in", "gt", "contains", "is_null"])
    records = (
        Record(id=f"id-{index}", dataset_id="toy", release_id="r1", snapshot_id="s1", source={"label": index})
        for index in (2, 10, 1)
    )
    target = tmp_path / "category"
    build_parquet_snapshot(records, [numeric], target, root=tmp_path, dataset_id="toy", release_id="r1", snapshot_id="s1", expected_count=3, population_scope="complete")
    snapshot = ParquetSnapshot(tmp_path, target)
    result = snapshot.query(Query(snapshot_id="s1", population_scope="complete", sort=[{"field_id": "source.label", "direction": "asc"}]))
    assert [record.source["label"] for record in result.records] == [1, 2, 10]
    assert snapshot.query(Query(snapshot_id="s1", population_scope="complete", filter={"field_id": "source.label", "op": "eq", "value": 2})).matched_count == 1
    assert snapshot.query(Query(snapshot_id="s1", population_scope="complete", filter={"field_id": "source.label", "op": "eq", "value": "2"})).matched_count == 0
    assert snapshot.query(Query(snapshot_id="s1", population_scope="complete", filter={"field_id": "source.label", "op": "contains", "value": "2"})).matched_count == 0


def test_complete_result_join_filters_before_count_and_pagination(tmp_path):
    snapshot = make_snapshot(tmp_path, count=10_050)
    result_ids = [f"toy:example:{index:06d}" for index in range(10)]
    items = [
        {"id": result_ids[0], "status": "completed", "output": {"detections": []}},
        {"id": result_ids[1], "status": "failed", "error": "offline fixture"},
        *[{"id": result_ids[index], "status": "completed", "output": {"detections": [{"class": "person"}] * index}}
          for index in range(2, 10)],
    ]
    artifact = Artifact(id="detect-run", kind="detect.coco_v1", snapshot_ids=["s1"], unit="example", ids=result_ids, data={"items": items})
    available = {field.id for field in snapshot.query_fields([artifact])}
    assert {"prediction.detect-run.status", "prediction.detect-run.detection_count"} <= available
    assert "prediction.detect-run.status" not in {field.id for field in snapshot.fields}

    def run(field_id, op, value, limit=100):
        return snapshot.query(Query(snapshot_id="s1", population_scope="complete", result_snapshot_ids=[artifact.id],
                                    filter={"field_id": field_id, "op": op, "value": value}, limit=limit), [artifact])

    zero = run("prediction.detect-run.detection_count", "eq", 0, limit=1)
    assert zero.matched_count == zero.returned_count == 1
    assert [record.id for record in zero.records] == result_ids[:1]
    assert zero.records[0].prediction["detect-run.detection_count"] == 0
    failed = run("prediction.detect-run.status", "eq", "failed")
    assert failed.matched_count == 1
    assert [record.id for record in failed.records] == result_ids[1:2]
    assert "detect-run.detection_count" not in failed.records[0].prediction
    missing_count = run("prediction.detect-run.detection_count", "is_null", True, limit=1)
    assert missing_count.matched_count == 10_041  # one failure and 10,040 uncomputed rows
    assert missing_count.returned_count == 1 and missing_count.cursor
    assert missing_count.records[0].id == result_ids[1]
    assert run("prediction.detect-run.status", "is_null", True).matched_count == 10_040
    assert run("prediction.detect-run.detection_count", "gt", 5).matched_count == 4

    # The same scalar aggregation is attached by the preview path.
    pack = Pack(dataset=Dataset(id="toy", name="Toy", release="r1", snapshot_id="s1"),
                fields=FIELDS, records=list(rows(10)), population_scope="complete")
    preview = attach_results(pack, [artifact])
    assert zero.records[0].prediction == preview.records[0].prediction
    assert failed.records[0].prediction == preview.records[1].prediction


def test_result_join_requires_explicit_matching_snapshot_and_unit(tmp_path):
    snapshot = make_snapshot(tmp_path, count=2)
    artifact = Artifact(id="a", kind="test", snapshot_ids=["s1"], unit="example", ids=["toy:example:000000"],
                        data={"items": [{"id": "toy:example:000000", "status": "completed", "output": {"score": 1}}]})
    query = Query(snapshot_id="s1", population_scope="complete", result_snapshot_ids=["a"],
                  filter={"field_id": "prediction.a.score", "op": "eq", "value": 1})
    assert snapshot.query(query, [artifact]).matched_count == 1
    with pytest.raises(ValueError, match="Explicit"):
        snapshot.query(query)
    with pytest.raises(ValueError, match="Explicit"):
        snapshot.query(query.model_copy(update={"result_snapshot_ids": []}), [artifact])
    with pytest.raises(ValueError, match="incompatible"):
        snapshot.query(query, [artifact.model_copy(update={"snapshot_ids": ["foreign"]})])
    with pytest.raises(ValueError, match="incompatible"):
        snapshot.query(query, [artifact.model_copy(update={"unit": "asset"})])
    with pytest.raises(ValueError, match="Unknown field"):
        snapshot.query(query.model_copy(update={"result_snapshot_ids": [], "filter": query.filter}))
    assert "prediction.a.score" not in snapshot.registry


def test_result_join_is_query_local_under_concurrent_filters(tmp_path):
    snapshot = make_snapshot(tmp_path, count=100)
    first = Artifact(id="first", kind="score", snapshot_ids=["s1"], unit="example", ids=["toy:example:000000", "toy:example:000001"],
                     data={"items": [
                         {"id": "toy:example:000000", "status": "completed", "output": {"score": None}},
                         {"id": "toy:example:000001", "status": "completed", "output": {"score": 3}},
                     ]})
    second = Artifact(id="second", kind="score", snapshot_ids=["s1"], unit="example", ids=["toy:example:000002"],
                      data={"items": [{"id": "toy:example:000002", "status": "completed", "output": {"score": 7}}]})
    assert next(field for field in snapshot.result_fields([first]) if field.id == "prediction.first.score").dtype == "number"

    def run(artifact, value):
        query = Query(snapshot_id="s1", population_scope="complete", result_snapshot_ids=[artifact.id],
                      filter={"field_id": f"prediction.{artifact.id}.score", "op": "gte", "value": value})
        return snapshot.query(query, [artifact])

    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(run, first, 3)
        right = pool.submit(run, second, 7)
        assert [record.id for record in left.result().records] == ["toy:example:000001"]
        assert [record.id for record in right.result().records] == ["toy:example:000002"]
    assert len(snapshot.registry) == len(FIELDS) + 7


@pytest.mark.parametrize("method",["random","stratified"])
def test_seeded_sampling_matches_pack_and_pages(tmp_path,method):
    snapshot=make_snapshot(tmp_path,count=1050)
    pack=Pack(dataset=Dataset(id="toy",name="Toy",release="r1",snapshot_id="s1"),fields=FIELDS,records=list(rows(1050)),population_scope="complete")
    query=Query(snapshot_id="s1",population_scope="complete",sample={"method":method,"seed":-17,"size":37,"field_id":"source.group"},limit=19)
    first=snapshot.query(query);expected=query_pack(pack,query)
    assert [r.id for r in first.records]==[r.id for r in expected.records]
    assert first.matched_count==1050 and first.coverage["sampled_count"]==37
    assert first.cursor
    second=snapshot.query(query.model_copy(update={"cursor":first.cursor}))
    expected_second=query_pack(pack,query.model_copy(update={"cursor":expected.cursor}))
    assert [r.id for r in second.records]==[r.id for r in expected_second.records]
    assert second.cursor is None and len(second.records)==18
