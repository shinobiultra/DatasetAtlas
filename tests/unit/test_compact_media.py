import hashlib
import io
import json
import sqlite3
import numpy as np
import pytest
from PIL import Image, features
from dataset_atlas.storage.compact import encode_image, compact_entry, read_compact, store_directory


def picture(mode='RGB', size=(200, 120), orientation=None):
    image = Image.fromarray(np.random.default_rng(4).integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)).convert(mode)
    out = io.BytesIO()
    if orientation:
        exif = Image.Exif(); exif[274] = orientation
        image.save(out, 'PNG', exif=exif)
    else: image.save(out, 'PNG')
    return out.getvalue()


def test_previews_are_byte_exact_and_other_images_keep_dimensions_and_orientation():
    data = picture(orientation=6)
    original, mime, metadata = encode_image(data, protected=True)
    assert original == data and mime == 'image/png' and metadata['protected_preview']
    if not features.check('avif'): pytest.skip('Optional AVIF codec unavailable')
    compact, mime, metadata = encode_image(data)
    assert mime == 'image/avif' and metadata['representation'] == 'compressed_avif'
    assert len(compact) < len(data)
    assert metadata['original_sha256'] == hashlib.sha256(data).hexdigest()
    with Image.open(io.BytesIO(compact)) as decoded:
        assert decoded.size == (200, 120)
        assert decoded.getexif()[274] == 6


def test_scientific_and_multiframe_images_stay_original():
    out = io.BytesIO(); Image.fromarray(np.arange(400, dtype=np.uint16).reshape(20, 20)).save(out, 'PNG')
    data = out.getvalue()
    assert encode_image(data)[0] == data
    assert encode_image(data)[2]['reason'] == 'unsupported_pixel_mode_preserved'
    out = io.BytesIO()
    Image.new('RGB', (30, 30), 'red').save(out, 'GIF', save_all=True, append_images=[Image.new('RGB', (30, 30), 'blue')])
    assert encode_image(out.getvalue())[2]['reason'] == 'multiframe_original'


@pytest.mark.parametrize('error', [TypeError("can't concat str to bytes"), __import__('struct').error('unsigned field out of range')])
def test_encoder_metadata_rejection_preserves_original(monkeypatch, error):
    if not features.check('avif'): pytest.skip('Optional AVIF codec unavailable')
    data = picture()
    def reject(*args, **kwargs):
        raise error
    monkeypatch.setattr(Image.Image, 'save', reject)
    payload, mime, metadata = encode_image(data)
    assert payload == data and mime == 'image/png'
    assert metadata['reason'] == 'AVIF_encoder_rejected_source_preserved'
    assert metadata['representation'] == 'original'


def test_store_checks_bytes_and_snapshot_identity(tmp_path):
    data = picture(); sha = hashlib.sha256(data).hexdigest()
    directory = store_directory(tmp_path, 'dataset', 'snapshot'); (directory/'objects').mkdir(parents=True)
    (directory/'objects'/sha).write_bytes(data)
    entry = {'sha256': sha, 'mime': 'image/png', 'representation': 'original', 'original_sha256': sha}
    with sqlite3.connect(directory/'index.sqlite') as db:
        db.execute('CREATE TABLE media (ref TEXT PRIMARY KEY, metadata TEXT)')
        db.execute('INSERT INTO media VALUES (?,?)', ('native/image.png', json.dumps(entry)))
    assert compact_entry(tmp_path, 'dataset', 'another-snapshot', 'native/image.png') is None
    assert read_compact(tmp_path, 'dataset', 'snapshot', 'native/image.png', 100000)[0] == data
    with pytest.raises(ValueError, match='budget'): read_compact(tmp_path, 'dataset', 'snapshot', 'native/image.png', 1)
    (directory/'objects'/sha).write_bytes(b'changed')
    with pytest.raises(ValueError, match='checksum'): read_compact(tmp_path, 'dataset', 'snapshot', 'native/image.png', 100000)


