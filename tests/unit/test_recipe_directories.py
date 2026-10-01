"""Recipes can place files by name in a directory the adapter reads, and fix a portable snapshot ID.

Some releases (MNIST's IDX files, image sets referenced by name) are read as a directory of files, not
as one archive. Fetching must also give two workspaces the same snapshot ID for the same bytes.
"""
import hashlib
import io
import json

import pytest
import yaml
from PIL import Image

from dataset_atlas.models import Coverage, Dataset
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.registry import Registry


def png():
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), (9, 99, 199)).save(buffer, format='PNG')
    return buffer.getvalue()


def workspace(root, recipe_extra=None, files_extra=None):
    (root / 'registry/datasets').mkdir(parents=True)
    (root / 'registry/recipes').mkdir(parents=True)
    entry = Dataset(id='listed', name='Listed', release='r0', snapshot_id='s0', adapter='structured',
                    adapter_config={'path': 'work/sources/missing.json', 'mapping': {'id': 'id', 'media': 'image', 'text': 'text'}},
                    coverage=Coverage(preview_count=1, total_count=2))
    (root / 'registry/datasets/listed.yaml').write_text(yaml.safe_dump(entry.model_dump()))
    records = root / 'records.json'
    records.write_text(json.dumps([{'id': 'a', 'image': 'one.png', 'text': 'first'}, {'id': 'b', 'image': 'one.png', 'text': 'second'}]))
    image = root / 'one.png'
    image.write_bytes(png())
    def file(path, name, **more):
        return {'url': f'https://example.org/{name}', 'source_name': name, 'bytes': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **more}
    recipe = {'adapter': 'structured', 'release': 'listed-r1', 'expected_count': 2, 'scope': 'two listed records',
              'adapter_config': {'mapping': {'id': 'id', 'media': 'image', 'text': 'text'}},
              'files': [file(records, 'records.json', config_key='path', format='json'),
                        file(image, 'one.png', config_dir='media_root', format='png', **(files_extra or {}))],
              **(recipe_extra or {})}
    (root / 'registry/recipes/listed.yaml').write_text(yaml.safe_dump(recipe))
    return records, image


def fetch(root, monkeypatch, records, image):
    paths = {'https://example.org/records.json': records, 'https://example.org/one.png': image}
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch', lambda self, url, *a, **k: paths[url])
    manager = PreparationManager(root)
    plan = manager.plan('listed', 10_000_000, 10_000_000)
    assert plan['ready'], plan['requirements']
    run(root, plan['id'])
    assert manager.status(plan['id'])['status'] == 'completed'
    return Registry(root).dataset('listed')


def test_files_are_placed_by_name_in_the_directory_the_adapter_reads(tmp_path, monkeypatch):
    records, image = workspace(tmp_path)
    dataset = fetch(tmp_path, monkeypatch, records, image)
    media = dataset.adapter_config['media_root']
    assert (tmp_path / 'work/prepared/listed').resolve() in __import__('pathlib').Path(media).resolve().parents
    assert open(f'{media}/one.png', 'rb').read() == png()
    from dataset_atlas.adapters import resolve_dataset_asset
    assert resolve_dataset_asset(dataset, 'one.png').data == png()


def test_dest_name_renames_the_placed_file(tmp_path, monkeypatch):
    records, image = workspace(tmp_path, files_extra={'dest_name': 'renamed.png'})
    dataset = fetch(tmp_path, monkeypatch, records, image)
    from pathlib import Path
    assert sorted(p.name for p in Path(dataset.adapter_config['media_root']).iterdir()) == ['renamed.png']


@pytest.mark.parametrize('bad', ['../escape.png', 'sub/dir.png', '.hidden/../x'])
def test_unsafe_destination_names_are_rejected_at_plan_time(tmp_path, bad):
    workspace(tmp_path, files_extra={'dest_name': bad})
    with pytest.raises(ValueError, match='plain file name'):
        PreparationManager(tmp_path).plan('listed', 10_000_000, 10_000_000)


def test_a_reviewed_recipe_snapshot_id_is_used_verbatim(tmp_path, monkeypatch):
    records, image = workspace(tmp_path, recipe_extra={'snapshot_id': 'listed-reviewed-2026'})
    assert fetch(tmp_path, monkeypatch, records, image).snapshot_id == 'listed-reviewed-2026'


def test_two_workspaces_fetching_the_same_bytes_share_a_snapshot_id(tmp_path, monkeypatch):
    ids = []
    for name, budget in (('ann', 10_000_000), ('bob-with-a-longer-path', 99_000_000)):
        root = tmp_path / name
        records, image = workspace(root)
        monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch',
                            lambda self, url, *a, _r=records, _i=image, **k: _r if url.endswith('.json') else _i)
        manager = PreparationManager(root)
        plan = manager.plan('listed', budget, budget)
        run(root, plan['id'])
        ids.append(Registry(root).dataset('listed').snapshot_id)
    assert ids[0] == ids[1] and ids[0].startswith('listed-')
