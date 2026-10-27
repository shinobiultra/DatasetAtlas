"""Synthetic embedded-Parquet flows; native acceptance is recorded separately."""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path

from PIL import Image
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from dataset_atlas.adapters import get_adapter
from dataset_atlas.models import Dataset, Pack
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.queries.parquet import ParquetSnapshot

ROOT = Path(__file__).resolve().parents[2]
NAMES = ['mathvision', 'sbbench-synthetic-age-crop-false',
         'sbbench-synthetic-gender-crop-false', 'sbbench-synthetic-gender-crop-true']


def fixture_file(tmp_path, column):
    rows = []
    for i, color in enumerate(['red', 'blue']):
        buffer = BytesIO()
        Image.new('RGB', (3, 2), color).save(buffer, format='PNG')
        rows.append({'id': f'synthetic-{i}', 'question': f'Synthetic question {i}',
                     'options': ['Synthetic A', 'Synthetic B'], 'label': i,
                     column: {'bytes': buffer.getvalue(), 'path': f'synthetic-{i}.png'}})
    path = tmp_path / 'synthetic-original.parquet'
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


@pytest.mark.parametrize('name', NAMES)
def test_direct_recipe_cold_plan_and_hardlinked_source_keep_original_embedded_bytes(tmp_path, monkeypatch, name):
    document = yaml.safe_load((ROOT / 'registry/recipes' / (name + '.yaml')).read_text())
    baseline = yaml.safe_load((ROOT / 'registry/datasets' / (name + '.yaml')).read_text())
    original = fixture_file(tmp_path, baseline['adapter_config']['media_columns'][0])
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    baseline.update(name='Synthetic direct-Parquet fixture', release='synthetic-release', snapshot_id='synthetic-snapshot')
    baseline['adapter_config'].update(path='work/not-installed.parquet', sha256=digest)
    document.update(release='synthetic-release', snapshot_id='synthetic-snapshot', expected_count=2)
    document['files'][0].update(bytes=original.stat().st_size, sha256=digest)
    root = tmp_path / name
    for folder in ['registry/datasets', 'registry/recipes']:
        (root / folder).mkdir(parents=True)
    (root / 'registry/datasets' / (name + '.yaml')).write_text(yaml.safe_dump(baseline))
    (root / 'registry/recipes' / (name + '.yaml')).write_text(yaml.safe_dump(document))

    def no_network(*args, **kwargs):
        raise AssertionError('Hardlinked synthetic source must not trigger a network read')

    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher.fetch', no_network)
    manager = PreparationManager(root)
    cold = manager.plan(name, original.stat().st_size, 2_000_000)
    assert cold['ready'] and cold['kind'] == 'http_archive'
    assert cold['expected_download_bytes'] == original.stat().st_size
    objects = root / 'work/source-objects'
    objects.mkdir()
    os.link(original, objects / digest)
    plan = manager.plan(name, original.stat().st_size, 2_000_000)
    assert plan['reuse_registered_sources'] == [document['files'][0]['source_name']]
    run(root, plan['id'], activate=False)
    assert manager.status(plan['id'])['status'] == 'completed'
    version = root / 'work/prepared' / name / plan['id']
    dataset = Dataset.model_validate_json((version / 'dataset.json').read_text())
    assert dataset.adapter == 'embedded_parquet'
    copied = Path(dataset.adapter_config['path'])
    assert copied.stat().st_ino == original.stat().st_ino
    control = Dataset.model_validate(baseline)
    control.adapter_config['path'] = str(original)
    adapter = get_adapter(control)
    expected = adapter.iter_records(adapter.prepare(adapter.plan(100, 2_000_000))).records
    reader = ParquetSnapshot(root, version / 'snapshot')
    actual = reader.records([record.id for record in expected])
    assert list(actual.values()) == expected
    pack = Pack.model_validate_json((version / 'pack/pack.json').read_text())
    assert len(pack.records) == 2 and not pack.checksums
    assert not list(version.rglob('*.png'))
    prepared_adapter = get_adapter(dataset)
    for record in pack.records:
        asset = record.assets[0]
        source = prepared_adapter.prepare(prepared_adapter.plan(1, 2_000_000))
        handle = prepared_adapter.resolve_original_asset(source, asset.uri)
        assert hashlib.sha256(handle.data).hexdigest() == asset.sha256
    receipt = json.loads((version / 'receipt.json').read_text())
    assert receipt['total_transfer_bytes'] == 0
    assert not (version.parent / 'active.json').exists()


@pytest.mark.parametrize('name', NAMES)
def test_direct_recipe_preserves_card_identity_and_parser(name):
    document = yaml.safe_load((ROOT / 'registry/recipes' / (name + '.yaml')).read_text())
    baseline = yaml.safe_load((ROOT / 'registry/datasets' / (name + '.yaml')).read_text())
    assert document['adapter'] == baseline['adapter'] == 'embedded_parquet'
    assert document['release'] == baseline['release']
    assert document['snapshot_id'] == baseline['snapshot_id']
    assert document['expected_count'] == baseline['coverage']['total_count']
    assert len(document['files']) == 1 and document['files'][0]['config_key'] == 'path'
    assert document['files'][0]['sha256'] == baseline['adapter_config']['sha256']
    assert document['adapter_config']['mapping'] == baseline['adapter_config']['mapping']
    assert document['adapter_config']['media_columns'] == baseline['adapter_config']['media_columns']
