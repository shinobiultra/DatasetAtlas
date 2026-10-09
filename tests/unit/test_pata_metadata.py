import json
from pathlib import Path
import pytest
from dataset_atlas.converters.pata import native_rows
from dataset_atlas.preparation.pata import prepare_metadata, REVISION, SOURCES
from dataset_atlas.converters.pata import convert_pata


def inputs(tmp_path, lines='scene_with_parts_R_G_A|https://example.test/a.jpg\n', groups=None):
    files = tmp_path / 'native.lst'
    captions = tmp_path / 'captions.json'
    files.write_text(lines)
    captions.write_text(json.dumps(groups if groups is not None else [
        {'short': 'scene_with_parts', 'long': 'Synthetic caption', 'pos': {'age': ['Synthetic positive']}, 'neg': {}}]))
    return files, captions


def test_duplicate_native_label_groups_keep_each_url_and_exact_caption(tmp_path):
    lines = ('scene_with_parts_R_G_A|https://example.test/a.jpg\r\n'
             'scene_with_parts_R_G_A|https://example.test/b.jpg\n')
    files, captions = inputs(tmp_path, lines)
    files.write_bytes(lines.encode())
    rows = list(native_rows(files, captions))
    assert [r['source_row'] for r in rows] == [0, 1]
    assert rows[0]['native_line'].endswith('\r\n')
    assert rows[0]['scene'] == 'scene_with_parts'
    assert rows[0]['media_url'].endswith('/a.jpg') and rows[1]['media_url'].endswith('/b.jpg')
    assert rows[0]['captions'] == json.loads(captions.read_text())[0]
    assert all(r['media_available'] is False for r in rows)


@pytest.mark.parametrize('line', ['no-url', 'scene_with_parts_R_G_A|file:///etc/passwd',
                                'unknown_R_G_A|https://example.test/a', 'scene_R_G|https://example.test/a'])
def test_invalid_or_unjoined_rows_are_refused(tmp_path, line):
    with pytest.raises(ValueError):
        list(native_rows(*inputs(tmp_path, line)))


def test_duplicate_and_unjoined_caption_objects_are_refused(tmp_path):
    group = {'short': 'scene_with_parts', 'long': 'Generated caption', 'pos': {}, 'neg': {}}
    for groups in [[group, group], [group, {**group, 'short': 'unused'}]]:
        with pytest.raises(ValueError):
            list(native_rows(*inputs(tmp_path, groups=groups)))


def test_cancelled_conversion_stops_before_rows_are_yielded(tmp_path):
    def cancel():
        raise TimeoutError('generated cancellation')
    with pytest.raises(TimeoutError):
        list(native_rows(*inputs(tmp_path), check=cancel))


def test_dry_run_does_not_create_sources(tmp_path):
    receipt = prepare_metadata(tmp_path)
    assert receipt['status'] == 'planned' and receipt['native_image_preview_count'] == 0
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError):
        prepare_metadata(tmp_path, max_download_bytes=1)


