import copy

import pytest

from dataset_atlas.models import Artifact
from dataset_atlas.processors import run_processor


def source(pack):
    return Artifact(id='detector.fixture', kind='detect.coco_v1', snapshot_ids=['s1'], unit='example', ids=[r.id for r in pack.records],
                    provenance={'processor_provenance': {'extraction_threshold': 0.2}},
                    data={'items': [
                        {'id': 'r0', 'status': 'completed', 'output': {'assets': [{'asset_id': 'a', 'status': 'completed', 'detections': [
                            {'class': 'person', 'score': 0.7, 'box': [0, 0, 10, 10]},
                            {'class': 'cat', 'score': 0.9, 'box': [2, 2, 6, 6]}]}]}},
                        {'id': 'r1', 'status': 'completed', 'output': {'assets': [{'asset_id': 'b', 'status': 'completed', 'detections': []}]}},
                        {'id': 'r2', 'status': 'failed', 'output': None, 'error': 'fixture failure'}]})


def test_threshold_view_preserves_source_and_distinguishes_zero_failure_missing(pack):
    artifact = source(pack)
    original = copy.deepcopy(artifact.model_dump())
    result = run_processor('detect.view', pack.records, {'detector_artifact': artifact.model_dump(), 'display_threshold': 0.8})
    rows = result['items']
    assert len(rows[0]['output']['assets'][0]['detections']) == 1
    assert rows[0]['output']['derived']['detection_count_v1'] == 1
    assert rows[0]['output']['derived']['person_count_v1'] == 0
    assert rows[1]['output']['derived']['detection_count_v1'] == 0
    assert rows[2]['status'] == 'failed' and rows[2]['output'] is None
    assert rows[3]['status'] == 'not_applicable' and rows[3]['output'] is None
    assert result['provenance']['model_execution'] is False
    assert result['provenance']['source_artifact_id'] == artifact.id
    assert artifact.model_dump() == original


def test_threshold_view_keeps_partial_coverage_counts_null(pack):
    artifact = source(pack)
    artifact.data['items'][0]['output']['assets'].append({'asset_id': 'unavailable', 'status': 'failed'})
    result = run_processor('detect.view', pack.records, {'detector_artifact': artifact.model_dump(), 'display_threshold': 0.8})
    derived = result['items'][0]['output']['derived']
    assert derived['detection_count_v1'] is None and derived['person_count_v1'] is None
    assert derived['detection_coverage_complete_v1'] is False


def test_threshold_view_deduplicates_byte_identical_originals_in_counts(pack):
    artifact = source(pack)
    assets = artifact.data['items'][0]['output']['assets']
    assets[0]['file_sha256'] = 'a' * 64
    duplicate = copy.deepcopy(assets[0])
    duplicate['asset_id'] = 'duplicate-slot'
    assets.append(duplicate)
    result = run_processor('detect.view', pack.records, {'detector_artifact': artifact.model_dump(), 'display_threshold': 0.8})
    assert result['items'][0]['output']['derived']['detection_count_v1'] == 1
    assert len(result['items'][0]['output']['assets']) == 2


@pytest.mark.parametrize('change,threshold,match', [
    ({'snapshot_ids': ['wrong']}, 0.5, 'snapshot'),
    ({'unit': 'asset'}, 0.5, 'unit'),
    ({}, 0.1, 'discarded'),
    ({}, float('nan'), 'finite'),
    ({'kind': 'import.research'}, 0.5, 'detector artifact'),
])
def test_threshold_view_rejects_incompatible_or_unrecoverable_input(pack, change, threshold, match):
    artifact = source(pack).model_copy(update=change)
    with pytest.raises(ValueError, match=match):
        run_processor('detect.view', pack.records, {'detector_artifact': artifact.model_dump(), 'display_threshold': threshold})


def test_threshold_view_cannot_lower_an_existing_view_or_accept_duplicate_ids(pack):
    artifact = source(pack)
    artifact.provenance['processor_provenance']['display_threshold'] = 0.8
    with pytest.raises(ValueError, match='discarded'):
        run_processor('detect.view', pack.records, {'detector_artifact': artifact.model_dump(), 'display_threshold': 0.7})
    artifact.data['items'].append(copy.deepcopy(artifact.data['items'][0]))
    with pytest.raises(ValueError, match='unique'):
        run_processor('detect.view', pack.records, {'detector_artifact': artifact.model_dump(), 'display_threshold': 0.8})
