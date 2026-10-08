import hashlib
import json
import zipfile

import pytest

from dataset_atlas.adapters.visual_genome import VisualGenomeAdapter
from dataset_atlas.models import Dataset


def fixture(tmp_path, orphan_image=False):
    rows = {
        'image': [{'image_id': 7, 'url': 'http://native.example/root/VG_100K/7.jpg', 'width': 8, 'height': 6},
                  {'image_id': 8, 'url': 'http://native.example/root/VG_100K/8.jpg', 'width': 9, 'height': 7}],
        'regions': [{'id': 7, 'regions': [{'image_id': 7, 'region_id': 11}]}, {'id': 8, 'regions': [{'image_id': 8, 'region_id': 12}]}],
        'questions': [{'id': 7, 'qas': [{'qa_id': 21, 'image_id': 7, 'question': 'Fixture?'}]}],
        'paragraphs': [{'image_id': 9 if orphan_image else 7, 'paragraph': 'First'}, {'image_id': 7, 'paragraph': 'Second'}],
        'qa_objects': {'21': {'question_objects': []}},
        'qa_to_region_mapping': {'21': 11, '22': 12, '23': 99},
    }
    tables, files, config = [], [], {}
    for name, values in rows.items():
        path = tmp_path/(name+'.zip')
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(name+'.json', json.dumps(values))
        key = 'image_data_path' if name == 'image' else name+'_path'
        config[key] = str(path)
        spec = dict(path_key=key, member=name+'.json', field=name)
        if name.startswith('qa_'): spec['qa_keyed'] = True
        else: spec['key'] = 'id' if name in {'regions', 'questions'} else 'image_id'
        if name == 'questions': spec['qa_list'] = 'qas'
        if name == 'regions': spec['region_list'] = 'regions'
        if name == 'paragraphs': spec['multiple'] = True
        if name == 'qa_to_region_mapping': spec['region_mapping'] = True
        tables.append(spec)
        files.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    config.update(tables=tables, source_files=files, join_index_path=str(tmp_path/'derived'/'join.sqlite'), annotations=[{'path_key': spec['path_key']} for spec in tables],
                  media_path_remove_prefix='root/', media_archive_by_prefix={'VG_100K': 'vg'}, remote_archives={'vg': {'etag': '"fixture"'}})
    return VisualGenomeAdapter(Dataset(id='vg', name='Fixture', release='r', snapshot_id='s', adapter='visual_genome', adapter_config=config))


def test_streaming_join_preserves_native_repeated_and_unjoined_rows(tmp_path):
    adapter = fixture(tmp_path)
    source = adapter.prepare(adapter.plan(2, 100000))
    first = adapter.iter_records(source)
    last = adapter.iter_records(source, first.next_cursor)
    assert adapter.count == 3 and first.next_cursor == '2' and last.next_cursor is None
    assert [p['paragraph'] for p in first.records[0].source['paragraphs']] == ['First', 'Second']
    assert first.records[0].source['qa_objects']['21'] == {'question_objects': []}
    assert first.records[1].source['qa_to_region_mapping'] == {'22': 12}
    assert first.records[0].assets[0].uri == 'zip/vg/VG_100K/7.jpg'
    assert last.records[0].source['orphan_qa_to_region_mapping'] == {'23': 99}
    assert not last.records[0].assets
    # Reopen the derived index and page across the images/orphans boundary.
    fresh = VisualGenomeAdapter(adapter.dataset)
    page = fresh.iter_records(fresh.prepare(fresh.plan(10, 100000)), '1')
    assert [r.id for r in page.records] == [first.records[1].id, last.records[0].id]
    assert fresh.derived_sources[0]['bytes'] > 0
    fresh.config['tables'][0]['key'] = 'changed'
    fresh.__dict__.pop('_index_ready', None)
    with pytest.raises(ValueError, match='does not match'):
        fresh._ensure_index()


def test_streaming_join_rejects_undeclared_image_and_disk_overrun(tmp_path):
    adapter = fixture(tmp_path, orphan_image=True)
    with pytest.raises(ValueError, match='Unmatched.*image ID'):
        adapter.prepare(adapter.plan(10, 100000))
    assert not adapter._index_path().exists()
    adapter = fixture(tmp_path)
    adapter.config['max_join_bytes'] = 4096
    with pytest.raises(Exception, match='full'):
        adapter.prepare(adapter.plan(10, 100000))
    assert not adapter._index_path().exists()


def test_join_cancellation_cleans_partial_derivative_without_touching_originals(tmp_path):
    adapter = fixture(tmp_path)
    original = {p.name: p.read_bytes() for p in tmp_path.glob('*.zip')}
    def cancel(): raise InterruptedError('cancelled')
    with pytest.raises(InterruptedError): adapter.validate_media(1000, cancel)
    assert not adapter._index_path().exists()
    assert not list((tmp_path/'derived').glob('*.tmp'))
    assert original == {p.name: p.read_bytes() for p in tmp_path.glob('*.zip')}
    adapter = fixture(tmp_path)
    del adapter.config['join_index_path']
    with pytest.raises(ValueError, match='explicit writable'): adapter._ensure_index()
    assert not (tmp_path/'visual-genome-join.sqlite').exists()


def test_existing_join_obeys_reduced_disk_budget_and_qa_region_agreement(tmp_path):
    adapter = fixture(tmp_path)
    adapter.prepare(adapter.plan(10, 100000))
    fresh = VisualGenomeAdapter(adapter.dataset)
    fresh.config['max_join_bytes'] = 4096
    with pytest.raises(ValueError, match='exceeds disk budget'): fresh._ensure_index()
    adapter._index_path().unlink()
    archive = tmp_path/'qa_to_region_mapping.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('qa_to_region_mapping.json', json.dumps({'21': 12}))
    with pytest.raises(ValueError, match='different images'): VisualGenomeAdapter(adapter.dataset)._ensure_index()


def test_original_media_preparation_never_builds_an_annotation_join(tmp_path, monkeypatch):
    adapter = fixture(tmp_path)
    monkeypatch.setattr(adapter, '_ensure_index', lambda: pytest.fail('Media access rebuilt the annotation join'))
    source = adapter.prepare_media(adapter.plan(1, 100000))
    assert source.dataset_id == 'vg'
    assert not adapter._index_path().exists()
    # Native source validation still applies even though the join is unnecessary.
    corrupted = tmp_path / 'image.zip'
    corrupted.write_bytes(b'changed source')
    fresh = VisualGenomeAdapter(adapter.dataset)
    with pytest.raises(ValueError, match='annotation checksum changed'):
        fresh.prepare_media(fresh.plan(1, 100000))
