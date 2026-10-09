import hashlib
import io

import pytest
from PIL import Image


def test_objectnet_index_records_and_original_media_budget(pack, monkeypatch):
    from dataset_atlas.adapters.core import PreparedSource
    from dataset_atlas.adapters.objectnet import ObjectNetAdapter

    dataset = pack.dataset
    dataset.id = 'objectnet-fixture'; dataset.release = 'v1'; dataset.snapshot_id = 'fixture'
    dataset.adapter = 'objectnet'
    dataset.adapter_config = {'url': 'https://objectnet.dev/source.zip', 'bytes': 1000,
                              'etag': '"etag"', 'mapping_sha256': 'a' * 64}
    adapter = ObjectNetAdapter(dataset)
    name = 'objectnet-1.0/images/umbrella/one.png'
    monkeypatch.setattr(adapter, '_inventory', lambda: [(name, 'umbrella', 'Umbrella', 100, 123)])
    adapter._member_names = {name}
    source = PreparedSource(dataset.id, dataset.release, 100_000, 10, 'fixture')
    page = adapter.iter_records(source, limit=1)
    assert page.next_cursor is None and page.records[0].source['label'] == 'Umbrella'
    assert page.records[0].assets[0].uri == name

    image = io.BytesIO(); Image.new('RGB', (3, 3), 'red').save(image, 'PNG')
    payload = image.getvalue()

    class Reader:
        bytes_transferred = len(payload) + 10
        def __enter__(self): return self
        def __exit__(self, *_): pass

    monkeypatch.setattr(adapter, '_reader', lambda _: Reader())
    monkeypatch.setattr('dataset_atlas.adapters.objectnet.REMOTE_ZIP_MEMBERS.read',
                        lambda *_, **__: payload)
    result = adapter.resolve_asset(source, name)
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    adapter._transfer_cap = adapter.bytes_fetched
    with pytest.raises(ValueError, match='approved budget'):
        adapter.resolve_asset(source, name)
    with pytest.raises(ValueError, match='absent'):
        adapter.resolve_asset(source, 'objectnet-1.0/images/umbrella/other.png')
