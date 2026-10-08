"""Sampled previews of remote Parquet releases (synthetic shards; tests only)."""
import hashlib
import io
import json
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from PIL import Image
from dataset_atlas.models import Dataset
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.remote_sample import TwoStageSampler
from dataset_atlas.preparation.worker import run
from dataset_atlas.registry import Registry


def drain(sampler, limit=10_000):
    rows = []
    while len(rows) < limit and (row := sampler.next()) is not None:
        rows.append(row)
    return rows


def test_unbounded_budget_is_a_reproducible_simple_random_sample():
    groups = [(g // 5, g % 5, 10, 100) for g in range(50)]
    first = drain(TwoStageSampler(groups, seed=3, byte_budget=10**9), 100)
    again = drain(TwoStageSampler(groups, seed=3, byte_budget=10**9), 100)
    other = drain(TwoStageSampler(groups, seed=4, byte_budget=10**9), 100)
    assert first == again and first != other
    assert len(set(first)) == 100 and all(0 <= row < 10 for _, _, row in first)
    sampler = TwoStageSampler(groups, seed=3, byte_budget=10**9)
    drain(sampler, 100)
    assert sampler.description(100)['design'] == 'simple random sample of rows without replacement'


def test_budget_limits_selected_row_groups_and_then_exhausts_them():
    groups = [(0, g, 10, 100) for g in range(50)]
    sampler = TwoStageSampler(groups, seed=0, byte_budget=350)
    rows = drain(sampler)
    assert len({(f, g) for f, g, _ in rows}) == 3 and len(rows) == 30
    assert sampler.selected_bytes <= 350 and sampler.next() is None
    assert sampler.description(len(rows))['design'].startswith('Budget-conditioned')


def test_row_group_larger_than_budget_selects_nothing():
    assert TwoStageSampler([(0, 0, 10, 1000)], byte_budget=10).next() is None
    with pytest.raises(ValueError, match='no rows'):
        TwoStageSampler([(0, 0, 0, 1)])


def test_budgeted_full_index_preview_preserves_native_subset_and_group_provenance():
    from dataset_atlas.models import Record
    from dataset_atlas.preparation.remote_sample import draw_native_subset
    class Adapter:
        def records_at(self, source, targets):
            return [Record(id=str(row), dataset_id='fixture', release_id='native', snapshot_id='pinned',
                source={'label': row}) for _, _, row in targets]
    spec = {'native_class_groups': {'field': 'label', 'groups': [{'name': 'kept', 'start': 10, 'end': 19}],
                                  'provenance': {'revision': 'fixture-author'}}}
    sampler = TwoStageSampler([(0, 0, 100, 1)], byte_budget=10)
    records, description = draw_native_subset(Adapter(), None, sampler, 10, spec)
    assert {record.source['label'] for record in records} == set(range(10, 20))
    assert all(record.source['_atlas_native_class_group']['native_label'] == record.source['label'] for record in records)
    assert description['native_source_population_count'] == 100
    assert description['excluded_by_native_filter'] > 0
    assert description['rows_drawn'] > 10
    with pytest.raises(ValueError, match='candidate and transfer bounds'):
        draw_native_subset(Adapter(), None, TwoStageSampler([(0, 0, 100, 1)], byte_budget=10), 10, spec, max_candidates=1)


def shards(tmp_path, images=False, nullable=True):
    payloads = {}
    for shard in range(2):
        rows = []
        for i in range(117):
            row = {'text': f'shard {shard} row {i}', 'value': i}
            if images:
                picture = io.BytesIO(); Image.new('RGB', (4 + i % 3, 5), (i, shard, 7)).save(picture, 'PNG')
                row['images'] = [{'bytes': None if nullable and i % 4 == 0 else picture.getvalue(), 'path': f'{shard}-{i}.png'}]
            rows.append(row)
        path = tmp_path / f'train-{shard}.parquet'
        pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=10)
        payloads[f'train-{shard}.parquet'] = path.read_bytes()
    return payloads


def configure(tmp_path, monkeypatch, payloads, recipe=None):
    dataset = Dataset(id='huge', name='Synthetic huge release', release='unresolved', source_url='https://huggingface.co/datasets/owner/huge',
                      adapter='remote_columnar', adapter_config={'mapping': {'text': 'text'}})
    (tmp_path / 'registry/datasets').mkdir(parents=True)
    (tmp_path / 'registry/datasets/huge.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    (tmp_path / 'registry/recipes').mkdir()
    (tmp_path / 'registry/recipes/huge.yaml').write_text(yaml.safe_dump({'scope': 'Every row of both synthetic shards', **(recipe or {})}))
    monkeypatch.setattr('dataset_atlas.preparation.read_metadata', lambda url: {'sha': 'a' * 40, 'siblings': [
        {'rfilename': name, 'size': len(data), 'lfs': {'sha256': hashlib.sha256(data).hexdigest()}} for name, data in payloads.items()]})
    monkeypatch.setattr('dataset_atlas.preparation.remote.range_fingerprint', lambda *args, **kwargs: '"fixture"')
    def fetch(self, start, end):
        return payloads[self.url.rsplit('/', 1)[1]][start:end + 1]
    monkeypatch.setattr('dataset_atlas.storage.ranges.HttpsRangeReader._fetch', fetch)


def test_sampled_preview_covers_all_shards_without_a_complete_index(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, shards(tmp_path))
    manager = PreparationManager(tmp_path)
    plan = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample')
    assert plan['ready'] and plan['kind'] == 'huggingface_remote_sample' and plan['download_is_upper_bound']
    run(tmp_path, plan['id'])
    assert manager.status(plan['id'])['status'] == 'completed'
    registry = Registry(tmp_path)
    dataset = registry.dataset('huge')
    assert dataset.coverage.preview_count == 100 and dataset.coverage.total_count == 234
    assert dataset.coverage.complete_data == 'exceeds_storage_budget' and dataset.coverage.preview == 'complete_target'
    pack = registry.pack('huge')
    assert pack.sampling['method'] == 'sha256_counter_two_stage_row_groups' and pack.sampling['population_count'] == 234
    assert pack.sampling['design'] == 'simple random sample of rows without replacement'
    assert {r.source['_atlas_origin']['file'] for r in pack.records} == {'train-0.parquet', 'train-1.parquet'}
    assert len({r.id for r in pack.records}) == 100
    assert not (registry.active_directory('huge') / 'snapshot').exists()
    first = [r.id for r in pack.records]
    # A new plan over the same pinned shards draws the identical sample.
    (tmp_path / 'registry/recipes/huge.yaml').write_text(yaml.safe_dump({'scope': 'Every row of both synthetic shards', 'description': 'again'}))
    again = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample')
    run(tmp_path, again['id'])
    assert [r.id for r in Registry(tmp_path).pack('huge').records] == first
    record = pack.records[0]
    origin = record.source['_atlas_origin']
    assert record.text == f"shard {origin['file'][6]} row {origin['row']}"


def test_complete_filtered_index_and_budgeted_media_preview_have_identical_membership(tmp_path, monkeypatch):
    payloads = shards(tmp_path, images=True, nullable=False)
    spec = {'native_class_groups': {'field': 'value', 'groups': [{'name': 'native subset', 'start': 0, 'end': 69}],
                                  'provenance': {'revision': 'synthetic author mapping'}}}
    configure(tmp_path, monkeypatch, payloads, {'expected_count': 140, 'adapter_config': {
        'expected_source_count': 234, 'record_filter': spec}})
    manager = PreparationManager(tmp_path)
    plan = manager.plan('huge', 5_000_000, 5_000_000, source_mode='selective')
    assert plan['ready']
    run(tmp_path, plan['id'])
    assert manager.status(plan['id'])['status'] == 'completed'
    registry = Registry(tmp_path)
    pack = registry.pack('huge')
    originals = {json.loads(value)['id']: json.loads(value)['source'] for value in
        pq.read_table(registry.snapshot_path('huge') / 'records.parquet', columns=['record_json']).column(0).to_pylist()}
    assert len(originals) == 140 and len(pack.records) == 100
    for record in pack.records:
        assert 0 <= record.source['value'] <= 69
        assert record.source == originals[record.id]
        assert record.source['_atlas_native_class_group']['native_label'] == record.source['value']
    assert pack.sampling['population_count'] == 140
    assert pack.sampling['native_source_population_count'] == 234


def test_transfer_budget_switches_to_documented_two_stage_design(tmp_path, monkeypatch):
    payloads = shards(tmp_path)
    configure(tmp_path, monkeypatch, payloads)
    # These small shards fit in one 64 KB footer block, so the footer pass transfers each whole file.
    footer = sum(len(data) for data in payloads.values())
    first = pq.ParquetFile(io.BytesIO(payloads['train-0.parquet'])).metadata.row_group(0)
    group = sum(first.column(i).total_compressed_size for i in range(first.num_columns))
    plan = PreparationManager(tmp_path).plan('huge', footer + group * 3 + group // 2, 5_000_000, source_mode='sample')
    run(tmp_path, plan['id'])
    pack = Registry(tmp_path).pack('huge')
    assert pack.sampling['design'].startswith('Budget-conditioned')
    assert pack.sampling['selected_row_group_transfer_bytes'] <= pack.sampling['transfer_budget_bytes']
    assert len(pack.records) == 10 * pack.sampling['row_groups_selected'] < 100
    assert Registry(tmp_path).dataset('huge').coverage.preview == 'partial'


def test_embedded_images_are_opened_and_absent_slots_excluded(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, shards(tmp_path, images=True))
    plan = PreparationManager(tmp_path).plan('huge', 20_000_000, 5_000_000, source_mode='sample')
    run(tmp_path, plan['id'])
    registry = Registry(tmp_path)
    pack = registry.pack('huge')
    receipt = json.loads((registry.active_directory('huge') / 'receipt.json').read_text())
    assert len(pack.records) == 100 and all(r.source['value'] % 4 for r in pack.records)
    assert receipt['preview_media_validation']['unavailable_candidate_records'] > 0
    assert pack.sampling['valid_for_population_prevalence'] is False
    assert pack.sampling['media_availability_exclusions'] == receipt['preview_media_validation']['unavailable_candidate_records']
    assert receipt['sampling']['valid_for_population_prevalence'] is False
    assert all(a.sha256 for r in pack.records for a in r.assets)
    assert receipt['remote_media_bytes']>0
    assert receipt['retained_preview_original_bytes']>0
    assert pack.checksums
    for record in pack.records:
        for asset in record.assets:
            path=registry.active_directory('huge')/'pack'/asset.uri
            assert hashlib.sha256(path.read_bytes()).hexdigest()==asset.sha256
            assert asset.metadata['source_ref'].startswith('remote/')


def test_shard_rank_reads_only_selected_footers_and_leaves_total_unknown(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, shards(tmp_path), {'sample_footers': 'shard_rank', 'sample_shards': 1})
    plan = PreparationManager(tmp_path).plan('huge', 5_000_000, 5_000_000, source_mode='sample')
    run(tmp_path, plan['id'])
    registry = Registry(tmp_path)
    pack = registry.pack('huge')
    assert pack.sampling['shards_in_population'] == 1 and pack.sampling['shards_in_release'] == 2
    assert len({r.source['_atlas_origin']['file'] for r in pack.records}) == 1
    assert registry.dataset('huge').coverage.total_count is None


def test_cost_conditioning_is_disclosed_even_before_first_rejected_draw():
    sampler = TwoStageSampler([(0,0,100,1),(0,1,900,1000)],byte_budget=1)
    receipt = sampler.description(0)
    assert receipt['row_groups_exceeding_initial_budget'] == 1
    assert receipt['rows_in_groups_exceeding_initial_budget'] == 900
    assert receipt['rejected_draws_for_transfer_budget'] == 0
    assert receipt['valid_for_population_prevalence'] is False
    assert 'zero inclusion' in receipt['design']
