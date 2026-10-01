#!/usr/bin/env python3
"""Report which catalogue previews a colleague can fetch from an empty workspace, and which were verified.

Plans every catalogue entry against a throwaway workspace that holds only the shipped catalogue (metadata
requests only, nothing is downloaded), then joins:
  * the maintainer's coverage report, to show which datasets have a preview on the maintainer's machine, and
  * completed preparations found in one or more *verification workspaces* (empty workspaces in which
    `atlas previews fetch --execute` was run), as evidence that the fetch really works from scratch.

Usage: report_reproducibility.py [--verified-from WORKSPACE ...] [--output-prefix reports/preview-reproducibility]
"""
from __future__ import annotations
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = [
    ('verified', 'Fetched from an empty workspace and checked', 'Verified from scratch'),
    ('planned', 'A source plan is ready within the budget; not yet fetched from an empty workspace', 'Fetchable, not yet verified'),
    ('larger_budget', 'Fetchable, but the source is larger than the per-dataset budget used here', 'Needs a larger download budget'),
    ('gated', 'Source requires an account, agreement or approval; Atlas does not bypass it', 'Gated at the source'),
    ('no_recipe', 'No pinned acquisition recipe or adapter yet. For a public source this is a gap in Atlas; where availability is unverified, source research comes first', 'No acquisition path yet'),
    ('unreleased', 'The authors have not released this data; nothing can be fetched', 'Unreleased'),
    ('other', 'Another stated requirement', 'Other'),
]


def classify(plan: dict) -> str:
    if plan['ready']:
        return 'planned'
    text = ' '.join(plan.get('requirements', [])).lower()
    if 'exceeds the selected download budget' in text:
        return 'larger_budget'
    if 'gated' in text or 'needs approval or an agreement' in text:
        return 'gated'
    if 'unreleased' in text or 'have not released' in text:
        return 'unreleased'
    if 'no pinned acquisition recipe' in text or 'no acquisition path' in text or 'adapter implementation missing' in text or 'authorized local source' in text:
        return 'no_recipe'
    return 'other'


def plan_all(per_dataset_bytes: int) -> list[dict]:
    from dataset_atlas.preparation import PreparationManager
    workspace = Path(tempfile.mkdtemp(prefix='atlas-repro-'))
    try:
        for name in ('registry', 'schemas'):
            shutil.copytree(ROOT / name, workspace / name)
        manager = PreparationManager(workspace)
        datasets = {d.id: d for d in manager.registry.datasets()}

        def one(dataset_id: str) -> dict:
            row = {'dataset_id': dataset_id, 'name': datasets[dataset_id].name}
            try:
                plan = manager.plan(dataset_id, per_dataset_bytes, 1_000_000_000, 'auto')
            except Exception as exc:  # reported, never hidden
                row.update(ready=False, requirements=[f'{type(exc).__name__}: {str(exc)[:200]}'], kind=None, download_bytes=0)
            else:
                row.update(ready=plan['ready'], requirements=plan['requirements'][:2], kind=plan.get('kind'), download_bytes=plan['expected_download_bytes'],
                           upper_bound=bool(plan.get('download_is_upper_bound')), source_bytes=plan.get('source_total_bytes'))
            row['category'] = classify(row)
            return row
        with ThreadPoolExecutor(8) as pool:
            return sorted(pool.map(one, sorted(datasets)), key=lambda r: r['dataset_id'])
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def reads_outside(plan: dict, workspace: Path) -> bool:
    """True if the plan's adapter configuration reads an absolute path that is not inside its own workspace."""
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
    root = str(workspace.resolve())
    config = (plan.get('prepared_dataset') or plan['dataset']).get('adapter_config', {})
    return any(text.startswith('/') and not text.startswith(root) and Path(text).exists() for text in strings(config))


