#!/usr/bin/env python3
"""Query the complete index of every dataset that claims one, through a local workbench, and check the answer is what the registry says.

For each dataset with an indexed complete population the check asks for a three-record page at complete scope and requires: HTTP 200, the
response's snapshot to be the dataset's, an exact matched count equal to the registry's total, and three records that carry the dataset's
identity. A dataset whose registry total is unknown is reported, not failed. Nothing is downloaded and no media is requested.

    python scripts/verify_complete_index_smoke.py --api http://127.0.0.1:8766 --output reports/complete-index-smoke.json
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='http://127.0.0.1:8766')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    host = urlparse(args.api).hostname
    if host != 'localhost' and not (host and ipaddress.ip_address(host).is_loopback):
        raise ValueError('The smoke test requires a loopback workbench API')
    client = httpx.Client(timeout=180, headers={'X-Atlas-Request': '1'})
    datasets = client.get(args.api + '/api/v1/datasets').json()
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'api': args.api, 'datasets': {}}
    for dataset in datasets:
        coverage = dataset.get('coverage') or {}
        has_local_index=(dataset.get('availability') or {}).get('complete_data')=='local'
        if not has_local_index and (not coverage.get('preview_count') or coverage.get('complete_data') not in {'supported', 'indexed_metadata_partial_media', 'wild_subset_complete', 'full_csv_indexed', 'presented_stimuli_indexed', 'partial_media'}):
            continue
        body = {'snapshot_id': dataset['snapshot_id'], 'population_scope': 'complete', 'unit': coverage.get('unit', 'example'), 'limit': 3}
        started = time.monotonic()
        try:
            response = client.post(f"{args.api}/api/v1/queries/{dataset['id']}", json=body)
        except Exception as exc:
            report['datasets'][dataset['id']] = {'status': 'request_failed', 'error': f'{type(exc).__name__}: {str(exc)[:160]}'}
            continue
        elapsed = round(time.monotonic() - started, 3)
        if response.status_code != 200:
            report['datasets'][dataset['id']] = {'status': 'bad_response', 'http': response.status_code, 'error': response.text[:200], 'seconds': elapsed}
            continue
        result = response.json()
        problems = []
        if result.get('snapshot_id') != dataset['snapshot_id']:
            problems.append('response snapshot differs from the dataset snapshot')
        if result.get('population_scope') != 'complete':
            problems.append(f"scope is {result.get('population_scope')}")
        total = coverage.get('total_count')
        if result.get('count_status') != 'exact':
            problems.append(f"count status is {result.get('count_status')}")
        elif total is not None and result.get('matched_count') != total:
            problems.append(f"matched {result.get('matched_count')} but the registry total is {total}")
        records = result.get('records', [])
        if len(records) != min(3, result.get('matched_count') or 0):
            problems.append(f'returned {len(records)} records')
        if any(r.get('dataset_id') != dataset['id'] for r in records):
            problems.append('a record names another dataset')
        report['datasets'][dataset['id']] = {'status': 'failed' if problems else 'ok', 'matched_count': result.get('matched_count'),
                                             'registry_total': total, 'seconds': elapsed, **({'problems': problems} if problems else {})}
    summary = {}
    for value in report['datasets'].values():
        summary[value['status']] = summary.get(value['status'], 0) + 1
    report['summary'] = summary
    report['slowest_seconds'] = sorted(((v.get('seconds', 0), k) for k, v in report['datasets'].items()), reverse=True)[:5]
    report['failures'] = {k: v for k, v in report['datasets'].items() if v['status'] != 'ok'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'datasets': len(report['datasets']), 'summary': summary, 'slowest': report['slowest_seconds'], 'failed': sorted(report['failures'])}, indent=1))
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
