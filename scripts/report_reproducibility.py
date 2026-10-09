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
import hashlib
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
    ('attempt_failed', 'A fetch from an empty workspace was attempted and failed; the stated reason is the last observed error, not a source restriction', 'Fetch attempted, failed'),
    ('larger_budget', 'Fetchable, but the source or output exceeds the per-dataset budgets used here', 'Needs a larger preparation budget'),
    ('gated', 'Source requires an account, agreement or approval; Atlas does not bypass it', 'Gated at the source'),
    ('no_recipe', 'No pinned acquisition recipe or adapter yet. For a public source this is a gap in Atlas; where availability is unverified, source research comes first', 'No acquisition path yet'),
    ('unreleased', 'The authors have not released this data; nothing can be fetched', 'Unreleased'),
    ('other', 'Another stated requirement', 'Other'),
]


def classify(plan: dict) -> str:
    if plan['ready']:
        return 'planned'
    text = ' '.join(plan.get('requirements', [])).lower()
    if 'exceeds the selected download budget' in text or 'output budget' in text:
        return 'larger_budget'
    if 'gated' in text or 'needs approval or an agreement' in text:
        return 'gated'
    if 'unreleased' in text or 'have not released' in text:
        return 'unreleased'
    if 'no pinned acquisition recipe' in text or 'no acquisition path' in text or 'adapter implementation missing' in text or 'authorized local source' in text or 'format-specific acquisition recipe' in text:
        return 'no_recipe'
    return 'other'


def plan_all(per_dataset_bytes: int, per_dataset_output_bytes: int = 1_000_000_000) -> list[dict]:
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
                plan = manager.plan(dataset_id, per_dataset_bytes, per_dataset_output_bytes, 'auto')
            except Exception as exc:  # reported, never hidden
                row.update(ready=False, requirements=[f'{type(exc).__name__}: {str(exc)[:200]}'], kind=None, download_bytes=0)
            else:
                row.update(ready=plan['ready'], requirements=plan['requirements'][:2], kind=plan.get('kind'), download_bytes=plan['expected_download_bytes'],
                           upper_bound=bool(plan.get('download_is_upper_bound')), source_bytes=plan.get('source_total_bytes'),
                           recipe_sha256=plan.get('recipe_sha256'))
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
    from dataset_atlas.storage.retention import _local_config_path
    root = workspace.resolve()
    config = (plan.get('prepared_dataset') or plan['dataset']).get('adapter_config', {})
    return any(candidate is not None and candidate.exists() and not candidate.is_relative_to(root)
               for text in strings(config) if (candidate:=_local_config_path(root,text)) is not None)


