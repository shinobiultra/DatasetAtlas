"""A researcher can add their own folder or table and browse it like any catalogue dataset.

Fixtures are synthetic by necessity: these are the researcher's files, not catalogue data. The point is
that inspection is honest (exact counts, typed columns, missing media reported), registration never
touches the source, and the shipped catalogue can neither be shadowed nor modified.
"""
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from PIL import Image

from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.registry import Registry
from dataset_atlas.registry.user import inspect_source, register, slugify, unregister


def image(path: Path, colour=(200, 30, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (8, 8), colour).save(path)


@pytest.fixture
def lab(tmp_path):
    root = tmp_path / 'lab'
    (root / 'registry/datasets').mkdir(parents=True)
    return root


@pytest.fixture
def classes(tmp_path):
    folder = tmp_path / 'sorted'
    for label in ('cat', 'dog', 'bird'):
        for i in range(4):
            image(folder / label / f'{i}.png')
    (folder / '.hidden').write_text('not an image')
    (folder / 'notes.txt').write_text('ignored')
    return folder


def write_csv(path: Path, rows: list[dict]):
    columns = list(rows[0])
    path.write_text('\n'.join([','.join(columns)] + [','.join(str(r[c]) for c in columns) for r in rows]) + '\n')


# ---- folders -------------------------------------------------------------------------------

def test_class_folders_become_a_label_and_the_count_is_exact(classes):
    found = inspect_source(str(classes))
    assert (found['kind'], found['adapter'], found['count']) == ('images', 'directory', 12)
    assert found['adapter_config']['fields']['label']['values'] == ['bird', 'cat', 'dog']
    assert found['labels'] == ['label']
    assert found['modalities'] == ['image']


def test_flat_folder_has_no_label(tmp_path):
    for i in range(3):
        image(tmp_path / 'flat' / f'{i}.jpg')
    found = inspect_source(str(tmp_path / 'flat'))
    assert found['count'] == 3 and found['labels'] == [] and 'path_regex' not in found['adapter_config']


def test_mixed_depth_does_not_invent_labels_and_says_so(tmp_path):
    image(tmp_path / 'mixed/top.png')
    image(tmp_path / 'mixed/a/one.png')
    image(tmp_path / 'mixed/b/two.png')
    found = inspect_source(str(tmp_path / 'mixed'))
    assert found['count'] == 3 and found['labels'] == []
    assert any('different folder depths' in w for w in found['warnings'])


def test_folder_suggests_adding_a_beside_table(tmp_path):
    image(tmp_path / 'both/0.png')
    (tmp_path / 'both/labels.csv').write_text('file,score\n0.png,1\n')
    assert any('labels.csv' in w for w in inspect_source(str(tmp_path / 'both'))['warnings'])


@pytest.mark.parametrize('make,message', [
    (lambda p: p.mkdir(), 'No images found'),
    (lambda p: p.write_text('x'), 'Unsupported source type'),
])
def test_unusable_sources_fail_with_an_actionable_message(tmp_path, make, message):
    target = tmp_path / 'thing.xyz' if message.startswith('Unsupported') else tmp_path / 'empty'
    make(target)
    with pytest.raises(ValueError, match=message):
        inspect_source(str(target))


def test_relative_and_missing_paths_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='absolute path'):
        inspect_source('some/relative')
    with pytest.raises(ValueError, match='No such file'):
        inspect_source(str(tmp_path / 'nope'))


def test_zip_archive_of_images_is_counted_without_extraction(tmp_path):
    import zipfile
    archive = tmp_path / 'pics.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        for i in range(3):
            image(tmp_path / 'stage' / f'{i}.png')
            z.write(tmp_path / 'stage' / f'{i}.png', f'pics/{i}.png')
    found = inspect_source(str(archive))
    assert found['count'] == 3 and found['adapter_config']['sha256']


# ---- tables --------------------------------------------------------------------------------

