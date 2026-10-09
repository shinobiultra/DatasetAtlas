#!/usr/bin/env python3
"""Independently compare the prepared radiography preview with native ZIP bytes."""
import asyncio
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATASET = 'covid-19-radiography'
BASE = 'http://127.0.0.1:8765'
ARCHIVE = ROOT / 'work/sources/covid-19-radiography/kaggle-v5.zip'


async def verify_http(items, expected):
    gate = asyncio.Semaphore(8)
    async with httpx.AsyncClient(timeout=30) as client:
        async def one(uri, role, _):
            async with gate:
                response = await client.get(BASE + uri.split('?')[0] + '?representation=original')
                response.raise_for_status()
                payload = response.content
                if hashlib.sha256(payload).hexdigest() != expected[uri]:
                    raise ValueError('Live original differs from pinned Kaggle ZIP')
                with Image.open(io.BytesIO(payload)) as image:
                    dimensions = image.size
                    image.verify()
                return len(payload), role, dimensions
        return await asyncio.gather(*(one(*item) for item in items))


def main():
    with zipfile.ZipFile(ARCHIVE) as archive, httpx.Client(timeout=30) as client:
        pack_response = client.get(BASE + f'/api/v1/datasets/{DATASET}/pack')
        pack_response.raise_for_status()
        pack = pack_response.json()
        rows = pack['records']
        if len(rows) != 100 or pack['sampling']['method'] != 'sha256_bottom_k_primary_asset':
            raise ValueError('Preview is not the expected full-population sample')
        query = client.post(BASE + f'/api/v1/queries/{DATASET}',
                            json={'population_scope': 'complete',
                                  'snapshot_id': pack['dataset']['snapshot_id'], 'limit': 1},
                            headers={'X-Atlas-Request': '1'})
        query.raise_for_status()
        later = query.json()['records'][0]
        if later['id'] in {row['id'] for row in rows}:
            raise ValueError('Later media check is inside preview')
        items = []
        for record in rows + [later]:
            for asset in record['assets']:
                role = asset['metadata']['condition']
                ref = record['source']['image_path' if role == 'radiograph' else 'mask_path']
                items.append((asset['uri'], role, ref))
        expected = {uri: hashlib.sha256(archive.read(ref)).hexdigest()
                    for uri, _, ref in items}
        native_members = [info.filename for info in archive.infolist() if not info.is_dir()]
        if len(native_members) != 42_335 or len(native_members) != len(set(native_members)):
            raise ValueError('Native archive member population changed')
        native_dimensions = Counter()
        for info in archive.infolist():
            if not info.filename.endswith('.png'):
                continue
            role = 'segmentation mask' if '/masks/' in info.filename else 'radiograph'
            if info.file_size > 10_000_000:
                raise ValueError('Native image exceeds media budget')
            with Image.open(io.BytesIO(archive.read(info))) as image:
                native_dimensions[(role, str(image.size), image.mode)] += 1
                image.verify()
        if sum(native_dimensions.values()) != 42_330:
            raise ValueError('Native image decode population changed')
    checked = asyncio.run(verify_http(items, expected))
    dimensions = Counter((role, str(size)) for _, role, size in checked)
    with ARCHIVE.open('rb') as source:
        archive_sha256 = hashlib.file_digest(source, 'sha256').hexdigest()
    report = {
        'dataset_id': DATASET,
        'kaggle_version': 5,
        'archive_sha256': archive_sha256,
        'snapshot_id': pack['dataset']['snapshot_id'],
        'native_source_rows_and_image_mask_pairs': 21_165,
        'source_archive_members': len(native_members),
        'full_native_png_decode_checks': sum(native_dimensions.values()),
        'full_native_dimensions_and_modes': {str(key): value for key, value in sorted(native_dimensions.items())},
        'preview_records': len(rows),
        'preview_assets_http_byte_exact_decode_checks': len(items) - 2,
        'later_non_preview_assets_http_byte_exact_decode_checks': 2,
        'http_bytes_verified': sum(length for length, _, _ in checked),
        'checked_dimensions_by_role': {str(key): value for key, value in sorted(dimensions.items())},
        'source_metadata_discrepancy': 'Four native tables claim 256*256 for source radiographs; sampled originals are 299x299 and paired masks 256x256. Atlas does not assert source-table SIZE as asset dimensions.',
        'rights_note': 'Local inspection only. Kaggle describes data files as copyright of original authors; medical image redistribution is not approved. Exact cited-paper subset remains unpinned.',
    }
    (ROOT / 'reports/covid-radiography-live-verification-20260924.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