def verified(workspaces: list[Path]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    completed: dict[str, float] = {}
    for workspace in workspaces:
        for status_path in sorted((workspace / 'work/preparation').glob('*/status.json')):
            status = json.loads(status_path.read_text())
            dataset_id = status.get('dataset_id')
            if status.get('status') != 'completed' or not dataset_id:
                continue
            if not (workspace / 'work/prepared' / dataset_id / 'active.json').is_file():
                continue
            plan = json.loads((status_path.parent / 'plan.json').read_text())
            plan_id=status_path.parent.name
            if plan.get('id')!=plan_id or status.get('id')!=plan_id or plan.get('dataset_id')!=dataset_id:
                continue
            if reads_outside(plan, workspace):
                continue  # prepared from files already on someone's machine, which proves nothing about a clean clone
            version=plan_id
            receipt_path=workspace/'work/prepared'/dataset_id/version/'receipt.json'
            if not receipt_path.is_file():continue
            receipt=json.loads(receipt_path.read_text())
            if receipt.get('plan_id')!=plan_id:continue
            dataset_manifest_sha=None
            if receipt.get('dataset_id') is None:
                metadata=receipt_path.parent/'dataset.json'
                if not metadata.is_file():continue
                prepared=json.loads(metadata.read_text())
                if (prepared.get('id'),prepared.get('snapshot_id'))!=(dataset_id,receipt.get('snapshot_id')):continue
                dataset_manifest_sha=hashlib.sha256(metadata.read_bytes()).hexdigest()
            elif receipt.get('dataset_id')!=dataset_id:continue
            stamp=float(status.get('updated_at',0))
            if stamp<=completed.get(dataset_id,float('-inf')):continue
            completed[dataset_id]=stamp
            found[dataset_id] = {'downloaded_bytes': status.get('downloaded_bytes', 0), 'kind': plan.get('kind'),
                                 'recipe_sha256': plan.get('recipe_sha256'),
                                 'dataset_identity_bound_by':'immutable_dataset_manifest' if dataset_manifest_sha else 'immutable_receipt',
                                 'dataset_manifest_sha256':dataset_manifest_sha,
                                 'status_sha256': hashlib.sha256(status_path.read_bytes()).hexdigest(),
                                 'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                                 'records_indexed': receipt.get('record_count') if receipt.get('record_count') is not None else status.get('indexed_count'),
                                 'population_scope': 'preview' if plan.get('kind') == 'huggingface_remote_sample' else 'complete',
                                 'preview_count': receipt.get('preview_count', status.get('preview_count', 100)),
                                 'snapshot_id': receipt.get('snapshot_id'),
                                 'completed_at_epoch':stamp,
                                 'completed_at': datetime.fromtimestamp(status.get('updated_at', 0), timezone.utc).strftime('%Y-%m-%d')}
    return found


def failures(workspaces: list[Path]) -> dict[str, dict]:
    """Last failed preparation per dataset in the verification workspaces (a later success is handled by the caller)."""
    found: dict[str, dict] = {}
    for workspace in workspaces:
        for status_path in sorted((workspace / 'work/preparation').glob('*/status.json')):
            status = json.loads(status_path.read_text())
            if status.get('status') == 'failed' and status.get('dataset_id'):
                stamp = status.get('updated_at', 0)
                plan_path=status_path.parent/'plan.json'
                if not plan_path.is_file():continue
                plan=json.loads(plan_path.read_text())
                if plan.get('id')!=status_path.parent.name or plan.get('dataset_id')!=status['dataset_id']:continue
                if status['dataset_id'] not in found or stamp > found[status['dataset_id']]['updated_at']:
                    message=str(status.get('error','')).lower()
                    classification=('source_access_denied' if '403' in message or '401' in message else
                                    'source_not_found' if '404' in message else 'bounded_acquisition_failed')
                    found[status['dataset_id']]={'updated_at':stamp,'recipe_sha256':plan.get('recipe_sha256'),
                        'error_classification':classification,'status_sha256':hashlib.sha256(status_path.read_bytes()).hexdigest()}
    return found


def fmt_bytes(value) -> str:
    if not value:
        return '0 B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1000 or unit == 'TB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
        value /= 1000
    raise AssertionError('Byte-format unit inventory is exhausted')


def attach_verification(row: dict, proof: dict) -> None:
    """An old successful acquisition cannot certify a changed current recipe."""
    if proof.get('recipe_sha256') and proof['recipe_sha256'] == row.get('recipe_sha256'):
        row['category'], row['verification'] = 'verified', proof
    else:
        row['historical_verification'] = proof
        row['historical_verification_status'] = ('recipe_changed' if proof.get('recipe_sha256')
                                                  else 'recipe_identity_not_recorded')


def attach_failure(row: dict, failure: dict) -> None:
    row['last_failed_acquisition']=failure
    if not failure.get('recipe_sha256') or failure['recipe_sha256']!=row.get('recipe_sha256'):return
    if row['category']=='verified':
        proof=row['verification']
        stamp=proof.get('completed_at_epoch') or datetime.fromisoformat(proof.get('completed_at','1970-01-01')).replace(tzinfo=timezone.utc).timestamp()
        if failure['updated_at']<=stamp:return
        row['historical_verification']=row.pop('verification')
        row['historical_verification_status']='later_acquisition_failed'
    if row['category'] in {'planned','verified'}:
        row['category']='attempt_failed';row['requirements']=[failure['error_classification']]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verified-from', type=Path, action='append', default=[], help='Empty workspace in which previews were fetched')
    parser.add_argument('--per-dataset-bytes', type=int, default=10_000_000_000)
    parser.add_argument('--per-dataset-output-bytes', type=int, default=1_000_000_000)
    parser.add_argument('--output-prefix', type=Path, default=ROOT / 'reports/preview-reproducibility')
    args = parser.parse_args()
    rows = plan_all(args.per_dataset_bytes, args.per_dataset_output_bytes)
    evidence = verified([path.resolve() for path in args.verified_from])
    # Verification workspaces are deleted to free disk, so earlier evidence is carried over from the previous report. It keeps its own
    # date, and records the commit it was first reported at; a dataset is carried only while it is still in the catalogue.
    previous = args.output_prefix.with_suffix('.json')
    if previous.is_file():
        old = json.loads(previous.read_text())
        for entry in old.get('datasets', []):
            proof = entry.get('verification') or entry.get('historical_verification')
            if entry['dataset_id'] not in evidence and proof:
                evidence[entry['dataset_id']] = {**proof,
                    'carried_from_commit': proof.get('carried_from_commit', old.get('commit')),
                    'evidence_carry_report_date': old.get('generated_at'),
                    'evidence_carry_report_source_tree_sha256': old.get('source_tree_sha256')}
                # This identifies the report carrying the evidence, not the
                # source tree executed in a historical acquisition.
                evidence[entry['dataset_id']].pop('carried_from_source_tree_sha256',None)
                evidence[entry['dataset_id']].pop('carried_from_modified_tree',None)
    for value in evidence.values():
        if value.get('kind')=='huggingface_remote_sample':value['population_scope']='preview'
    failed = failures([path.resolve() for path in args.verified_from])
    coverage = {row['dataset_id']: row for row in csv.DictReader((ROOT / 'reports/dataset_coverage.csv').open())}
    for row in rows:
        row['maintainer_preview'] = coverage.get(row['dataset_id'], {}).get('preview', 'none') != 'none'
        if row['dataset_id'] in evidence:
            attach_verification(row, evidence[row['dataset_id']])
        if row['dataset_id'] in failed:
            attach_failure(row,failed[row['dataset_id']])
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    summary = {c: sum(r['category'] == c for r in rows) for c, _, _ in CATEGORIES}
    with_preview = [r for r in rows if r['maintainer_preview']]
    dirty = bool(subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    source_hash = hashlib.sha256()
    for directory in ('src', 'registry', 'schemas'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and path.suffix in {'.py', '.yaml', '.json'}:
                source_hash.update(str(path.relative_to(ROOT)).encode() + b'\0')
                source_hash.update(hashlib.sha256(path.read_bytes()).digest())
    document = {'generated_at': datetime.now(timezone.utc).isoformat(), 'commit': commit,
                'working_tree_dirty': dirty, 'source_tree_sha256': source_hash.hexdigest(), 'catalogue_entries': len(rows),
                'per_dataset_budget_bytes': args.per_dataset_bytes, 'per_dataset_output_budget_bytes': args.per_dataset_output_bytes,
                'summary': summary,
                'maintainer_previews': len(with_preview),
                'maintainer_previews_reproducible': sum(r['category'] in {'verified', 'planned', 'larger_budget'} for r in with_preview),
                'datasets': rows}
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix('.json').write_text(json.dumps(document, indent=1, sort_keys=True) + '\n')

    lines = ['# Preview reproducibility from an empty workspace', '',
             f"Generated {document['generated_at'][:10]} from {'the modified working tree based on' if dirty else 'commit'} `{commit}` "
             f"(source/registry/schema SHA-256 `{source_hash.hexdigest()}`). A colleague's workspace holds only the shipped catalogue; "
             'this reports what `atlas previews fetch` can obtain from each dataset\'s own publisher. Planning reads source metadata only '
             f'(per-dataset source budget {fmt_bytes(args.per_dataset_bytes)}, output budget {fmt_bytes(args.per_dataset_output_bytes)}); it downloads nothing.', '',
             f"**{summary['verified']} verified from scratch · {summary['planned']} more fetchable (not yet tried) · {summary['attempt_failed']} tried and failed · {summary['larger_budget']} need a larger budget · "
             f"{summary['gated']} gated · {summary['no_recipe']} with no acquisition path yet · {summary['unreleased']} unreleased · {summary['other']} other** of {len(rows)} catalogue entries.", '',
             f"The maintainer's workspace holds {len(with_preview)} previews; {document['maintainer_previews_reproducible']} of them can be reproduced from the "
             'catalogue alone, subject to the individual source budgets and access conditions below. A "verified" dataset was fetched in an empty workspace, produced a '
             'preview of 100 records (or all if smaller). Complete indices and sampled previews are distinguished below; '
             'a sampled preview does not prove full-population indexing. Earlier evidence retains its original date and commit, '
             'but certifies the current recipe only when its recipe checksum matches; other historical successes remain explicitly historical. '
             'The snapshot ID refers to the acquired release, whose scope can differ from the paper-used subset.', '']
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
                detail = (f"{v.get('preview_count', 100)}-record sampled preview; no complete index, "
                          if v.get('population_scope') == 'preview' else
                          f"{v['records_indexed']:,} records indexed, " if v['records_indexed'] is not None else 'index scope not recorded, ')
                detail += f"{fmt_bytes(v['downloaded_bytes'])} fetched, {v['completed_at']}"
                if v.get('carried_from_commit'):
                    detail += f" (earlier run, first reported at {v['carried_from_commit']})"
            elif category == 'planned':
                detail = f"{'up to ' if r.get('upper_bound') else ''}{fmt_bytes(r['download_bytes'])} · {r['kind']}"
            elif r.get('requirements'):
                detail = r['requirements'][0][:140]
            if r.get('historical_verification'):
                detail += f"; earlier success {r['historical_verification'].get('completed_at', 'date unknown')}, current recipe unverified"
            lines.append(f"| `{r['dataset_id']}` | {'yes' if r['maintainer_preview'] else 'no'} | {fmt_bytes(r['download_bytes'])} | {detail.replace('|', '/')} |")
        lines.append('')
    args.output_prefix.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: document[k] for k in ('catalogue_entries', 'summary', 'maintainer_previews', 'maintainer_previews_reproducible')}, indent=1))


if __name__ == '__main__':
    main()