@pytest.fixture
def table(tmp_path):
    for i in range(6):
        image(tmp_path / 'imgs' / f'{i}.png')
    rows = [{'file': f'imgs/{i}.png', 'score': i * 1.5, 'group': 'a' if i % 2 else 'b', 'blank': '' if i == 2 else str(i),
             'caption': f'A fairly long free-text description of picture number {i} for testing.'} for i in range(6)]
    write_csv(tmp_path / 'meta.csv', rows)
    return tmp_path / 'meta.csv'


def test_csv_columns_are_typed_roles_are_found_and_media_is_checked(table):
    found = inspect_source(str(table))
    roles = {c['name']: c['role'] for c in found['columns']}
    assert roles['file'] == 'media' and roles['caption'] == 'text' and roles['group'] == 'label'
    assert found['count'] == 6 and found['unit'] == 'rows'
    assert found['adapter_config']['csv_types'] == {'score': 'number', 'blank': 'number'}
    assert found['adapter_config']['fields']['group']['values'] == ['a', 'b']
    assert found['adapter_config']['media_root'] == str(table.parent)
    assert found['modalities'] == ['image', 'text'] and found['warnings'] == []


def test_missing_media_is_reported_not_hidden(tmp_path):
    write_csv(tmp_path / 'm.csv', [{'file': f'nothing/{i}.png', 'n': i} for i in range(3)])
    found = inspect_source(str(tmp_path / 'm.csv'))
    assert any('None of the first 3' in w for w in found['warnings'])


def test_blank_numeric_cells_are_missing_not_zero(table):
    from dataset_atlas.adapters import get_adapter
    from dataset_atlas.models import Dataset
    found = inspect_source(str(table))
    rows = list(get_adapter(Dataset(id='x', name='x', adapter='structured', snapshot_id='s', release='r', adapter_config=found['adapter_config']))._rows())
    assert rows[2]['blank'] is None and rows[3]['blank'] == 3 and rows[1]['score'] == 1.5


def test_a_column_that_is_not_wholly_numeric_stays_text(tmp_path):
    write_csv(tmp_path / 'm.csv', [{'code': v} for v in ('1', '2', 'x7')])
    assert 'csv_types' not in inspect_source(str(tmp_path / 'm.csv'))['adapter_config']


def test_id_column_must_be_unique(tmp_path):
    write_csv(tmp_path / 'm.csv', [{'key': 'a', 'v': 1}, {'key': 'a', 'v': 2}])
    with pytest.raises(ValueError, match='not unique'):
        inspect_source(str(tmp_path / 'm.csv'), {'id_column': 'key'})
    write_csv(tmp_path / 'u.csv', [{'key': 'a', 'v': 1}, {'key': 'b', 'v': 2}])
    assert inspect_source(str(tmp_path / 'u.csv'), {'id_column': 'key'})['adapter_config']['mapping']['id'] == 'key'


def test_tsv_jsonl_json_and_parquet_are_read(tmp_path):
    (tmp_path / 'a.tsv').write_text('x\ty\n1\tfoo\n2\tbar\n')
    assert inspect_source(str(tmp_path / 'a.tsv'))['count'] == 2
    (tmp_path / 'b.jsonl').write_text('\n'.join(json.dumps({'n': i, 'tag': 'q'}) for i in range(5)))
    assert inspect_source(str(tmp_path / 'b.jsonl'))['count'] == 5
    (tmp_path / 'c.json').write_text(json.dumps([{'n': 1}, {'n': 2}, {'n': 3}]))
    assert inspect_source(str(tmp_path / 'c.json'))['count'] == 3
    pq.write_table(pa.table({'n': [1, 2, 3, 4], 'tag': list('abab')}), tmp_path / 'd.parquet')
    found = inspect_source(str(tmp_path / 'd.parquet'))
    assert found['count'] == 4 and found['adapter'] == 'structured'


