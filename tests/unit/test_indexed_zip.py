import hashlib
import io
import json
import zipfile

import pytest

from dataset_atlas.storage.indexed_zip import build_zip_index, read_zip_member


@pytest.mark.parametrize('method', [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_zip_originals_after_eviction_use_only_the_selected_member(tmp_path, method):
    source = tmp_path/'native.zip'
    values = {f'images/{i}.bin': bytes(range(256)) * (i + 1) for i in range(15)}
    with zipfile.ZipFile(source, 'w', compression=method) as archive:
        for name, data in values.items(): archive.writestr(name, data)
    payload = source.read_bytes()
    remote = {'url': 'https://example.org/native.zip', 'bytes': len(payload), 'etag': '"immutable"', 'allowed_hosts': ['example.org']}
    index = tmp_path/'index'
    receipt = build_zip_index(source, index, source_sha256=hashlib.sha256(payload).hexdigest(), remote=remote, max_input_bytes=100_000)
    assert receipt['members'] == len(values)
    source.unlink()
    class Ranges(io.BytesIO):
        def __init__(self, url, **kwargs):
            super().__init__(payload); self.bytes_fetched = 0
        def read(self, size=-1):
            data = super().read(size); self.bytes_fetched += len(data)
            return data
    result, evidence = read_zip_member(index, 'images/12.bin', reader_factory=Ranges)
    assert result == values['images/12.bin']
    assert evidence['transferred_bytes'] <= len(result) < len(payload)
    with pytest.raises(ValueError, match='budget'):
        read_zip_member(index, 'images/12.bin', max_bytes=5, reader_factory=Ranges)
    with pytest.raises(FileNotFoundError):
        read_zip_member(index, 'missing', reader_factory=Ranges)
    class Corrupt(Ranges):
        def read(self, size=-1):
            data = super().read(size)
            return data[:-1] + bytes([data[-1] ^ 0xff])
    with pytest.raises((ValueError, __import__('zlib').error)):
        read_zip_member(index, 'images/12.bin', reader_factory=Corrupt)
    with (index/'members.sqlite').open('ab') as stream: stream.write(b'tampered')
    with pytest.raises(ValueError, match='index checksum'):
        read_zip_member(index, 'images/12.bin', reader_factory=Ranges)


def test_original_route_remaps_native_zip_prefix(tmp_path, monkeypatch):
    from dataset_atlas.storage.indexed_tar import route_path, read_original_route
    index = tmp_path/'work/original-access/native'; index.mkdir(parents=True)
    (index/'receipt.json').write_text(json.dumps({'format': 'atlas-remote-zip-v1'}))
    route = route_path(tmp_path, 'fixture', 'snapshot'); route.parent.mkdir()
    route.write_text(json.dumps({'dataset_id': 'fixture', 'snapshot_id': 'snapshot',
        'archives': [{'index': 'native', 'asset_prefix': 'media/', 'member_prefix': 'Release/'}]}))
    def reader(index, member, **kwargs):
        assert member == 'Release/images/1.png'
        return b'original', {'sha256': 'test'}
    monkeypatch.setattr('dataset_atlas.storage.indexed_zip.read_zip_member', reader)
    assert read_original_route(tmp_path, 'fixture', 'snapshot', 'media/images/1.png', 100)[0] == b'original'