def verified(workspaces: list[Path]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for workspace in workspaces:
        for status_path in sorted((workspace / 'work/preparation').glob('*/status.json')):
            status = json.loads(status_path.read_text())
            dataset_id = status.get('dataset_id')
            if status.get('status') != 'completed' or not dataset_id:
                continue
            if not (workspace / 'work/prepared' / dataset_id / 'active.json').is_file():
                continue
            plan = json.loads((status_path.parent / 'plan.json').read_text())
            if reads_outside(plan, workspace):
                continue  # prepared from files already on someone's machine, which proves nothing about a clean clone
            version = json.loads((workspace / 'work/prepared' / dataset_id / 'active.json').read_text())['version']
            receipt = json.loads((workspace / 'work/prepared' / dataset_id / version / 'receipt.json').read_text())
            found[dataset_id] = {'downloaded_bytes': status.get('downloaded_bytes', 0), 'kind': plan.get('kind'),
                                 'records_indexed': receipt.get('record_count'), 'snapshot_id': receipt.get('snapshot_id'),
                                 'completed_at': datetime.fromtimestamp(status.get('updated_at', 0), timezone.utc).strftime('%Y-%m-%d')}
    return found


def fmt_bytes(value) -> str:
    if not value:
        return '0 B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1000 or unit == 'TB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
        value /= 1000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verified-from', type=Path, action='append', default=[], help='Empty workspace in which previews were fetched')
    parser.add_argument('--per-dataset-bytes', type=int, default=10_000_000_000)
    parser.add_argument('--output-prefix', type=Path, default=ROOT / 'reports/preview-reproducibility')
    args = parser.parse_args()
    rows = plan_all(args.per_dataset_bytes)
    evidence = verified([path.resolve() for path in args.verified_from])
    coverage = {row['dataset_id']: row for row in csv.DictReader((ROOT / 'reports/dataset_coverage.csv').open())}
    for row in rows:
        row['maintainer_preview'] = coverage.get(row['dataset_id'], {}).get('preview', 'none') != 'none'
        if row['dataset_id'] in evidence:
            row['category'], row['verification'] = 'verified', evidence[row['dataset_id']]
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    summary = {c: sum(r['category'] == c for r in rows) for c, _, _ in CATEGORIES}
    with_preview = [r for r in rows if r['maintainer_preview']]
    document = {'generated_at': datetime.now(timezone.utc).isoformat(), 'commit': commit, 'catalogue_entries': len(rows),
                'per_dataset_budget_bytes': args.per_dataset_bytes, 'summary': summary,
                'maintainer_previews': len(with_preview),
                'maintainer_previews_reproducible': sum(r['category'] in {'verified', 'planned', 'larger_budget'} for r in with_preview),
                'datasets': rows}
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix('.json').write_text(json.dumps(document, indent=1, sort_keys=True) + '\n')

    lines = ['# Preview reproducibility from an empty workspace', '',
             f"Generated {document['generated_at'][:10]} at commit `{commit}`. A colleague's workspace holds only the shipped catalogue; "
             'this reports what `atlas previews fetch` can obtain from each dataset\'s own publisher. Planning reads source metadata only '
             f'(per-dataset budget {fmt_bytes(args.per_dataset_bytes)}); it downloads nothing.', '',
             f"**{summary['verified']} verified from scratch · {summary['planned']} more fetchable · {summary['larger_budget']} need a larger budget · "
             f"{summary['gated']} gated · {summary['no_recipe']} with no acquisition path yet · {summary['other']} other** of {len(rows)} catalogue entries.", '',
             f"The maintainer's workspace holds {len(with_preview)} previews; {document['maintainer_previews_reproducible']} of them can be reproduced from the "
             'catalogue alone. The rest need a recipe (see below). A "verified" dataset was fetched in an empty workspace, produced a '
             "100-record preview and complete index, and (where the catalogue pins one) carries the maintainer's snapshot ID.", '']
    for category, meaning, title in CATEGORIES:
        members = [r for r in rows if r['category'] == category]
        if not members:
            continue
        lines += [f'## {title} ({len(members)})', '', meaning + '.', '']
        lines += ['| Dataset | Maintainer preview | Source size | Detail |', '| --- | --- | --- | --- |']
        for r in members:
            detail = ''
            if category == 'verified':
                v = r['verification']
                detail = f"{v['records_indexed']:,} records indexed, {fmt_bytes(v['downloaded_bytes'])} fetched, {v['completed_at']}"
            elif category == 'planned':
                detail = f"{'up to ' if r.get('upper_bound') else ''}{fmt_bytes(r['download_bytes'])} · {r['kind']}"
            elif r.get('requirements'):
                detail = r['requirements'][0][:140]
            lines.append(f"| `{r['dataset_id']}` | {'yes' if r['maintainer_preview'] else 'no'} | {fmt_bytes(r['download_bytes'])} | {detail.replace('|', '/')} |")
        lines.append('')
    args.output_prefix.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: document[k] for k in ('catalogue_entries', 'summary', 'maintainer_previews', 'maintainer_previews_reproducible')}, indent=1))


if __name__ == '__main__':
    main()