def test_parquet_with_embedded_images_uses_the_embedded_adapter(tmp_path):
    import io
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4)).save(buffer, format='PNG')
    struct = pa.array([{'bytes': buffer.getvalue(), 'path': None}] * 3, type=pa.struct([('bytes', pa.binary()), ('path', pa.string())]))
    pq.write_table(pa.table({'image': struct, 'label': [0, 1, 0]}), tmp_path / 'e.parquet')
    found = inspect_source(str(tmp_path / 'e.parquet'))
    assert (found['adapter'], found['count'], found['modalities']) == ('embedded_parquet', 3, ['image'])
    assert found['adapter_config']['media_columns'] == ['image']


def test_huggingface_urls_are_validated_before_any_request():
    with pytest.raises(ValueError, match='Only Hugging Face dataset URLs'):
        inspect_source('https://example.com/not/a/dataset')


# ---- registration --------------------------------------------------------------------------

def test_registration_writes_a_user_entry_and_never_touches_the_source(lab, classes):
    before = sorted(p.name for p in classes.rglob('*'))
    entry = register(lab, inspect_source(str(classes)), name='My Sorted Pets')
    assert entry.id == 'my-sorted-pets' and entry.origin == 'user'
    written = lab / 'local-config/registry/datasets/my-sorted-pets.yaml'
    assert written.is_file() and yaml.safe_load(written.read_text())['origin'] == 'user'
    assert sorted(p.name for p in classes.rglob('*')) == before
    shown = Registry(lab).dataset('my-sorted-pets')
    assert shown.coverage.total_count == 12 and shown.coverage.access == 'locally_supplied'
    assert shown.coverage.publication == 'not_reviewed' and shown.rights == {}


def test_a_user_cannot_shadow_or_overwrite_the_shipped_catalogue(lab, classes):
    shipped = {'id': 'clevr', 'name': 'CLEVR', 'origin': 'catalogue', 'schema_version': '1.0'}
    (lab / 'registry/datasets/clevr.yaml').write_text(yaml.safe_dump(shipped))
    with pytest.raises(ValueError, match='shipped catalogue'):
        register(lab, inspect_source(str(classes)), name='CLEVR', dataset_id='clevr')


def test_duplicate_ids_need_an_explicit_replace(lab, classes):
    found = inspect_source(str(classes))
    register(lab, found, name='Pets')
    with pytest.raises(ValueError, match='already added'):
        register(lab, found, name='Pets')
    assert register(lab, found, name='Pets again', dataset_id='pets', replace=True).name == 'Pets again'


@pytest.mark.parametrize('bad', ['A', 'x', '-lead', 'UPPER', 'has space', 'a' * 64, 'dots.no'])
def test_invalid_ids_are_refused(lab, classes, bad):
    with pytest.raises(ValueError, match='lowercase letters'):
        register(lab, inspect_source(str(classes)), name='x y', dataset_id=bad)


def test_slugify_is_stable_and_safe():
    assert slugify('My Dataset (v2)!') == 'my-dataset-v2'
    assert slugify('!!') .startswith('dataset-')


def test_a_hand_written_user_file_must_declare_its_origin(lab):
    (lab / 'local-config/registry/datasets').mkdir(parents=True)
    (lab / 'local-config/registry/datasets/sneaky.yaml').write_text(yaml.safe_dump({'id': 'sneaky', 'name': 'x', 'schema_version': '1.0'}))
    with pytest.raises(ValueError, match='origin: user'):
        Registry(lab).datasets()


def test_unregister_keeps_source_files_and_purges_only_on_request(lab, classes):
    register(lab, inspect_source(str(classes)), name='Pets')
    (lab / 'work/prepared/pets/v1').mkdir(parents=True)
    result = unregister(lab, 'pets')
    assert result['source_files_touched'] is False and result['purged'] == []
    assert (lab / 'work/prepared/pets/v1').exists() and len(list(classes.rglob('*.png'))) == 12
    register(lab, inspect_source(str(classes)), name='Pets')
    assert unregister(lab, 'pets', purge=True)['purged'] == ['work/prepared/pets']
    assert not (lab / 'work/prepared/pets').exists()


