#!/usr/bin/env python3
"""Fetch a few preview assets of every browsable dataset through a local workbench and check that each one really decodes.

For each dataset with a prepared preview, the first, middle and last asset of the preview pack are requested through the live media route
(the same URL the browser uses, with `?representation=display` for assets flagged as needing a browser rendering). Images must decode with
Pillow and have non-zero size; audio and video must report a media content type and a non-empty body; 3D models must be non-empty.
Assets the source marks `absent_from_pinned_release` have no media request and are counted, not failed. Nothing is downloaded to disk and no
external model provider is contacted; remote originals are read exactly as the browser would read them.

    python scripts/verify_preview_media_smoke.py --api http://127.0.0.1:8766 --output reports/preview-media-smoke.json
"""
from __future__ import annotations
import argparse
import concurrent.futures as futures
import io
import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

PER_DATASET = 3


def pick(records: list[dict]) -> list[tuple[dict, dict]]:
    """First, middle and last asset-bearing record of the preview, one asset each (primary asset)."""
    bearing = [(r, r['assets'][0]) for r in records if r.get('assets')]
    if not bearing:
        return []
    indices = sorted({0, len(bearing) // 2, len(bearing) - 1})
    return [bearing[i] for i in indices][:PER_DATASET]


def check(client: httpx.Client, base: str, record: dict, asset: dict) -> dict:
    result = {'record_id': record['id'], 'asset_id': asset['id'], 'modality': asset.get('modality')}
    if asset.get('metadata', {}).get('availability') == 'absent_from_pinned_release' or not asset.get('uri'):
        return {**result, 'status': 'absent_from_release_declared'}
    uri = asset['uri']
    if asset.get('metadata', {}).get('browser_render_required') and uri.startswith('/api/v1/media/'):
        uri += ('&' if '?' in uri else '?') + 'representation=display'
    if not uri.startswith('/api/v1/media/'):
        return {**result, 'status': 'not_a_local_media_route', 'uri_scheme': urlparse(uri).scheme or 'relative'}
    try:
        response = client.get(base + uri, timeout=120)
    except Exception as exc:  # network, remote source or server failure
        return {**result, 'status': 'request_failed', 'error': f'{type(exc).__name__}: {str(exc)[:160]}'}
    content_type = response.headers.get('content-type', '')
    result.update(http=response.status_code, content_type=content_type, bytes=len(response.content),
                  representation=response.headers.get('x-atlas-media-representation'))
    if response.status_code != 200 or not response.content:
        return {**result, 'status': 'bad_response', 'error': response.text[:160] if response.status_code != 200 else 'empty body'}
    try:
        if asset.get('modality') == 'image':
            with Image.open(io.BytesIO(response.content)) as image:
                image.load()
                if image.width * image.height == 0:
                    return {**result, 'status': 'decode_failed', 'error': 'zero-size image'}
                result.update(width=image.width, height=image.height)
        elif asset.get('modality') in {'audio', 'video'} and not content_type.startswith(('audio/', 'video/')):
            return {**result, 'status': 'bad_content_type'}
    except Exception as exc:
        return {**result, 'status': 'decode_failed', 'error': f'{type(exc).__name__}: {str(exc)[:160]}'}
    return {**result, 'status': 'ok'}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='http://127.0.0.1:8766')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--only', action='append', default=[], help='check only these dataset IDs (repeatable)')
    args = parser.parse_args()
    host = urlparse(args.api).hostname
    if host != 'localhost' and not (host and ipaddress.ip_address(host).is_loopback):
        raise ValueError('The smoke test requires a loopback workbench API')
    client = httpx.Client(timeout=120)
    datasets = client.get(args.api + '/api/v1/datasets').json()
    browsable = [d for d in datasets if (d.get('coverage') or {}).get('preview_count', 0) > 0 and (not args.only or d['id'] in args.only)]
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'api': args.api, 'per_dataset': PER_DATASET,
              'scope': 'First, middle and last primary asset of each preview pack, fetched through the live media route and decoded.', 'datasets': {}}

    def one(dataset: dict) -> tuple[str, dict]:
        try:
            pack = client.get(f"{args.api}/api/v1/datasets/{dataset['id']}/pack", timeout=120).json()
        except Exception as exc:
            return dataset['id'], {'status': 'pack_unavailable', 'error': f'{type(exc).__name__}: {str(exc)[:160]}'}
        chosen = pick(pack.get('records', []))
        if not chosen:
            return dataset['id'], {'status': 'no_media_assets', 'records': len(pack.get('records', []))}
        checks = [check(client, args.api, record, asset) for record, asset in chosen]
        bad = [c for c in checks if c['status'] not in {'ok', 'absent_from_release_declared'}]
        return dataset['id'], {'status': 'failed' if bad else 'ok', 'checks': checks}

    with futures.ThreadPoolExecutor(args.workers) as pool:
        for dataset_id, result in pool.map(one, browsable):
            report['datasets'][dataset_id] = result
    summary = {}
    for result in report['datasets'].values():
        summary[result['status']] = summary.get(result['status'], 0) + 1
    report['summary'] = summary
    report['asset_checks'] = sum(len(r.get('checks', [])) for r in report['datasets'].values())
    report['failures'] = {k: [c for c in v.get('checks', []) if c['status'] not in {'ok', 'absent_from_release_declared'}] or v
                          for k, v in report['datasets'].items() if v['status'] in {'failed', 'pack_unavailable'}}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'datasets': len(browsable), 'summary': summary, 'asset_checks': report['asset_checks'], 'failed': sorted(report['failures'])}, indent=1))
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