def test_external_source_symlink_refused_before_network(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'workspace'
    (root / 'work').mkdir(parents=True)
    (root / 'work/sources').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes'):
        prepare_metadata(root, execute=True)
    assert not list(outside.iterdir())


def test_changed_retained_native_file_refused(tmp_path):
    directory = tmp_path / 'work/sources/pata' / REVISION
    directory.mkdir(parents=True)
    (directory / SOURCES['files'][0]).write_bytes(b'generated altered source')
    with pytest.raises(ValueError, match='differs'):
        prepare_metadata(tmp_path, execute=True)


def test_output_hardlinked_to_native_input_is_refused_without_modification(tmp_path):
    import os
    files, captions = inputs(tmp_path)
    original = files.read_bytes()
    os.link(files, tmp_path / 'pata-metadata.jsonl')
    with pytest.raises(FileExistsError):
        convert_pata({}, {'files': files, 'captions': captions}, tmp_path)
    assert files.read_bytes() == original


def generated_preparation(tmp_path, monkeypatch):
    import hashlib
    from dataset_atlas.models import Dataset
    import dataset_atlas.preparation.pata as module
    directory = tmp_path / 'work/sources/pata' / REVISION
    directory.mkdir(parents=True)
    files, captions = inputs(directory, 'scene_with_parts_R_G_A|https://example.test/a.jpg\n' * 4934)
    monkeypatch.setattr(module, 'SOURCES', {key: (path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size)
                                          for key, path in [('files', files), ('captions', captions)]})
    class SyntheticRegistry:
        def __init__(self, root):
            pass
        def baseline_dataset(self, identity):
            return Dataset(id='pata', name='Generated PATA fixture')
    monkeypatch.setattr(module, 'Registry', SyntheticRegistry)
    return module.prepare_metadata(tmp_path, execute=True)


@pytest.mark.parametrize('change', ['population_scope', 'release_id', 'unit', 'fields'])
def test_resume_rejects_changed_snapshot_contract(tmp_path, monkeypatch, change):
    generated_preparation(tmp_path, monkeypatch)
    pointer = json.loads((tmp_path / 'work/prepared/pata/active.json').read_text())
    manifest = tmp_path / 'work/prepared/pata' / pointer['version'] / 'snapshot/manifest.json'
    value = json.loads(manifest.read_text())
    if change == 'fields':
        value[change][0]['name'] = 'Generated conflicting descriptor'
    else:
        value[change] = {'population_scope': 'preview', 'release_id': 'generated different release', 'unit': 'asset'}[change]
    manifest.chmod(0o644)
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        prepare_metadata(tmp_path, execute=True)


def test_resume_rejects_materialized_column_diverging_from_native_json(tmp_path, monkeypatch):
    import hashlib
    import pyarrow as pa
    import pyarrow.parquet as pq
    from dataset_atlas.queries.parquet import ParquetSnapshot
    generated_preparation(tmp_path, monkeypatch)
    pointer = json.loads((tmp_path / 'work/prepared/pata/active.json').read_text())
    directory = tmp_path / 'work/prepared/pata' / pointer['version'] / 'snapshot'
    field = ParquetSnapshot(tmp_path, directory).registry['source.media_available'][0]
    parquet = directory / 'records.parquet'
    table = pq.read_table(parquet)
    index = table.schema.get_field_index(field)
    table = table.set_column(index, table.schema.field(index), pa.array([True] * table.num_rows))
    parquet.chmod(0o644)
    pq.write_table(table, parquet)
    manifest = directory / 'manifest.json'
    value = json.loads(manifest.read_text())
    value['parquet_bytes'] = parquet.stat().st_size
    value['checksums']['records.parquet'] = hashlib.sha256(parquet.read_bytes()).hexdigest()
    manifest.chmod(0o644)
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='query field'):
        prepare_metadata(tmp_path, execute=True)


def test_source_change_during_conversion_cannot_activate_an_unpinned_index(tmp_path, monkeypatch):
    import dataset_atlas.preparation.pata as module
    generated_preparation(tmp_path, monkeypatch)
    original = module.convert_pata
    def change_then_convert(params, inputs, output_dir, check):
        path = inputs['files']
        path.write_bytes(path.read_bytes().replace(b'/a.jpg', b'/b.jpg'))
        return original(params, inputs, output_dir, check)
    # Remove only generated derived state to exercise a new conversion/index.
    import shutil
    shutil.rmtree(tmp_path / 'work/prepared')
    shutil.rmtree(tmp_path / 'work/sources/pata' / REVISION / 'converted')
    monkeypatch.setattr(module, 'convert_pata', change_then_convert)
    with pytest.raises(ValueError, match='source changed'):
        prepare_metadata(tmp_path, execute=True)
    assert not (tmp_path / 'work/prepared/pata/active.json').exists()
