"""Content-derived identity for future remote sampled previews; synthetic only."""
import copy
import io
import json

import pyarrow as pa
import pyarrow.parquet as pq

from dataset_atlas.models import Asset, Dataset, FieldDescriptor, Pack, Record
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.registry import Registry
from test_remote_sample import configure


def prepare_pair(tmp_path, monkeypatch):
    payloads = {}
    for shard in range(2):
        target = io.BytesIO()
        pq.write_table(pa.Table.from_pylist([{'text': f'shard {shard} row {row}', 'value': row}
                                            for row in range(120)]), target, row_group_size=10)
        payloads[f'train-{shard}.parquet'] = target.getvalue()
    configure(tmp_path, monkeypatch, payloads)
    footers = sum(len(data) for data in payloads.values())
    sizes = []
    for data in payloads.values():
        metadata = pq.ParquetFile(io.BytesIO(data)).metadata
        for i in range(metadata.num_row_groups - 1):
            group = metadata.row_group(i)
            sizes.append(sum(group.column(c).total_compressed_size for c in range(group.num_columns)))
    manager = PreparationManager(tmp_path)
    full = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample')
    partial = manager.plan('huge', footers + max(sizes) * 3 + max(sizes) // 2, 5_000_000, source_mode='sample')
    return manager, full, partial, payloads


def test_budget_conditioned_membership_has_a_distinct_frozen_snapshot(tmp_path, monkeypatch):
    _, full, partial, _ = prepare_pair(tmp_path, monkeypatch)
    run(tmp_path, full['id'])
    registry = Registry(tmp_path)
    previous = registry.pack('huge')
    path = registry.active_directory('huge') / 'pack/pack.json'
    original = path.read_bytes()
    (path.parents[1].parent / 'active.json').unlink()
    run(tmp_path, partial['id'])
    current = Registry(tmp_path).pack('huge')
    assert len(previous.records) == 100 and len(current.records) == 30
    assert previous.dataset.snapshot_id != current.dataset.snapshot_id
    assert all(r.snapshot_id == current.dataset.snapshot_id for r in current.records)
    receipt = json.loads((Registry(tmp_path).active_directory('huge') / 'receipt.json').read_text())
    assert receipt['snapshot_id'] == current.dataset.snapshot_id
    assert receipt['snapshot_identity'] == current.sampling['snapshot_identity']
    assert all(item['snapshot_id'] == current.dataset.snapshot_id for item in current.dataset.evidence
               if item['kind'] in {'local_preparation', 'sampled_cohort_identity', 'computed_measurement'})
    assert path.read_bytes() == original
    frozen = Registry(tmp_path).versions('huge', snapshot_id=previous.dataset.snapshot_id)
    assert len(frozen) == 1
    assert [r.id for r in Pack.model_validate_json(frozen[0][1].read_text()).records] == [r.id for r in previous.records]


def test_cached_footers_cannot_rebind_the_same_plan_to_different_membership(tmp_path, monkeypatch):
    _, _, plan, _ = prepare_pair(tmp_path, monkeypatch)
    run(tmp_path, plan['id'])
    first = Registry(tmp_path).pack('huge')
    (Registry(tmp_path).active_directory('huge').parent / 'active.json').unlink()
    # A cache hit transfers no bytes, leaving more allowance for row-group draws.
    from dataset_atlas.adapters.remote_columnar import RemoteColumnarAdapter
    original = RemoteColumnarAdapter.warm_layouts
    def cached(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.bytes_fetched = 0
    monkeypatch.setattr(RemoteColumnarAdapter, 'warm_layouts', cached)
    # Execute the same plan parameters in a separate fresh preparation directory.
    plan2 = copy.deepcopy(plan)
    plan2['id'] = 'f' * 64
    directory = tmp_path / 'work/preparation' / plan2['id']
    directory.mkdir()
    (directory / 'plan.json').write_text(json.dumps(plan2))
    run(tmp_path, plan2['id'])
    second = Registry(tmp_path).pack('huge')
    assert len(first.records) == 30 and len(second.records) == 100
    assert first.dataset.snapshot_id != second.dataset.snapshot_id


def test_identical_native_content_is_stable_across_workspace_and_budget(tmp_path, monkeypatch):
    first_root, second_root = tmp_path / 'one', tmp_path / 'two'
    first_root.mkdir(); second_root.mkdir()
    first, _, _, payloads = prepare_pair(first_root, monkeypatch)
    plan = first.plan('huge', 5_000_000, 5_000_000, source_mode='sample')
    run(first_root, plan['id'])
    previous = Registry(first_root).pack('huge')
    configure(second_root, monkeypatch, payloads)
    second = PreparationManager(second_root)
    plan = second.plan('huge', 9_000_000, 8_000_000, source_mode='sample')
    run(second_root, plan['id'])
    current = Registry(second_root).pack('huge')
    assert [r.id for r in previous.records] == [r.id for r in current.records]
    assert previous.dataset.snapshot_id == current.dataset.snapshot_id
    assert all(r.snapshot_id == current.dataset.snapshot_id for r in current.records)


def test_cohort_identity_tracks_native_content_order_and_checked_media_without_runtime_paths():
    from dataset_atlas.preparation.remote_sample import sampled_snapshot_identity
    dataset = Dataset(id='fixture', name='Synthetic', release='a' * 40)
    records = [Record(id='fixture:example:1', dataset_id='fixture', release_id=dataset.release, snapshot_id='provisional',
        source={'snapshot_id': 'native-value', 'label': 'synthetic'}, assets=[Asset(id='a', dataset_id='fixture',
        release_id=dataset.release, modality='image', uri='remote/0/1/images/0.png', sha256='1' * 64,
        metadata={'availability': 'original checked'})]),
        Record(id='fixture:example:2', dataset_id='fixture', release_id=dataset.release, snapshot_id='provisional', source={'native': 2})]
    files = [{'source_name': 'native/train.parquet', 'sha256': '2' * 64, 'bytes': 1234, 'etag': '"pinned"'}]
    def identity(rows):
        return sampled_snapshot_identity(dataset, rows, files, 200)[0]
    original = identity(records)
    cached = copy.deepcopy(records)
    cached[0].snapshot_id = 'another-provisional'
    cached[0].assets[0].metadata.update(source_ref=cached[0].assets[0].uri, _compact_snapshot_id='temporary')
    cached[0].assets[0].uri = '/different/workspace/cache/image.png'
    assert identity(cached) == original
    for mutate in (
        lambda rows: rows.reverse(),
        lambda rows: rows[0].source.update(snapshot_id='different-native-value'),
        lambda rows: setattr(rows[0].assets[0], 'sha256', '3' * 64),
        lambda rows: rows[0].assets[0].metadata.update(availability='absent_from_release'),
    ):
        changed = copy.deepcopy(records); mutate(changed)
        assert identity(changed) != original
    declared = [FieldDescriptor(id='source.label', name='label', dtype='string')]
    changed_schema = [FieldDescriptor(id='source.label', name='label', dtype='object')]
    assert sampled_snapshot_identity(dataset, records, files, 200, declared)[0] != sampled_snapshot_identity(
        dataset, records, files, 200, changed_schema)[0]
