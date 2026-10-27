"""Request-scoped remote resampling over synthetic pinned native shards."""
import hashlib
import io
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from dataset_atlas.models import Dataset
from dataset_atlas.preparation import PreparationManager, snapshot_for
from dataset_atlas.preparation.worker import run
from dataset_atlas.registry import Registry


ROOT = Path(__file__).resolve().parents[2]


def configure(tmp_path, monkeypatch, *, recipe=None, dataset_id='huge', large=False):
    payloads = {}
    for configuration in ('llava_instruct_150k', 'other_native_configuration'):
        table = pa.Table.from_pylist([{
            'texts': [{'user': f'Synthetic question {i}', 'assistant': f'Synthetic answer {i}'}],
            'native_annotation': {'position': i, 'labels': ['synthetic', configuration]},
        } for i in range(250)])
        data = io.BytesIO()
        pq.write_table(table, data, row_group_size=10)
        payloads[f'{configuration}/train-00000.parquet'] = data.getvalue()
    dataset = Dataset(id=dataset_id, name='Synthetic native mixture', adapter='structured',
                      source_url='https://huggingface.co/datasets/owner/huge')
    directory = tmp_path / 'registry/datasets'
    directory.mkdir(parents=True)
    (directory / f'{dataset_id}.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipes = tmp_path / 'registry/recipes'
    recipes.mkdir()
    (recipes / f'{dataset_id}.yaml').write_text(yaml.safe_dump({
        'scope': 'Every row of both synthetic native configurations',
        'sample_seed': 7,
        'adapter_config': {'mapping': {'conversation_pairs': 'texts', 'configuration_from_path': True}},
        **(recipe or {}),
    }))
    monkeypatch.setattr('dataset_atlas.preparation.read_metadata', lambda url: {
        'sha': 'a' * 40, 'siblings': [{'rfilename': name, 'size': 300_000_000 if large else len(data),
                                     'lfs': {'sha256': hashlib.sha256(data).hexdigest()}}
                                    for name, data in payloads.items()]})
    monkeypatch.setattr('dataset_atlas.preparation.remote.range_fingerprint', lambda *args, **kwargs: '"synthetic"')
    monkeypatch.setattr('dataset_atlas.storage.ranges.HttpsRangeReader._fetch',
                        lambda reader, start, end: next(data for name, data in payloads.items()
                                                       if reader.url.endswith(name))[start:end + 1])
    return PreparationManager(tmp_path)


def test_request_seed_changes_frozen_plan_and_snapshot_without_changing_recipe(tmp_path, monkeypatch):
    manager = configure(tmp_path, monkeypatch)
    default = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample')
    first = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample', sample_seed=13)
    again = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample', sample_seed=13)
    assert default['sample']['seed'] == 7
    assert first['sample']['seed'] == 13
    assert first['id'] == again['id'] != default['id']
    assert json.loads((manager._path(first['id']) / 'plan.json').read_text())['sample']['seed'] == 13
    assert snapshot_for('huge', first, first['id'], tmp_path) != snapshot_for('huge', default, default['id'], tmp_path)


@pytest.mark.parametrize('seed', [True, 1.5, '13', 2**53, -(2**53)])
def test_request_seed_rejects_values_that_cannot_roundtrip_through_browser_json(tmp_path, monkeypatch, seed):
    manager = configure(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='sample_seed'):
        manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample', sample_seed=seed)


def test_auto_remote_sampling_retains_explicit_request_seed(tmp_path, monkeypatch):
    manager = configure(tmp_path, monkeypatch, large=True)
    plan = manager.plan('huge', 5_000_000, 5_000_000, source_mode='auto', sample_seed=19)
    assert plan['ready'] and plan['kind'] == 'huggingface_remote_sample'
    assert plan['sample']['seed'] == 19


def test_another_seed_reaches_beyond_preview_and_preserves_immutable_first_sample(tmp_path, monkeypatch):
    manager = configure(tmp_path, monkeypatch)
    first = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample', sample_seed=13)
    run(tmp_path, first['id'])
    registry = Registry(tmp_path)
    original_directory = registry.active_directory('huge')
    original_bytes = (original_directory / 'pack/pack.json').read_bytes()
    original = registry.pack('huge')
    other = manager.plan('huge', 5_000_000, 5_000_000, source_mode='sample', sample_seed=14)
    run(tmp_path, other['id'])
    current = Registry(tmp_path).pack('huge')
    assert current.sampling['seed'] == 14 and original.sampling['seed'] == 13
    assert current.sampling['population_count'] == 500
    assert current.sampling['shards_in_population'] == 2
    assert len({record.id for record in current.records} - {record.id for record in original.records}) > 50
    assert (original_directory / 'pack/pack.json').read_bytes() == original_bytes
    for record in current.records:
        native = record.source['texts'][0]
        assert record.question == native['user']
        assert record.conversation == [{'role': 'user', 'content': native['user']},
                                       {'role': 'assistant', 'content': native['assistant']}]
        assert record.source['native_annotation']['labels'][0] == 'synthetic'
        assert record.source['_atlas_configuration'] == record.source['_atlas_origin']['file'].split('/')[0]
        assert record.unit == 'example'


def test_finevision_recipe_samples_the_whole_native_mixture_and_maps_native_pairs(tmp_path, monkeypatch):
    recipe = yaml.safe_load((ROOT / 'registry/recipes/finevision.yaml').read_text())
    manager = configure(tmp_path, monkeypatch, recipe=recipe, dataset_id='finevision')
    plan = manager.plan('finevision', 5_000_000, 5_000_000, source_mode='sample', sample_seed=21)
    assert plan['ready'] and plan['sample']['footers'] == 'all'
    assert len(plan['files']) == 2
    run(tmp_path, plan['id'])
    pack = Registry(tmp_path).pack('finevision')
    assert {record.source['_atlas_configuration'] for record in pack.records} == {
        'llava_instruct_150k', 'other_native_configuration'}
    assert all(record.conversation and record.unit == 'example' for record in pack.records)