def test_only_user_datasets_can_be_unregistered(lab):
    (lab / 'registry/datasets/clevr.yaml').write_text(yaml.safe_dump({'id': 'clevr', 'name': 'CLEVR', 'schema_version': '1.0'}))
    with pytest.raises(KeyError, match='not a dataset you added'):
        unregister(lab, 'clevr')


# ---- end to end through the real preparation pipeline -------------------------------------

def prepare(lab, dataset_id):
    manager = PreparationManager(lab)
    plan = manager.plan(dataset_id, 1_000_000, 50_000_000, 'auto')
    assert plan['ready'], plan['requirements']
    assert plan['expected_download_bytes'] == 0
    run(lab, plan['id'])
    status = manager.status(plan['id'])
    assert status['status'] == 'completed', status.get('error')
    return Registry(lab).pack(dataset_id), plan


def test_an_image_folder_is_prepared_into_a_browsable_indexed_preview(lab, tmp_path):
    folder = tmp_path / 'big'
    for label in ('x', 'y'):
        for i in range(60):
            image(folder / label / f'{i}.png', (i * 3 % 255, 10, 10))
    register(lab, inspect_source(str(folder)), name='Big folder')
    pack, _ = prepare(lab, 'big-folder')
    assert len(pack.records) == 100
    assert {r.source['label'] for r in pack.records} == {'x', 'y'}
    # The preview states what it samples from: a seeded draw over the complete indexed population, not a prefix.
    assert (pack.sampling['population_count'], pack.sampling['requested_count'], pack.sampling['returned_count']) == (120, 100, 100)
    assert pack.sampling['method'] == 'sha256_bottom_k_primary_asset' and pack.sampling['seed'] == 0
    assert Registry(lab).dataset('big-folder').coverage.total_count == 120
    assert Registry(lab).local_state('big-folder') == (True, True)


def test_a_table_with_media_is_prepared_with_typed_columns_and_resolvable_images(lab, table):
    register(lab, inspect_source(str(table)), name='Scored pictures')
    pack, _ = prepare(lab, 'scored-pictures')
    assert len(pack.records) == 6
    by_score = {r.source['score'] for r in pack.records}
    assert by_score == {0, 1.5, 3.0, 4.5, 6.0, 7.5}
    assert any(r.source['blank'] is None for r in pack.records)
    assert all(len(r.assets) == 1 for r in pack.records)
    from dataset_atlas.adapters import resolve_dataset_asset
    dataset = Registry(lab).dataset('scored-pictures')
    handle = resolve_dataset_asset(dataset, pack.records[0].assets[0].uri)
    assert handle.data[:4] == b'\x89PNG'


def test_replacing_a_changed_source_creates_a_new_snapshot_and_keeps_the_old_one(lab, tmp_path):
    folder = tmp_path / 'grow'
    for i in range(3):
        image(folder / f'{i}.png')
    first = register(lab, inspect_source(str(folder)), name='Grow')
    for i in range(3, 5):
        image(folder / f'{i}.png')
    second = register(lab, inspect_source(str(folder)), name='Grow', replace=True)
    assert first.snapshot_id != second.snapshot_id and second.coverage.total_count == 5


# ---- HTTP API ------------------------------------------------------------------------------

def http(lab):
    from fastapi.testclient import TestClient
    from dataset_atlas.api.app import create_app
    return TestClient(create_app(lab), headers={'X-Atlas-Request': '1'})


