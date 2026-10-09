#!/usr/bin/env python3
"""Audit ObjectNet's bounded remote index and pinned original-media preview."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx
from PIL import Image

from dataset_atlas.adapters.remote_zip import PinnedHTTPRangeReader
from dataset_atlas.registry import Registry
from dataset_atlas.storage.compact import read_compact


ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8765'
SOURCE = 'https://objectnet.dev/downloads/objectnet-1.0.zip'
SIZE = 197_047_590_895
ETAG = '"2de0f39fef-59faa199a3893"'


def main():
    registry = Registry(ROOT)
    dataset = registry.dataset('objectnet')
    pack = registry.pack('objectnet')
    if dataset.coverage.total_count != 50_273 or len(pack.records) != 100:
        raise ValueError('ObjectNet index or preview population differs')
    if pack.sampling['method'] != 'sha256_bottom_k_primary_asset_verified_media':
        raise ValueError('ObjectNet preview did not verify original media')
    active = registry.active_directory('objectnet')
    receipt = json.loads((active / 'receipt.json').read_text())
    manifest = json.loads((active / 'snapshot/manifest.json').read_text())
    if manifest['record_count'] != 50_273 or receipt['record_count'] != 50_273:
        raise ValueError('ObjectNet complete snapshot count differs')
    with (active / 'snapshot/records.parquet').open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != manifest['checksums']['records.parquet']:
            raise ValueError('ObjectNet complete snapshot hash differs')
    preview_ids = {row.id for row in pack.records}
    pinned_bytes = 0
    for record in pack.records:
        asset = record.assets[0]
        original = read_compact(ROOT, dataset.id, dataset.snapshot_id, asset.uri, 50_000_000)
        if not original or original[2].get('representation') != 'original' or not original[2].get('protected_preview'):
            raise ValueError('ObjectNet preview original is not pinned')
        payload = original[0]
        if hashlib.sha256(payload).hexdigest() != asset.sha256:
            raise ValueError('ObjectNet preview asset hash differs from prepared verification')
        with Image.open(io.BytesIO(payload)) as image:
            image.verify()
        with Image.open(io.BytesIO(payload)) as image:
            rgb = image.convert('RGB')
            if (rgb.getpixel((0, 0)) != (255, 0, 0)
                    or rgb.getpixel((rgb.width - 1, rgb.height - 1)) != (255, 0, 0)):
                raise ValueError('ObjectNet source red border is absent from preview')
        pinned_bytes += len(payload)
    with httpx.Client(timeout=60) as client:
        query = client.post(BASE + '/api/v1/queries/objectnet',
            json={'population_scope': 'complete', 'snapshot_id': dataset.snapshot_id, 'limit': 10},
            headers={'X-Atlas-Request': '1'})
        query.raise_for_status()
        later = [row for row in query.json()['records'] if row['id'] not in preview_ids][:3]
        if len(later) != 3:
            raise ValueError('No later ObjectNet records available for media checks')
        with PinnedHTTPRangeReader(SOURCE, allowed_host='objectnet.dev', expected_size=SIZE,
                expected_etag=ETAG, max_transfer=150_000_000, max_requests=250) as remote:
            with zipfile.ZipFile(remote) as archive:
                infos = archive.infolist()
                if len(infos) != 50_595 or len(infos) != len(archive.NameToInfo):
                    raise ValueError('ObjectNet remote directory changed')
                folders = {info.filename.split('/')[2] for info in infos
                           if info.filename.startswith('objectnet-1.0/images/')
                           and info.filename.endswith('.png')}
                if len(folders) != 313:
                    raise ValueError('ObjectNet native class folders changed')
                for record in later:
                    member = record['source']['member']
                    info = archive.getinfo(member)
                    with archive.open(info, pwd=b'objectnetisatestset') as stream:
                        original = b''.join(iter(lambda: stream.read(1 << 20), b''))
                    uri = record['assets'][0]['uri'].split('?')[0]
                    response = client.get(BASE + uri + '?representation=original')
                    response.raise_for_status()
                    if response.content != original:
                        raise ValueError('Later live ObjectNet image differs from official ZIP')
                    with Image.open(io.BytesIO(original)) as image:
                        image.verify()
            later_remote_transfer = remote.bytes_transferred
    report = {
        'dataset_id': 'objectnet', 'snapshot_id': dataset.snapshot_id,
        'official_zip_bytes': SIZE, 'strong_etag': ETAG,
        'whole_archive_sha256_verified': False,
        'remote_directory_members': 50_595, 'complete_index_records': 50_273,
        'native_class_folders': len(folders), 'preview_records': len(pack.records),
        'original_preview_assets_pinned_and_decoded': len(pack.records),
        'original_red_borders_checked': len(pack.records),
        'preview_original_bytes_pinned': pinned_bytes,
        'later_non_preview_original_http_byte_exact_checks': len(later),
        'later_verification_remote_transfer_bytes': later_remote_transfer,
        'preparation_preview_media_validation': receipt.get('preview_media_validation'),
        'preparation_remote_metadata_bytes': receipt.get('remote_metadata_bytes'),
        'preparation_remote_zip_transfer_bytes': receipt.get('remote_zip_transfer_bytes'),
        'scope_note': 'Full native filename/class population and 100 verified original previews; availability of every non-preview media member and whole-archive SHA-256 remain unverified. Exact official original bytes stay on demand.',
        'publication_note': 'No ObjectNet image is approved for public packs. The source license prohibits model-parameter tuning and requires the original red border and attribution for posted images.',
    }
    (ROOT / 'reports/objectnet-live-verification-20260924.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
