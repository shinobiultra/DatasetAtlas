"""Faithful browser renderings of non-browser image formats: pixel fidelity, bit depth, bounds and the adapter flag."""
import io

import pytest
from PIL import Image

from dataset_atlas.storage.display import browser_render, safe_view


def tiff_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format='TIFF')
    return stream.getvalue()


def decode(png: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(png))
    image.load()
    assert image.format == 'PNG'
    return image


def test_an_rgb_tiff_renders_pixel_for_pixel_unlike_the_blurred_safe_view():
    source = Image.new('RGB', (64, 48))
    source.putdata([((x * 4) % 256, (y * 5) % 256, 255 if (x + y) % 2 else 0) for y in range(48) for x in range(64)])
    original = tiff_bytes(source)
    rendered = decode(browser_render(original))
    assert rendered.size == (64, 48) and rendered.convert('RGB').tobytes() == source.tobytes()
    blurred = decode(safe_view(original))
    assert blurred.convert('RGB').tobytes() != source.tobytes()  # the safe view is a different, deliberately lossy derivative


def test_sixteen_bit_samples_are_scaled_linearly_over_their_full_range():
    source = Image.new('I;16', (3, 1))
    source.putdata([1000, 3000, 5000])
    rendered = decode(browser_render(tiff_bytes(source)))
    assert rendered.mode == 'L' and list(rendered.tobytes()) == [0, 127, 255]


def test_a_flat_sixteen_bit_image_does_not_divide_by_zero():
    source = Image.new('I;16', (2, 2), 700)
    assert set(decode(browser_render(tiff_bytes(source))).tobytes()) == {0}


@pytest.mark.parametrize('nonfinite',[float('nan'),float('inf'),-float('inf')])
def test_nonfinite_float_tiff_fails_instead_of_erasing_finite_contrast(nonfinite):
    import numpy as np
    original=tiff_bytes(Image.fromarray(np.array([[nonfinite,10,20]],dtype='float32')))
    with pytest.raises(ValueError,match='finite pixel samples'):browser_render(original)


def test_alpha_is_kept_and_oversized_images_are_shrunk_to_the_bound():
    source = Image.new('RGBA', (300, 100), (1, 2, 3, 128))
    rendered = decode(browser_render(tiff_bytes(source), max_edge=150))
    assert rendered.mode == 'RGBA' and rendered.size == (150, 50) and rendered.getpixel((0, 0))[3] == 128


def test_palette_and_cmyk_images_become_displayable_rgb():
    palette = Image.new('P', (2, 2))
    cmyk = Image.new('CMYK', (2, 2), (0, 255, 255, 0))
    for source in (palette, cmyk):
        assert decode(browser_render(tiff_bytes(source))).mode in {'RGB', 'RGBA'}


def test_pixel_budget_and_non_images_are_refused_with_a_clear_error():
    huge = Image.new('1', (8000, 8000))
    with pytest.raises(ValueError, match='pixel budget'):
        browser_render(tiff_bytes(huge))
    with pytest.raises(Exception):
        browser_render(b'not an image')


def test_the_structured_adapter_flags_tiff_assets_for_browser_rendering_and_leaves_other_formats_alone(tmp_path):
    import json
    from dataset_atlas.adapters import get_adapter
    from dataset_atlas.models import Dataset
    path = tmp_path / 'rows.jsonl'
    path.write_text(json.dumps({'id': 'a', 'media_path': 'images/a.tif'}) + '\n' + json.dumps({'id': 'b', 'media_path': 'images/b.png'}) + '\n')
    dataset = Dataset(id='tiff-fixture', name='TIFF fixture', release='r1', snapshot_id='s1', adapter='structured',
                      adapter_config={'path': str(path), 'format': 'jsonl', 'mapping': {'id': 'id', 'media': 'media_path', 'media_modality': 'image'}})
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(5, 1_000_000))
    records = adapter.iter_records(source, None, 5).records
    tif, png = records[0].assets[0], records[1].assets[0]
    assert tif.metadata['browser_render_required'] is True and tif.metadata['source_format'] == 'TIFF'
    assert 'browser_render_required' not in png.metadata


