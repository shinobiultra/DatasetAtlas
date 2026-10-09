"""A historical acquisition must not certify a different preparation recipe."""
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('atlas_reproducibility_report',Path(__file__).parents[2]/'scripts/report_reproducibility.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_matching_recipe_accepts_actual_verification():
    row={'category':'planned','recipe_sha256':'same'};proof={'recipe_sha256':'same','population_scope':'preview'}
    module.attach_verification(row,proof)
    assert row['category']=='verified' and row['verification']==proof


def test_changed_recipe_preserves_only_historical_success():
    row={'category':'planned','recipe_sha256':'new'};proof={'recipe_sha256':'old','records_indexed':100}
    module.attach_verification(row,proof)
    assert row['category']=='planned' and row['historical_verification']==proof
    assert row['historical_verification_status']=='recipe_changed' and 'verification' not in row


def test_missing_recipe_identity_cannot_certify_current_recipe():
    row={'category':'planned','recipe_sha256':'new'}
    module.attach_verification(row,{'records_indexed':100})
    assert row['category']=='planned' and row['historical_verification_status']=='recipe_identity_not_recorded'


def test_output_budget_requirement_is_preparation_budget_limit():
    assert module.classify({'ready':False,'requirements':['Prepared index exceeds selected output budget']})=='larger_budget'


def acquisition(workspace,identity,stamp,recipe,receipt_plan=None):
    status_dir=workspace/'work/preparation'/identity;status_dir.mkdir(parents=True)
    (status_dir/'status.json').write_text(json.dumps({'id':identity,'dataset_id':'fixture','status':'completed','updated_at':stamp}))
    (status_dir/'plan.json').write_text(json.dumps({'id':identity,'dataset_id':'fixture','recipe_sha256':recipe,'kind':'original_files','dataset':{'adapter_config':{}}}))
    version=workspace/'work/prepared/fixture'/identity;version.mkdir(parents=True)
    (version/'receipt.json').write_text(json.dumps({'plan_id':receipt_plan or identity,'dataset_id':'fixture','record_count':99,'snapshot_id':identity+'-snapshot'}))
    (version.parent/'active.json').write_text(json.dumps({'version':identity}))


def test_proofs_use_exact_immutable_receipt_and_latest_timestamp(tmp_path):
    acquisition(tmp_path,'z-old',10,'old')
    acquisition(tmp_path,'a-new',20,'new')
    proof=module.verified([tmp_path])['fixture']
    assert proof['recipe_sha256']=='new' and proof['snapshot_id']=='a-new-snapshot'


def test_mismatched_receipt_plan_cannot_certify_acquisition(tmp_path):
    acquisition(tmp_path,'old',10,'old',receipt_plan='another-plan')
    assert module.verified([tmp_path])=={}


def test_legacy_receipt_requires_matching_immutable_dataset_manifest(tmp_path):
    acquisition(tmp_path,'current',10,'recipe')
    version=tmp_path/'work/prepared/fixture/current';path=version/'receipt.json'
    receipt=json.loads(path.read_text());receipt.pop('dataset_id');path.write_text(json.dumps(receipt))
    assert module.verified([tmp_path])=={}
    metadata=version/'dataset.json';metadata.write_text(json.dumps({'id':'fixture','snapshot_id':'current-snapshot'}))
    proof=module.verified([tmp_path])['fixture']
    assert proof['dataset_identity_bound_by']=='immutable_dataset_manifest' and proof['dataset_manifest_sha256']
    metadata.write_text(json.dumps({'id':'another','snapshot_id':'current-snapshot'}))
    assert module.verified([tmp_path])=={}


def test_sibling_prefix_and_relative_symlink_are_outside_workspace(tmp_path):
    workspace=tmp_path/'clean';workspace.mkdir()
    foreign=tmp_path/'clean-foreign';foreign.mkdir();source=foreign/'source.jsonl';source.write_text('{}\n')
    assert module.reads_outside({'dataset':{'adapter_config':{'path':str(source)}}},workspace)
    assert module.reads_outside({'dataset':{'adapter_config':{'path':'../clean-foreign/source.jsonl'}}},workspace)
    (workspace/'source.jsonl').symlink_to(source)
    assert module.reads_outside({'dataset':{'adapter_config':{'path':'source.jsonl'}}},workspace)
    own=workspace/'own.jsonl';own.write_text('{}\n')
    assert not module.reads_outside({'dataset':{'adapter_config':{'path':'own.jsonl'}}},workspace)


def test_current_failed_attempt_survives_older_recipe_success():
    row={'category':'planned','recipe_sha256':'current'}
    module.attach_verification(row,{'recipe_sha256':'old','completed_at_epoch':10})
    module.attach_failure(row,{'recipe_sha256':'current','updated_at':20,'error_classification':'bounded_acquisition_failed'})
    assert row['category']=='attempt_failed' and row['historical_verification']['recipe_sha256']=='old'
    assert row['last_failed_acquisition']['updated_at']==20


def test_later_success_remains_verified_with_earlier_failure_retained():
    row={'category':'planned','recipe_sha256':'current'}
    module.attach_verification(row,{'recipe_sha256':'current','completed_at_epoch':20})
    module.attach_failure(row,{'recipe_sha256':'current','updated_at':10,'error_classification':'source_access_denied'})
    assert row['category']=='verified' and row['last_failed_acquisition']['updated_at']==10


def test_new_failure_retains_success_as_historical():
    row={'category':'planned','recipe_sha256':'current'}
    module.attach_verification(row,{'recipe_sha256':'current','completed_at_epoch':10})
    module.attach_failure(row,{'recipe_sha256':'current','updated_at':20,'error_classification':'source_access_denied'})
    assert row['category']=='attempt_failed' and 'verification' not in row and row['historical_verification']
