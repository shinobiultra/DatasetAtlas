"""A retained preview video is stored under its content hash with no extension, so its media type must come from the container signature."""
import hashlib

from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.models import Asset, Record


def test_extensionless_retained_videos_are_served_with_their_container_type(workspace, pack):
    mp4 = b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2' + b'0' * 64
    webm = b'\x1aE\xdf\xa3' + b'0' * 64
    media = workspace / 'work/packs/fixture/media'
    media.mkdir()
    assets, checksums = [], {}
    for name, data in (('a' * 64, mp4), ('b' * 64, webm)):
        (media / name).write_bytes(data)
        checksums[f'media/{name}'] = hashlib.sha256(data).hexdigest()
        assets.append(Asset(id=f'video-{name[0]}', dataset_id='fixture', release_id='r1', modality='video', uri=f'media/{name}',
                            sha256=checksums[f'media/{name}']))
    pack.records = [Record(id='clips', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=assets, asset_ids=[a.id for a in assets])]
    pack.fields = []
    pack.checksums = checksums
    (workspace / 'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    with TestClient(create_app(workspace)) as client:
        exposed = client.get('/api/v1/datasets/fixture/pack').json()['records'][0]['assets']
        types = [client.get(a['uri']).headers['content-type'] for a in exposed]
    assert types == ['video/mp4', 'video/webm']
