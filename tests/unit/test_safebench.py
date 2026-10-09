import hashlib
import io
from pathlib import Path
import tarfile

import pytest

pytest.importorskip('indexed_gzip')

from dataset_atlas.adapters import get_adapter
from dataset_atlas.models import Dataset
from dataset_atlas.storage.indexed_tar import build_tar_index


def _source(tmp_path):
    archive = tmp_path/'safebench.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        def add(name, data):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for category in range(1, 24):
            text = '\n'.join(f'text-{category}-{item}' for item in range(1, 101)) + '\n'
            image = '\n'.join(f'image-{category}-{item}' for item in range(1, 101)) + '\n'
            add(f'final_bench/text/{category}.csv', text.encode())
            add(f'final_bench/image/{category}/out{category}.csv', image.encode())
            for item in range(1, 101):
                for name in (f'final_bench/image/{category}/{item}.png',
                             f'final_bench/audio/audio_data_male/{category}/{item}.wav',
                             f'final_bench/audio/audio_data_female/{category}/{item}.wav'):
                    add(name, name.encode())
    categories = tmp_path/'category.csv'
    categories.write_text('Index,Category\n' + ''.join(f'{item},class-{item}\n' for item in range(1, 24)))
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    index = tmp_path/'index'
    build_tar_index(archive, index, source_sha256=sha,
                    remote={'url':'https://example.com/archive.tar.gz','bytes':archive.stat().st_size,
                            'etag':'"pinned"','allowed_hosts':['example.com']},
                    max_uncompressed_bytes=20_000_000)
    return Dataset(id='safebench', name='SafeBench', adapter='safebench', release='fixture',
                   snapshot_id='fixture-snapshot', adapter_config={
                       'path':str(archive), 'sha256':sha, 'original_access_index':str(index),
                       'category_path':str(categories),
                       'category_sha256':hashlib.sha256(categories.read_bytes()).hexdigest()})


def test_safebench_preserves_native_groups_and_all_original_media(tmp_path):
    dataset = _source(tmp_path)
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(10, 2_000_000))
    assert adapter.count == 2300
    rows = adapter.iter_records(source, '2299', 5).records
    assert len(rows) == 1
    row = rows[0]
    assert row.source['category_index'] == 23
    assert row.source['ordinal'] == 100
    assert row.text == 'text-23-100'
    assert row.source['image_prompt'] == 'image-23-100'
    assert [asset.modality for asset in row.assets] == ['image', 'audio', 'audio']
    for asset in row.assets:
        handle = adapter.resolve_asset(source, asset.uri)
        assert handle.data == asset.uri.encode()
        assert handle.sha256 == asset.sha256
    with pytest.raises(ValueError, match='absent'):
        adapter.resolve_asset(source, 'final_bench/text/1.csv')


def test_safebench_rejects_changed_category_inventory(tmp_path):
    dataset = _source(tmp_path)
    Path(dataset.adapter_config['category_path']).write_text('Index,Category\n1,changed\n')
    adapter = get_adapter(dataset)
    with pytest.raises(ValueError, match='category inventory changed'):
        adapter.prepare(adapter.plan(1, 100_000))
