"""Budgeted batch acquisition of inspectable previews for a workspace that holds none yet.

A colleague's clone has the catalogue but none of the maintainer's prepared packs. This plans every
dataset whose registry entry records a verified preview population, fetches the cheapest first
within an explicit total download budget, and writes a receipt saying what was fetched, what was
skipped and why. Planning reads source metadata only; nothing downloads without `execute`.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from dataset_atlas.preparation import PreparationManager, atomic

TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


def targets(manager, dataset_ids=None):
    """Datasets still lacking a local preview: all with an upstream preview, or exactly those named."""
    registry = manager.registry
    if dataset_ids:
        unknown = [name for name in dataset_ids if not registry.has(registry.resolve(name))]
        if unknown:
            raise KeyError(f"Unknown dataset: {', '.join(unknown)}")
        wanted = {registry.resolve(name) for name in dataset_ids}
        candidates = [d for d in registry.datasets() if d.id in wanted]
    else:
        candidates = [d for d in registry.datasets() if d.coverage.preview_count]
    return [d for d in candidates if not registry.local_state(d.id)[0]]


def plan_all(manager, datasets, per_dataset_download_bytes, per_dataset_output_bytes, log=lambda message: None):
    """One entry per dataset with the cheapest ready plan, or the reasons none is ready."""
    rows = []
    for dataset in datasets:
        entry = {'dataset_id': dataset.id, 'name': dataset.name}
        try:
            plan = manager.plan(dataset.id, per_dataset_download_bytes, per_dataset_output_bytes, 'auto')
        except (ValueError, KeyError, OSError) as exc:
            entry.update(ready=False, requirements=[f'{type(exc).__name__}: {exc}'])
        else:
            entry.update(ready=plan['ready'], plan_id=plan['id'], kind=plan.get('kind'), requirements=plan['requirements'],
                         scope=plan['scope'], expected_download_bytes=plan['expected_download_bytes'],
                         download_is_upper_bound=bool(plan.get('download_is_upper_bound')))
        log(f"planned {dataset.id}: {'ready' if entry['ready'] else 'not ready'}")
        rows.append(entry)
    return rows


def fetch_previews(root, dataset_ids=None, *, per_dataset_download_bytes=2_000_000_000, per_dataset_output_bytes=1_000_000_000,
                   total_download_bytes=20_000_000_000, execute=False, poll_seconds=2.0, log=lambda message: None, manager=None,
                   sleep=time.sleep):
    root = Path(root).resolve()
    manager = manager or PreparationManager(root)
    started = datetime.now(timezone.utc)
    report = {'started_at': started.isoformat(), 'executed': execute, 'per_dataset_download_bytes': per_dataset_download_bytes,
              'per_dataset_output_bytes': per_dataset_output_bytes, 'total_download_bytes': total_download_bytes, 'datasets': []}
    rows = plan_all(manager, targets(manager, dataset_ids), per_dataset_download_bytes, per_dataset_output_bytes, log)
    # Cheapest first, so a limited total budget buys the most datasets rather than one large one.
    rows.sort(key=lambda row: (not row['ready'], row.get('expected_download_bytes', 0), row['dataset_id']))
    spent = 0
    current = None
    try:
        for row in rows:
            if not row['ready']:
                row['outcome'] = 'skipped_not_ready'
            elif spent + row['expected_download_bytes'] > total_download_bytes:
                row['outcome'] = 'skipped_total_budget'
                row['requirements'] = [f"Would exceed the {total_download_bytes:,}-byte total download budget; raise it or fetch this dataset alone."]
            elif not execute:
                row['outcome'] = 'planned'
                spent += row['expected_download_bytes']
            else:
                current = row['plan_id']
                log(f"fetching {row['dataset_id']} (up to {row['expected_download_bytes']:,} bytes)")
                status = manager.start(current)
                while status['status'] not in TERMINAL:
                    sleep(poll_seconds)
                    status = manager.status(current)
                current = None
                row['status'] = status['status']
                if status['status'] == 'completed' and manager.registry.local_state(row['dataset_id'])[0]:
                    row['outcome'] = 'fetched'
                    row['downloaded_bytes'] = status.get('downloaded_bytes', row['expected_download_bytes'])
                    spent += row['downloaded_bytes']
                else:
                    row['outcome'] = 'failed'
                    row['error'] = status.get('error') or 'Preparation finished without a local preview'
                    spent += status.get('downloaded_bytes', 0)
            report['datasets'].append(row)
    except KeyboardInterrupt:
        # Cancelling keeps completed work and verified partial downloads for the next run.
        if current:
            manager.cancel(current)
        report['interrupted'] = True
        for index, row in enumerate(rows[len(report['datasets']):]):
            row['outcome'] = 'interrupted' if index == 0 and current else 'not_attempted'
            report['datasets'].append(row)
    counts = {}
    for row in report['datasets']:
        counts[row['outcome']] = counts.get(row['outcome'], 0) + 1
    report.update(outcomes=counts, budgeted_download_bytes=spent, finished_at=datetime.now(timezone.utc).isoformat())
    if execute:
        atomic(root / 'work/previews' / f"fetch-{started.strftime('%Y%m%dT%H%M%SZ')}.json", report)
    return report