def test_api_inspects_adds_prepares_and_removes_without_exposing_local_paths(lab, classes):
    client = http(lab)
    found = client.post('/api/v1/local-datasets/inspect', json={'source': str(classes)})
    assert found.status_code == 200 and found.json()['count'] == 12
    assert str(classes) not in found.text and 'adapter_config' not in found.json()
    added = client.post('/api/v1/local-datasets', json={'source': str(classes), 'name': 'Pets'})
    assert added.status_code == 200
    detail = added.json()['dataset']
    assert detail['origin'] == 'user' and detail['adapter_config'] == {} and str(classes) not in added.text
    # Registered but not yet prepared: the interface offers to build its preview rather than claiming records exist.
    assert detail['availability']['preview'] == 'on_request' and detail['coverage']['preview_count'] == 0
    assert any(d['id'] == 'pets' for d in client.get('/api/v1/datasets').json())
    removed = client.delete('/api/v1/local-datasets/pets')
    assert removed.status_code == 200 and removed.json()['source_files_touched'] is False
    assert all(d['id'] != 'pets' for d in client.get('/api/v1/datasets').json())


def test_api_requires_the_state_change_header_and_explains_errors(lab, classes):
    from fastapi.testclient import TestClient
    from dataset_atlas.api.app import create_app
    bare = TestClient(create_app(lab))
    assert bare.post('/api/v1/local-datasets', json={'source': str(classes)}).status_code == 403
    assert bare.delete('/api/v1/local-datasets/x').status_code == 403
    client = http(lab)
    bad = client.post('/api/v1/local-datasets/inspect', json={'source': 'relative/path'})
    assert bad.status_code == 422 and 'absolute path' in bad.json()['detail']
    assert client.delete('/api/v1/local-datasets/never-added').status_code == 404
    assert client.post('/api/v1/local-datasets', json={'source': str(classes), 'extra': 1}).status_code == 422


# ---- declared CSV types in catalogue entries -----------------------------------------------

def test_catalogue_csv_fields_declared_numeric_are_cast_and_blanks_stay_missing(tmp_path):
    from dataset_atlas.adapters import get_adapter
    from dataset_atlas.models import Dataset
    (tmp_path / 'm.csv').write_text('id,score,flag,pick\n1,0.5,true,a\n2,,false,b\n3,7,true,a\n')
    config = {'path': str(tmp_path / 'm.csv'), 'format': 'csv', 'fields': {
        'score': {'dtype': 'number'}, 'flag': {'dtype': 'boolean'}, 'pick': {'dtype': 'category', 'values': ['a', 'b']}}}
    rows = list(get_adapter(Dataset(id='x', name='x', adapter='csv', snapshot_id='s', release='r', adapter_config=config))._rows())
    assert [r['score'] for r in rows] == [0.5, None, 7] and [r['flag'] for r in rows] == [True, False, True]
    assert [r['id'] for r in rows] == ['1', '2', '3'] and [r['pick'] for r in rows] == ['a', 'b', 'a']


def test_a_column_declared_numeric_that_is_not_fails_loudly_instead_of_loading_text(tmp_path):
    from dataset_atlas.adapters import get_adapter
    from dataset_atlas.models import Dataset
    (tmp_path / 'm.csv').write_text('who\nk_x\nk_y\n')
    config = {'path': str(tmp_path / 'm.csv'), 'format': 'csv', 'fields': {'who': {'dtype': 'number'}}}
    adapter = get_adapter(Dataset(id='x', name='x', adapter='csv', snapshot_id='s', release='r', adapter_config=config))
    with pytest.raises(ValueError, match="column 'who' is declared numeric"):
        list(adapter._rows())


def test_a_folder_far_too_large_to_be_a_dataset_is_refused_without_a_full_walk(tmp_path, monkeypatch):
    import dataset_atlas.registry.user as user
    for i in range(30):
        image(tmp_path / 'huge' / f'{i}.png')
    monkeypatch.setattr(user, 'MAX_FOLDER_ENTRIES', 10)
    with pytest.raises(ValueError, match='more than 10 files'):
        inspect_source(str(tmp_path / 'huge'))
    monkeypatch.setattr(user, 'MAX_FOLDER_ENTRIES', 1000)
    assert inspect_source(str(tmp_path / 'huge'))['count'] == 30
