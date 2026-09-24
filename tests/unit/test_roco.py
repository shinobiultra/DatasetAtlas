import hashlib
import io
import zipfile

import pytest
from PIL import Image


def _fixture(tmp_path, dataset):
    from dataset_atlas.adapters.roco import _ROOT

    path = tmp_path/'roco.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for split in ('train', 'validation', 'test'):
            for domain in ('radiology', 'non-radiology'):
                base = f'{_ROOT}/{split}/{domain}'
                chosen = split == 'train' and domain == 'radiology'
                archive.writestr(f'{base}/captions.txt',
                    'ROCO_00001\tFirst caption\ncontinued text\nROCO_00002\tSecond caption\n' if chosen else '')
                archive.writestr(f'{base}/dlinks.txt',
                    'ROCO_00001\twget -r ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/aa/bb/PMC1234.tar.gz -P /tmp\tfirst.jpg\n'
                    'ROCO_00002\twget -r ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/cc/dd/PMC5678.tar.gz -P /tmp\tsecond.jpg\n' if chosen else '')
                archive.writestr(f'{base}/licences.txt',
                    'ROCO_ID,PMC_ID,CC\nROCO_00001,PMC1234_first.jpg,CC BY\n' if chosen else 'ROCO_ID,PMC_ID,CC\n')
                for name in ('keywords', 'cuis', 'semtypes'):
                    archive.writestr(f'{base}/{name}.txt',
                        'ROCO_00001\t\talpha\nROCO_00002\t\tbeta\n' if chosen else '')
    dataset.id = 'roco'
    dataset.release = 'synthetic-test-release'
    dataset.snapshot_id = 'synthetic-test-snapshot'
    dataset.adapter = 'roco'
    dataset.adapter_config = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                              'expected_count': 2}
    return path


def test_roco_preserves_native_join_and_checks_current_pmc_media(tmp_path, pack, monkeypatch):
    from dataset_atlas.adapters.roco import RocoAdapter

    _fixture(tmp_path, pack.dataset)
    adapter = RocoAdapter(pack.dataset)
    source = adapter.prepare(adapter.plan(2, 1_000_000))
    assert adapter.count == 2
    rows = adapter.iter_records(source, limit=2).records
    assert rows[0].text == 'First caption\ncontinued text'
    assert rows[0].source['licence'] == 'CC BY'
    assert rows[1].source['licence'] is None

    image = io.BytesIO()
    Image.new('RGB', (11, 7), 'red').save(image, 'JPEG')
    payload = image.getvalue()
    md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    adapter._metadata['PMC1234'] = {
        'pmcid': 'PMC1234',
        'media_urls': [f's3://pmc-oa-opendata/PMC1234.1/first.jpg?md5={md5}'],
    }

    class Response:
        headers = {'Content-Length': str(len(payload))}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def raise_for_status(self): pass
        def iter_bytes(self, _): yield payload

    monkeypatch.setattr('dataset_atlas.adapters.roco.httpx.stream', lambda *_, **__: Response())
    media = adapter.resolve_asset(source, rows[0].assets[0].uri)
    assert media.data == payload and media.media_type == 'image/jpeg'
    adapter._metadata['PMC1234']['media_urls'] = [
        's3://pmc-oa-opendata/PMC1234.1/first.jpg?md5=' + '0'*32]
    with pytest.raises(ValueError, match='checksum'):
        adapter.resolve_asset(source, rows[0].assets[0].uri)


def test_roco_rejects_unjoined_source_images(tmp_path, pack):
    from dataset_atlas.adapters.roco import RocoAdapter, _ROOT

    path = _fixture(tmp_path, pack.dataset)
    with zipfile.ZipFile(path) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    contents[f'{_ROOT}/train/radiology/dlinks.txt'] = b'ROCO_00001\tbroken\tfirst.jpg\n'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, payload in contents.items():
            archive.writestr(name, payload)
    pack.dataset.adapter_config['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='caption and source-image IDs differ'):
        RocoAdapter(pack.dataset).count
