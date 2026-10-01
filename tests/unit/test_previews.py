"""A workspace must say what it holds, and fetch previews within explicit budgets.

A fresh clone carries the catalogue but none of the maintainer's prepared packs. These tests pin
that the interface never advertises records it cannot open, and that the batch fetcher plans
before it downloads, honours its total budget, and reports failures instead of hiding them.
"""
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from dataset_atlas.api.app import create_app
from dataset_atlas.catalogue import with_availability
from dataset_atlas.models import Coverage, Dataset
from dataset_atlas.preparation import AUTO_COMPLETE_DOWNLOAD_BYTES, PreparationManager
from dataset_atlas.preparation.previews import fetch_previews, targets


def client(workspace):
    return TestClient(create_app(workspace), headers={'X-Atlas-Request': '1'})


def dataset(**coverage):
    return Dataset(id='d', name='D', coverage=Coverage(preview='complete_target', preview_count=100, complete_data='supported', **coverage))


def test_local_preview_is_reported_as_held():
    result = with_availability(dataset(), True, True)
    assert (result.availability.preview, result.availability.complete_data) == ('local', 'local')
    assert result.coverage.preview_count == 100 and result.coverage.complete_data == 'supported'


def test_upstream_only_preview_is_not_advertised_as_browsable():
    result = with_availability(dataset(), False, False)
    assert result.availability.preview == 'on_request'
    assert result.availability.upstream_preview_count == 100
    # The fields the interface keys browsability on are corrected, not merely annotated.
    assert (result.coverage.preview, result.coverage.preview_count) == ('none', 0)
    assert result.coverage.complete_data == 'requires_preparation'
    assert result.availability.complete_data == 'on_request'


def test_dataset_without_any_preview_is_not_offered_on_request():
    bare = Dataset(id='b', name='B', coverage=Coverage(complete_data='unimplemented'))
    result = with_availability(bare, False, False)
    assert (result.availability.preview, result.availability.complete_data) == ('none', 'none')


def test_api_follows_the_files_actually_present(workspace):
    http = client(workspace)
    listed = {d['id']: d for d in http.get('/api/v1/datasets').json()}['fixture']
    assert listed['availability']['preview'] == 'local' and listed['coverage']['preview_count'] == 4
    (workspace / 'work/packs/fixture/pack.json').unlink()
    listed = {d['id']: d for d in http.get('/api/v1/datasets').json()}['fixture']
    assert listed['availability']['preview'] == 'on_request' and listed['coverage']['preview_count'] == 0
    detail = http.get('/api/v1/datasets/fixture').json()
    assert detail['availability']['preview'] == 'on_request' and detail['coverage']['preview'] == 'none'
    assert http.get('/api/v1/datasets/fixture/pack').status_code == 409


def test_api_never_exposes_adapter_paths(workspace):
    body = client(workspace).get('/api/v1/datasets').json()
    assert all(entry['adapter_config'] == {} for entry in body)


@pytest.fixture
def manager(workspace):
    (workspace / 'work/packs/fixture/pack.json').unlink()
    return PreparationManager(workspace)


def stub_plan(manager, plans):
    """Replace the network-backed planner with canned plans keyed by mode."""
    def _plan(dataset_id, max_download, max_output, mode='download'):
        return plans[mode]
    manager._plan = _plan


def plan(ready, bytes_=0, **extra):
    return {'id': 'p' * 64, 'ready': ready, 'expected_download_bytes': bytes_, 'requirements': [] if ready else ['not ready'],
            'scope': 'scope', 'kind': 'k', **extra}


def test_auto_prefers_a_small_complete_download(manager):
    stub_plan(manager, {'download': plan(True, 1_000), 'sample': plan(True, 5)})
    assert manager.plan('fixture', 10**9, 10**9, 'auto')['expected_download_bytes'] == 1_000


def test_auto_samples_when_a_complete_download_is_large(manager):
    stub_plan(manager, {'download': plan(True, AUTO_COMPLETE_DOWNLOAD_BYTES + 1), 'sample': plan(True, 7)})
    assert manager.plan('fixture', 10**12, 10**9, 'auto')['expected_download_bytes'] == 7


