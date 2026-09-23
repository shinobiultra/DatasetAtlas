import gzip
import hashlib
import io
import os
import tarfile
import pytest
pytest.importorskip('indexed_gzip')
from dataset_atlas.storage.indexed_tar import build_tar_index, read_tar_member


def test_original_member_after_local_source_removal_uses_bounded_remote_ranges(tmp_path):
    raw = io.BytesIO()
    rng = __import__('random').Random(18)
    values = {f'images/{i}.bin': rng.randbytes(512 << 10) for i in range(24)}
    with tarfile.open(fileobj=raw, mode='w') as archive:
        for name, data in values.items():
            info = tarfile.TarInfo(name); info.size = len(data); archive.addfile(info, io.BytesIO(data))
    payload = gzip.compress(raw.getvalue(), mtime=0)
    source = tmp_path/'source.tar.gz'; source.write_bytes(payload)
    remote = {'url': 'https://example.org/source.tar.gz', 'bytes': len(payload), 'etag': '"pinned"', 'allowed_hosts': ['example.org']}
    index = tmp_path/'index'
    build_tar_index(source, index, source_sha256=hashlib.sha256(payload).hexdigest(), remote=remote, max_uncompressed_bytes=20_000_000)
    source.unlink()
    class Ranges(io.BytesIO):
        def __init__(self, url, **kwargs):
            super().__init__(payload); self.bytes_fetched = 0; self.budget = kwargs['byte_budget']
        def read(self, size=-1):
            data = super().read(size); self.bytes_fetched += len(data)
            assert self.bytes_fetched <= self.budget
            return data
        def fileno(self): raise io.UnsupportedOperation('Remote file')
    result, receipt = read_tar_member(index, 'images/22.bin', transfer_bytes=6_000_000, reader_factory=Ranges)
    assert result == values['images/22.bin']
    assert 0 < receipt['transferred_bytes'] < len(payload) / 2
    with pytest.raises(ValueError, match='budget'):
        read_tar_member(index, 'images/22.bin', max_bytes=1, reader_factory=Ranges)
    with pytest.raises(FileNotFoundError):
        read_tar_member(index, 'absent', reader_factory=Ranges)


def test_indexed_archive_preparation_avoids_full_repack(tmp_path, monkeypatch):
    import json
    import yaml
    from PIL import Image
    from dataset_atlas.models import Dataset
    from dataset_atlas.preparation import PreparationManager
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry
    from dataset_atlas.storage.sources import register_source
    from dataset_atlas.adapters import get_adapter
    original = tmp_path/'native.tar.gz'
    image = io.BytesIO(); Image.new('RGB', (31, 17), '#145688').save(image, 'PNG'); data=image.getvalue()
    with tarfile.open(original, 'w:gz') as archive:
        for i in range(3):
            info=tarfile.TarInfo(f'images/{i}.png'); info.size=len(data); archive.addfile(info,io.BytesIO(data))
    sha=hashlib.sha256(original.read_bytes()).hexdigest(); size=original.stat().st_size
    register_source(tmp_path,original,sha,size)
    datasets=tmp_path/'registry/datasets';datasets.mkdir(parents=True)
    dataset=Dataset(id='native-fixture',name='Native fixture',release='test')
    (datasets/'native.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipes=tmp_path/'registry/recipes';recipes.mkdir()
    (recipes/'native-fixture.yaml').write_text(yaml.safe_dump({'adapter':'archive','release':'native-test','expected_count':3,
        'scope':'Synthetic test archive','adapter_config':{'archive_preparation':'indexed-gzip','max_uncompressed_bytes':100000},
        'files':[{'url':'https://example.org/native.tar.gz','bytes':size,'sha256':sha,'source_name':'native.tar.gz','format':'tar.gz','config_key':'path'}],
        'allowed_hosts':['example.org']}))
    monkeypatch.setattr('dataset_atlas.storage.ranges.range_fingerprint',lambda *a,**k:'"test"')
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1000000,1000000)
    assert plan['ready'];run(tmp_path,plan['id'])
    assert manager.status(plan['id'])['status']=='completed'
    registry=Registry(tmp_path);prepared=registry.dataset(dataset.id)
    assert not list(registry.active_directory(dataset.id).rglob('*.zip'))
    assert prepared.adapter_config['original_access_index']
    adapter=get_adapter(prepared);source=adapter.prepare(adapter.plan(3,100000))
    rows=adapter.iter_records(source).records;assert len(rows)==3
    assert adapter.resolve_asset(source,rows[0].assets[0].uri).data==data
    assert original.is_file() and hashlib.sha256(original.read_bytes()).hexdigest()==sha
