"""A prepared version fixes what preparation determined; the registry keeps the rest."""
import json
import yaml
from dataset_atlas.models import Dataset
from dataset_atlas.registry import Registry, merge_prepared


def _activate(workspace, registry, **overrides):
    baseline = registry.dataset('fixture')
    prepared = baseline.model_copy(deep=True)
    prepared.release = 'prepared-release'
    prepared.snapshot_id = 'prepared-snapshot'
    prepared.adapter = 'columnar'
    prepared.adapter_config = {'files': []}
    prepared.coverage.preview_count = 100
    prepared.coverage.total_count = 5640
    prepared.coverage.complete_data = 'supported'
    prepared.evidence = list(prepared.evidence) + [{'kind': 'local_preparation', 'snapshot_id': 'prepared-snapshot'}]
    for key, value in overrides.items():
        setattr(prepared, key, value)
    version = workspace / 'work/prepared/fixture/v1'
    version.mkdir(parents=True, exist_ok=True)
    (version / 'dataset.json').write_text(prepared.model_dump_json())
    (version.parent / 'active.json').write_text(json.dumps({'version': 'v1'}))
    return prepared


def test_registry_edits_stay_visible_while_a_version_is_active(workspace):
    registry = Registry(workspace)
    _activate(workspace, registry)
    path = workspace / 'registry/datasets/fixture.yaml'
    document = yaml.safe_load(path.read_text())
    document['aliases'] = ['Fixture (alias)']
    document['paper_ids'] = ['paper-new']
    document['rights'] = {'records': 'reviewed'}
    document['evidence'] = [{'kind': 'source_audit_rights', 'note': 'reviewed after preparation'}]
    path.write_text(yaml.safe_dump(document))
    registry.refresh()
    merged = registry.dataset('fixture')
    # Preparation-owned facts come from the prepared copy.
    assert merged.release == 'prepared-release' and merged.snapshot_id == 'prepared-snapshot'
    assert merged.adapter == 'columnar' and merged.coverage.total_count == 5640
    # Registry-owned facts come from the current YAML, not the plan-time freeze.
    assert merged.aliases == ['Fixture (alias)'] and merged.paper_ids == ['paper-new']
    assert merged.rights == {'records': 'reviewed'}
    kinds = [item.get('kind') for item in merged.evidence]
    assert kinds == ['source_audit_rights', 'local_preparation']


def test_recipe_overrides_of_description_follow_the_prepared_copy(workspace):
    registry = Registry(workspace)
    _activate(workspace, registry, description='Official population as named by the recipe')
    assert registry.dataset('fixture').description == ''  # no recipe: the baseline's (empty) description wins
    (workspace / 'registry/recipes').mkdir(exist_ok=True)
    (workspace / 'registry/recipes/fixture.yaml').write_text('description: Official population as named by the recipe\n')
    registry.refresh()
    registry._active_datasets.clear()
    assert registry.dataset('fixture').description == 'Official population as named by the recipe'


def test_merge_prepared_is_pure():
    baseline = Dataset(id='d', name='Base', aliases=['B'], release='r0', snapshot_id='s0', paper_ids=['p'])
    prepared = Dataset(id='d', name='Renamed by nobody', release='r1', snapshot_id='s1', coverage={'preview_count': 7})
    merged = merge_prepared(baseline, prepared, recipe_present=False)
    assert (merged.name, merged.aliases, merged.paper_ids) == ('Base', ['B'], ['p'])
    assert (merged.release, merged.snapshot_id, merged.coverage.preview_count) == ('r1', 's1', 7)
    assert baseline.release == 'r0' and prepared.name == 'Renamed by nobody'


def test_source_and_access_review_are_not_frozen_by_preparation():
    baseline=Dataset(id='d',name='Base',coverage={'identity':'resolved','source':'verified','access':'public','publication':'restricted'})
    prepared=Dataset(id='d',name='Base',coverage={'identity':'candidate','source':'unverified','access':'unverified','publication':'not_reviewed','preview_count':100,'total_count':150,'adapter':'tested'})
    merged=merge_prepared(baseline,prepared,recipe_present=True)
    assert (merged.coverage.identity,merged.coverage.source,merged.coverage.access,merged.coverage.publication)==('resolved','verified','public','restricted')
    assert (merged.coverage.preview_count,merged.coverage.total_count,merged.coverage.adapter)==(100,150,'tested')