def test_auto_reports_the_download_requirements_when_nothing_is_ready(manager):
    stub_plan(manager, {'download': plan(False), 'sample': plan(False)})
    chosen = manager.plan('fixture', 10**9, 10**9, 'auto')
    assert not chosen['ready'] and chosen['requirements'] == ['not ready']


def test_auto_falls_back_to_a_large_download_when_sampling_is_unavailable(manager):
    stub_plan(manager, {'download': plan(True, AUTO_COMPLETE_DOWNLOAD_BYTES * 4), 'sample': plan(False)})
    assert manager.plan('fixture', 10**12, 10**9, 'auto')['ready']


class StubManager:
    """Minimal PreparationManager surface: canned plans, instant jobs, no network."""
    def __init__(self, base, plans, outcomes=None):
        self.registry = base.registry
        self.plans, self.outcomes, self.started, self.cancelled = plans, outcomes or {}, [], []
    def plan(self, dataset_id, max_download, max_output, mode):
        return self.plans[dataset_id]
    def start(self, plan_id):
        self.started.append(plan_id)
        return {'status': 'queued'}
    def status(self, plan_id):
        return self.outcomes.get(plan_id, {'status': 'completed', 'downloaded_bytes': 10})
    def cancel(self, plan_id):
        self.cancelled.append(plan_id)


@pytest.fixture
def three(workspace):
    """Three catalogue datasets that claim an upstream preview and hold none locally."""
    (workspace / 'work/packs/fixture/pack.json').unlink()
    for name in ('big', 'small'):
        entry = Dataset(id=name, name=name, coverage=Coverage(preview='complete_target', preview_count=100))
        (workspace / f'registry/datasets/{name}.yaml').write_text(yaml.safe_dump(entry.model_dump()))
    return PreparationManager(workspace)


def canned(**sizes):
    return {name: {'id': name.ljust(64, '0'), 'ready': size is not None, 'expected_download_bytes': size or 0,
                   'requirements': [] if size is not None else ['No pinned recipe'], 'scope': 's', 'kind': 'k'}
            for name, size in sizes.items()}


def test_targets_are_datasets_with_an_upstream_preview_and_no_local_one(three):
    assert {d.id for d in targets(three)} == {'fixture', 'big', 'small'}
    assert [d.id for d in targets(three, ['small'])] == ['small']
    with pytest.raises(KeyError):
        targets(three, ['nonexistent'])


def test_dry_run_plans_cheapest_first_and_never_starts_a_job(three, workspace):
    stub = StubManager(three, canned(fixture=None, big=900, small=100))
    report = fetch_previews(workspace, total_download_bytes=10_000, manager=stub)
    assert [row['dataset_id'] for row in report['datasets']] == ['small', 'big', 'fixture']
    assert report['outcomes'] == {'planned': 2, 'skipped_not_ready': 1}
    assert stub.started == [] and report['executed'] is False
    assert not (workspace / 'work/previews').exists()
    unready = report['datasets'][-1]
    assert unready['requirements'] == ['No pinned recipe']


def test_total_budget_buys_the_cheapest_datasets_and_names_what_it_skipped(three, workspace):
    stub = StubManager(three, canned(fixture=300, big=900, small=100))
    report = fetch_previews(workspace, total_download_bytes=450, manager=stub)
    outcomes = {row['dataset_id']: row['outcome'] for row in report['datasets']}
    assert outcomes == {'small': 'planned', 'fixture': 'planned', 'big': 'skipped_total_budget'}
    assert report['budgeted_download_bytes'] == 400


def test_execute_runs_jobs_in_order_and_writes_a_receipt(three, workspace):
    # A completed job only counts as a fetched preview if a pack now exists.
    def finish(plan_id):
        name = plan_id.rstrip('0')
        (workspace / 'work/packs' / name).mkdir(parents=True, exist_ok=True)
        (workspace / 'work/packs' / name / 'pack.json').write_text('{}')
        return {'status': 'queued'}
    stub = StubManager(three, canned(fixture=None, big=None, small=100))
    stub.start = finish
    report = fetch_previews(workspace, total_download_bytes=10_000, execute=True, manager=stub, poll_seconds=0, sleep=lambda s: None)
    assert report['outcomes'] == {'fetched': 1, 'skipped_not_ready': 2}
    assert next(workspace.joinpath('work/previews').glob('fetch-*.json')).is_file()