def test_compact_dataset_api_keeps_preview_and_analysis_originals(workspace, pack):
    if not features.check('avif'): pytest.skip('Optional AVIF codec unavailable')
    from dataset_atlas.models import Asset, Record, Query, Selection
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.storage.compact import compact_dataset
    from dataset_atlas.registry import Registry
    from dataset_atlas.api import create_app
    from fastapi.testclient import TestClient
    media = workspace/'work/packs/fixture/media'; media.mkdir()
    originals = {}
    records = []
    for i in range(5):
        data = picture(size=(200+i, 120)); ref = f'media/{i}.png'; originals[ref] = data
        (media/f'{i}.png').write_bytes(data)
        asset = Asset(id=f'image-{i}', dataset_id='fixture', release_id='r1', modality='image', uri=ref)
        records.append(Record(id=f'item-{i}', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=[asset], asset_ids=[asset.id]))
    pack.records = [records[0].model_copy(deep=True)]; pack.fields = []
    # Legacy materialized packs use a different URI for the same stable asset.
    pack.records[0].assets[0].uri = 'preview/0.png'
    previews = workspace/'work/packs/fixture/preview'; previews.mkdir()
    (previews/'0.png').write_bytes(originals['media/0.png'])
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots = workspace/'work/snapshots'; snapshots.mkdir()
    build_parquet_snapshot(records, [], snapshots/'fixture', root=snapshots, dataset_id='fixture', release_id='r1', snapshot_id='s1', expected_count=5, population_scope='complete')
    result = compact_dataset(workspace, 'fixture', max_input_bytes=1_000_000, max_output_bytes=1_000_000)
    assert result['assets'] == 5 and result['protected_preview_assets'] == 1
    assert result['compressed_assets'] == 4
    assert compact_dataset(workspace, 'fixture', max_input_bytes=1, max_output_bytes=1_000_000)['reused_assets'] == 5
    app = create_app(workspace)
    with TestClient(app) as client:
        preview = client.get('/api/v1/datasets/fixture/pack').json()['records'][0]['assets'][0]
        assert preview['representation'] == 'original'
        assert client.get(preview['uri']).content == originals['media/0.png']
        reply = client.post('/api/v1/queries/fixture', headers={'X-Atlas-Request':'1'}, json=Query(snapshot_id='s1', population_scope='complete').model_dump())
        assert reply.status_code == 200, reply.text
        asset = next(r['assets'][0] for r in reply.json()['records'] if r['id'] == 'item-1')
        assert asset['representation'] == 'compressed_avif'
        compact = client.get(asset['uri'])
        assert compact.headers['content-type'] == 'image/avif'
        assert compact.headers['x-atlas-media-representation'] == 'compressed_avif'

        original = client.get(asset['metadata']['original_uri'])
        assert original.content == originals['media/1.png']
        selection = Selection(id='s', ids=['item-1'], unit='example', snapshot_ids=['s1'], dataset_ids=['fixture'], created_at='now', query={'population_scope':'complete'})
        canonical = app.state.selection_records(selection, prepare_media=True)[0].assets[0]
        assert canonical.representation == 'original'
        from pathlib import Path
        assert Path(canonical.uri).read_bytes() == originals['media/1.png']
    # Canonical packs are never rewritten to point at a browsing derivative.
    assert Registry(workspace).pack('fixture').records[0].assets[0].uri == 'preview/0.png'

def test_pin_preview_originals_preserves_exact_bytes_without_refetch(workspace, pack, monkeypatch):
    from dataset_atlas.models import Asset, Record
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.storage.compact import pin_preview_originals, read_compact
    from dataset_atlas.adapters.core import MediaHandle

    data = picture(size=(57, 31))
    ref = 'native/source.png'
    asset = Asset(id='exact-image', dataset_id='fixture', release_id='r1', modality='image', uri=ref,
                  sha256=hashlib.sha256(data).hexdigest())
    row = Record(id='exact-record', dataset_id='fixture', release_id='r1', snapshot_id='s1',
                 assets=[asset], asset_ids=[asset.id])
    pack.records = [row]
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots = workspace/'work/snapshots'; snapshots.mkdir()
    build_parquet_snapshot([row], [], snapshots/'fixture', root=snapshots, dataset_id='fixture',
                           release_id='r1', snapshot_id='s1', expected_count=1, population_scope='complete')
    calls = []
    def remote(_dataset, reference, **_):
        calls.append(reference)
        return MediaHandle(data, 'image/png', hashlib.sha256(data).hexdigest(), reference)
    monkeypatch.setattr('dataset_atlas.adapters.resolve_dataset_asset', remote)
    report = pin_preview_originals(workspace, 'fixture', max_input_bytes=100_000, max_output_bytes=100_000)
    assert report['preview_image_assets_pinned'] == 1 and calls == [ref]
    assert read_compact(workspace, 'fixture', 's1', ref, 100_000)[0] == data
    pin_preview_originals(workspace, 'fixture', max_input_bytes=1, max_output_bytes=100_000)
    assert calls == [ref]
