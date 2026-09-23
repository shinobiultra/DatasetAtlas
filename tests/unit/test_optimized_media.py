import hashlib
import io
import json

import numpy as np
import pytest
from PIL import Image, features

from dataset_atlas.storage.optimized import configure_storage, optimized_image, preparation_headroom


def native_image():
    out = io.BytesIO()
    Image.fromarray(np.random.default_rng(5).integers(0, 255, (120, 200, 3), dtype=np.uint8)).save(out, 'PNG')
    return out.getvalue()


def test_shared_cache_reuses_images_and_evicts_without_touching_original(tmp_path):
    if not features.check('avif'): pytest.skip('Optional AVIF codec unavailable')
    data = native_image(); calls = []
    def load(): calls.append(1); return data
    first = optimized_image(tmp_path, 'd', 's', 'image-1', load, cache_bytes=100_000)
    assert first[2]['original_sha256'] == hashlib.sha256(data).hexdigest()
    assert optimized_image(tmp_path, 'd', 's', 'image-1', load, cache_bytes=100_000) == first
    assert len(calls) == 1
    for i in range(2, 12): optimized_image(tmp_path, 'd', 's', f'image-{i}', load, cache_bytes=100_000)
    from dataset_atlas.storage.cache import BoundedCache
    usage = BoundedCache(tmp_path/'work/media-cache/optimized', 100_000).usage()
    assert usage['bytes'] <= 100_000 and usage['entries'] < 11
    optimized_image(tmp_path, 'd', 's', 'image-1', load, cache_bytes=100_000)
    assert len(calls) == 12


def test_preparation_admission_counts_existing_files_and_other_jobs(tmp_path):
    assert preparation_headroom(tmp_path, 100) is None
    configure_storage(tmp_path, target_bytes=100_000, ceiling_bytes=200_000, optimized_cache_bytes=20_000)
    (tmp_path/'retained').write_bytes(b'x' * 120_000)
    assert preparation_headroom(tmp_path, 50_000)['admitted']
    assert not preparation_headroom(tmp_path, 50_000, running_reservations=50_000)['admitted']
    (tmp_path/'another-source').write_bytes(b'x' * 80_000)
    assert not preparation_headroom(tmp_path, 1)['admitted']


def test_live_optimized_route_preserves_preview_and_original_model_bytes(workspace, pack):
    if not features.check('avif'): pytest.skip('Optional AVIF codec unavailable')
    from dataset_atlas.models import Asset, Record, Query, Selection
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.api import create_app
    from fastapi.testclient import TestClient
    data = native_image(); media = workspace/'work/packs/fixture/media'; media.mkdir()
    records = []
    for i in range(2):
        (media/f'{i}.png').write_bytes(data)
        asset = Asset(id=f'image-{i}', dataset_id='fixture', release_id='r1', modality='image', uri=f'media/{i}.png', sha256=hashlib.sha256(data).hexdigest())
        records.append(Record(id=f'item-{i}', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=[asset], asset_ids=[asset.id]))
    pack.records = [records[0]]; pack.fields = []
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots = workspace/'work/snapshots'; snapshots.mkdir()
    build_parquet_snapshot(records, [], snapshots/'fixture', root=snapshots, dataset_id='fixture', release_id='r1', snapshot_id='s1', expected_count=2, population_scope='complete')
    configure_storage(workspace, target_bytes=1_000_000, ceiling_bytes=2_000_000, optimized_cache_bytes=100_000)
    app = create_app(workspace)
    with TestClient(app) as client:
        preview = client.get('/api/v1/datasets/fixture/pack').json()['records'][0]['assets'][0]
        assert preview['representation'] == 'original'
        assert client.get(preview['uri']+'?representation=optimized').content == data
        response = client.post('/api/v1/queries/fixture', headers={'X-Atlas-Request':'1'}, json=Query(snapshot_id='s1', population_scope='complete').model_dump())
        assert response.status_code == 200, response.text
        asset = next(row['assets'][0] for row in response.json()['records'] if row['id'] == 'item-1')
        assert asset['representation'] == 'optimized_on_demand' and asset['sha256'] is None
        compressed = client.get(asset['uri']); assert compressed.status_code == 200, compressed.text
        assert compressed.headers['content-type'] == 'image/avif'
        assert compressed.headers['x-atlas-original-sha256'] == hashlib.sha256(data).hexdigest()
        with Image.open(io.BytesIO(compressed.content)) as im: assert im.size == (200, 120)
        assert client.get(asset['metadata']['original_uri']).content == data
        selection = Selection(id='s', ids=['item-1'], unit='example', snapshot_ids=['s1'], dataset_ids=['fixture'], created_at='now', query={'population_scope':'complete'})
        canonical = app.state.selection_records(selection, prepare_media=True)[0].assets[0]
        from pathlib import Path
        assert canonical.representation == 'original' and Path(canonical.uri).read_bytes() == data