def test_a_job_that_completes_without_a_pack_is_a_failure_not_a_success(three, workspace):
    stub = StubManager(three, canned(fixture=None, big=None, small=100))
    report = fetch_previews(workspace, total_download_bytes=10_000, execute=True, manager=stub, poll_seconds=0, sleep=lambda s: None)
    failed = [row for row in report['datasets'] if row['outcome'] == 'failed']
    assert [row['dataset_id'] for row in failed] == ['small']
    assert 'without a local preview' in failed[0]['error']


def test_failed_and_interrupted_jobs_are_reported_with_their_error(three, workspace):
    stub = StubManager(three, canned(fixture=None, big=None, small=100),
                       outcomes={'small'.ljust(64, '0'): {'status': 'failed', 'error': 'HTTP 503', 'downloaded_bytes': 3}})
    report = fetch_previews(workspace, execute=True, manager=stub, poll_seconds=0, sleep=lambda s: None)
    row = next(r for r in report['datasets'] if r['dataset_id'] == 'small')
    assert (row['outcome'], row['error'], row['status']) == ('failed', 'HTTP 503', 'failed')
    assert report['budgeted_download_bytes'] == 3


def test_keyboard_interrupt_cancels_the_running_job_and_keeps_the_rest_unattempted(three, workspace):
    stub = StubManager(three, canned(fixture=200, big=900, small=100))
    calls = []
    def interrupt(seconds):
        calls.append(seconds)
        raise KeyboardInterrupt
    stub.status = lambda plan_id: {'status': 'running'}
    report = fetch_previews(workspace, execute=True, manager=stub, poll_seconds=0, sleep=interrupt)
    assert report['interrupted'] is True
    assert stub.cancelled == ['small'.ljust(64, '0')]
    assert [r['outcome'] for r in report['datasets']] == ['interrupted', 'not_attempted', 'not_attempted']


# ---- snapshot identity across workspaces ---------------------------------------------------

def acquired(root, **changes):
    """A plan as two different workspaces would produce it for the same acquired bytes."""
    plan = {'id': 'f' * 64, 'kind': 'huggingface_columnar', 'revision': 'a' * 40, 'scope': 'all shards', 'expected_count': 10,
            'recipe_sha256': None, 'files': [{'source_name': 'data/a.parquet', 'sha256': '1' * 64, 'bytes': 100, 'url': f'https://x/{root}'}],
            'dataset': {'adapter_config': {'root': f'{root}/work/sources/x', 'preparation_budget_bytes': 5, 'mapping': {'text': 'q'}}}}
    plan.update(changes)
    return plan


def test_identical_data_gets_the_same_snapshot_id_in_every_workspace():
    from dataset_atlas.preparation import snapshot_for
    one = snapshot_for('ds', acquired('/home/ann/atlas'), 'plan-hash-one', '/home/ann/atlas')
    two = snapshot_for('ds', acquired('/srv/bob/ws', max_download_bytes=1), 'plan-hash-two', '/srv/bob/ws')
    assert one == two and one.startswith('ds-')


def test_different_bytes_or_scope_or_mapping_give_a_different_snapshot_id():
    from dataset_atlas.preparation import snapshot_for
    base = snapshot_for('ds', acquired('/w'), 'p', '/w')
    changed_file = acquired('/w')
    changed_file['files'][0]['sha256'] = '2' * 64
    assert snapshot_for('ds', changed_file, 'p', '/w') != base
    assert snapshot_for('ds', acquired('/w', revision='b' * 40), 'p', '/w') != base
    assert snapshot_for('ds', acquired('/w', scope='train only'), 'p', '/w') != base
    remapped = acquired('/w')
    remapped['dataset']['adapter_config']['mapping'] = {'text': 'other'}
    assert snapshot_for('ds', remapped, 'p', '/w') != base


def test_a_reviewed_recipe_snapshot_id_wins_and_local_plans_keep_their_own():
    from dataset_atlas.preparation import snapshot_for
    assert snapshot_for('ds', acquired('/w', recipe_snapshot_id='ds-reviewed'), 'p', '/w') == 'ds-reviewed'
    assert snapshot_for('ds', acquired('/w', files=[]), 'plan-hash-xyz', '/w') == 'ds-plan-hash-xyz'