def test_live_media_route_serves_the_original_tiff_and_a_faithful_png_rendering(workspace, pack):
    import hashlib
    from fastapi.testclient import TestClient
    from dataset_atlas.api import create_app
    from dataset_atlas.models import Asset, Record
    source = Image.new('RGB', (40, 30))
    source.putdata([((x * 6) % 256, (y * 8) % 256, (x * y) % 256) for y in range(30) for x in range(40)])
    original = tiff_bytes(source)
    media = workspace / 'work/packs/fixture/media'
    media.mkdir()
    (media / 'scene.tif').write_bytes(original)
    asset = Asset(id='tiff-1', dataset_id='fixture', release_id='r1', modality='image', uri='media/scene.tif', sha256=hashlib.sha256(original).hexdigest(),
                  metadata={'browser_render_required': True, 'source_format': 'TIFF'})
    pack.records = [Record(id='item-1', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=[asset], asset_ids=[asset.id])]
    pack.fields = []
    (workspace / 'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    with TestClient(create_app(workspace)) as client:
        exposed = client.get('/api/v1/datasets/fixture/pack').json()['records'][0]['assets'][0]
        assert exposed['metadata']['browser_render_required'] is True
        raw = client.get(exposed["uri"])
        assert raw.status_code == 200 and raw.content == original and raw.headers['content-type'] == 'image/tiff'
        shown = client.get(exposed['uri'] + '?representation=display')
        assert shown.status_code == 200 and shown.headers['content-type'] == 'image/png'
        assert shown.headers['x-atlas-media-representation'] == 'display'
        rendered = decode(shown.content)
        assert rendered.size == (40, 30) and rendered.convert('RGB').tobytes() == source.tobytes()
        assert client.get(exposed['uri']).content == original  # the original stays retrievable and unchanged


def test_display_rendering_accepts_unlabelled_bytes_but_refuses_non_images(workspace, pack):
    from fastapi.testclient import TestClient
    from dataset_atlas.api import app as app_module
    from starlette.requests import Request
    source = Image.new('RGB', (8, 6), (10, 20, 30))
    scope = {'type': 'http', 'method': 'GET', 'query_string': b'representation=display', 'headers': []}
    response = app_module.media_response(tiff_bytes(source), 'application/octet-stream', Request(scope))
    assert response.status_code == 200 and response.media_type == 'image/png'
    assert decode(response.body).convert('RGB').tobytes() == source.tobytes()
    with pytest.raises(ValueError, match='Unsupported display rendering'):
        app_module.media_response(b'RIFF....WAVE', 'audio/wav', Request(scope))
    with pytest.raises(Exception):
        app_module.media_response(b'not an image at all', 'application/octet-stream', Request(scope))


def test_a_pinned_original_served_as_a_rendering_is_labelled_as_the_rendering(workspace, pack, monkeypatch):
    """Regression: the pinned-preview path used to stamp every response 'original', even when the body was a requested PNG rendering."""
    import hashlib
    from fastapi.testclient import TestClient
    from dataset_atlas.adapters.core import MediaHandle
    from dataset_atlas.api import create_app
    from dataset_atlas.models import Asset, Record
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.storage.compact import pin_preview_originals
    source = Image.new('RGB', (30, 20))
    source.putdata([((x * 8) % 256, (y * 12) % 256, (x + y) % 256) for y in range(20) for x in range(30)])
    original = tiff_bytes(source)
    ref = 'native/scene.tif'
    asset = Asset(id='pinned-tiff', dataset_id='fixture', release_id='r1', modality='image', uri=ref, sha256=hashlib.sha256(original).hexdigest(),
                  metadata={'browser_render_required': True, 'source_format': 'TIFF'})
    row = Record(id='pinned-record', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=[asset], asset_ids=[asset.id])
    pack.records = [row]
    pack.fields = []
    (workspace / 'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots = workspace / 'work/snapshots'
    snapshots.mkdir()
    build_parquet_snapshot([row], [], snapshots / 'fixture', root=snapshots, dataset_id='fixture', release_id='r1', snapshot_id='s1',
                           expected_count=1, population_scope='complete')
    monkeypatch.setattr('dataset_atlas.adapters.resolve_dataset_asset',
                        lambda _d, reference, **_: MediaHandle(original, 'image/tiff', hashlib.sha256(original).hexdigest(), reference))
    assert pin_preview_originals(workspace, 'fixture', max_input_bytes=100_000, max_output_bytes=100_000)['preview_image_assets_pinned'] == 1
    with TestClient(create_app(workspace)) as client:
        exposed = client.get('/api/v1/datasets/fixture/pack').json()['records'][0]['assets'][0]
        raw = client.get(exposed['uri'])
        assert raw.content == original and raw.headers['x-atlas-media-representation'] == 'original'
        shown = client.get(exposed['uri'] + '?representation=display')
        assert shown.headers['content-type'] == 'image/png' and shown.headers['x-atlas-media-representation'] == 'display'
        assert decode(shown.content).convert('RGB').tobytes() == source.tobytes()
        blurred = client.get(exposed['uri'] + '?representation=safe-view')
        assert blurred.headers['x-atlas-media-representation'] == 'safe-view'


def test_a_pack_prepared_before_the_flag_existed_is_still_marked_for_browser_rendering(workspace, pack):
    import hashlib
    from fastapi.testclient import TestClient
    from dataset_atlas.api import create_app
    from dataset_atlas.models import Asset, Record
    original = tiff_bytes(Image.new('RGB', (6, 4), (1, 2, 3)))
    media = workspace / 'work/packs/fixture/media'
    media.mkdir()
    (media / 'old.tif').write_bytes(original)
    legacy = Asset(id='legacy-tiff', dataset_id='fixture', release_id='r1', modality='image', uri='media/old.tif', sha256=hashlib.sha256(original).hexdigest())
    png_like = Asset(id='plain-png', dataset_id='fixture', release_id='r1', modality='image', uri='media/plain.png')
    pack.records = [Record(id='old-record', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=[legacy, png_like], asset_ids=[legacy.id, png_like.id])]
    pack.fields = []
    (workspace / 'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    with TestClient(create_app(workspace)) as client:
        assets = client.get('/api/v1/datasets/fixture/pack').json()['records'][0]['assets']
    flagged = {a['id']: a['metadata'].get('browser_render_required') for a in assets}
    assert flagged == {'legacy-tiff': True, 'plain-png': None}
