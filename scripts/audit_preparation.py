#!/usr/bin/env python3
"""Report on-demand readiness for every catalogue entry without downloading data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.registry import Registry


def audit(root, download_bytes, output_bytes):
    root = Path(root).resolve()
    manager = PreparationManager(root)
    datasets = manager.registry.datasets()
    def inspect(dataset):
        entry = {'dataset_id':dataset.id, 'preview_count':dataset.coverage.preview_count,
                 'source_url':dataset.source_url, 'identity':dataset.coverage.identity}
        try:
            plan = manager.plan(dataset.id, download_bytes, output_bytes)
            entry.update(ready=plan['ready'], kind=plan.get('kind'), plan_id=plan['id'],
                         requirements=plan['requirements'], scope=plan['scope'],
                         expected_download_bytes=plan['expected_download_bytes'])
        except Exception as exc:
            entry.update(ready=False, requirements=[f'{type(exc).__name__}: {exc}'])
        print(dataset.id, 'ready' if entry['ready'] else 'requires work/access', flush=True)
        return entry
    with ThreadPoolExecutor(max_workers=4) as executor:
        rows = list(executor.map(inspect, datasets))
    return {'checked_at':datetime.now(timezone.utc).isoformat(), 'download_limit_bytes':download_bytes,
            'output_limit_bytes':output_bytes, 'dataset_count':len(rows),
            'ready_count':sum(row['ready'] for row in rows), 'datasets':rows,
            'note':'Readiness is a plan, not tested coverage. No dataset downloads were started by this audit.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--download-bytes', type=int, default=20_000_000_000)
    parser.add_argument('--output-bytes', type=int, default=2_000_000_000)
    parser.add_argument('--output', type=Path, default=Path('reports/preparation-readiness.json'))
    args = parser.parse_args()
    report = audit(args.root, args.download_bytes, args.output_bytes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
