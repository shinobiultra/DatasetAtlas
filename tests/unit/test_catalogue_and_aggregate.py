"""Catalogue thumbnails and population aggregates.

Both exist so the interface can be honest at a glance: a catalogue card shows
real media from a prepared pack, and an overview chart counts the population a
filter actually matched instead of whichever page happened to load.
"""

from fastapi.testclient import TestClient

from dataset_atlas.api.app import create_app
from dataset_atlas.catalogue import summarize_records
from dataset_atlas.models import Asset, Query, Record
from dataset_atlas.queries import aggregate_pack


def client(workspace):
    return TestClient(create_app(workspace), headers={'X-Atlas-Request': '1'})


def test_summarize_prefers_distinct_image_assets(pack):
    summary = summarize_records(pack.records)
    assert summary['modality'] == 'image'
    # Every fixture record shares one asset, so exactly one tile is offered.
    assert summary['tiles'] == [{'kind': 'image', 'uri': 'media/test.png'}]


def test_summarize_falls_back_to_text_without_media():
    records = [
        Record(id=f'r{index}', dataset_id='d', release_id='r', snapshot_id='s', question=f'Question {index}')
        for index in range(6)
    ]
    summary = summarize_records(records, limit=3)
    assert summary['modality'] == 'text'
    assert [tile['text'] for tile in summary['tiles']] == ['Question 0', 'Question 1', 'Question 2']


def test_summarize_skips_retained_raw_source_documents_when_choosing_sample_text():
    """An author-committed error page is kept faithfully as a labelled record, but must not stand in for the dataset on its catalogue card."""
    raw = Record(id='raw', dataset_id='d', release_id='r', snapshot_id='s', text='<html><title>Rate limit</title></html>',
                 source={'_atlas_source_status': 'Author-published file is not valid JSONL; raw source document retained, not an agent task.'})
    real = [Record(id=f'r{index}', dataset_id='d', release_id='r', snapshot_id='s', text=f'Task {index}') for index in range(2)]
    summary = summarize_records([raw, *real], limit=3)
    assert [tile['text'] for tile in summary['tiles']] == ['Task 0', 'Task 1']


def test_summarize_reports_no_tiles_rather_than_inventing_one():
    record = Record(id='r', dataset_id='d', release_id='r', snapshot_id='s',
                    assets=[Asset(id='a', dataset_id='d', release_id='r', modality='audio', uri='clip.wav')])
    summary = summarize_records([record])
    assert summary['tiles'] == []
    assert summary['modality'] == 'audio'


def test_thumbnails_endpoint_binds_media_handles(workspace):
    response = client(workspace).get('/api/v1/catalogue/thumbnails')
    assert response.status_code == 200
    body = response.json()
    assert body['schema_version'] == '1.0'
    tiles = body['datasets']['fixture']['tiles']
    assert len(tiles) == 1
    # Pack-local paths are never exposed; the browser gets a bound media token.
    assert tiles[0]['uri'].startswith('/api/v1/media/')


def test_thumbnails_skip_datasets_without_a_prepared_pack(workspace):
    (workspace / 'work/packs/fixture/pack.json').unlink()
    body = client(workspace).get('/api/v1/catalogue/thumbnails').json()
    assert body['datasets'] == {}


def test_aggregate_pack_counts_the_filtered_population(pack):
    query = Query(snapshot_id='s1', unit='example', population_scope='preview')
    result = aggregate_pack(pack, query, ['source.label', 'source.score'])
    assert result['denominator'] == 4
    label = next(item for item in result['results'] if item['field_id'] == 'source.label')
    assert label['kind'] == 'categorical'
    assert label['counts'] == [{'value': 'A', 'count': 2}, {'value': 'B', 'count': 1}]
    # A null label is missing, not a category of its own.
    assert label['missing'] == 1
    score = next(item for item in result['results'] if item['field_id'] == 'source.score')
    assert score['kind'] == 'numeric'
    assert (score['min'], score['max'], score['present'], score['missing']) == (1, 4, 3, 1)


def test_aggregate_respects_the_filter_and_states_its_scope(pack):
    query = Query(snapshot_id='s1', unit='example', population_scope='preview',
                  filter={'field_id': 'source.label', 'op': 'eq', 'value': 'A'})
    result = aggregate_pack(pack, query, ['source.label'])
    assert result['denominator'] == 2
    assert result['results'][0]['counts'] == [{'value': 'A', 'count': 2}]
    assert any('not a complete release' in warning for warning in result['warnings'])


def test_aggregate_never_presents_a_sample_as_prevalence(pack):
    query = Query(snapshot_id='s1', unit='example', population_scope='preview',
                  sample={'method': 'random', 'size': 2, 'seed': 0})
    result = aggregate_pack(pack, query, ['source.label'])
    assert result['sampling_applied'] is False
    assert result['denominator'] == 4
    assert any('Sampling in the browsing query was not applied' in warning for warning in result['warnings'])


def test_aggregate_rejects_an_unregistered_field(pack):
    query = Query(snapshot_id='s1', unit='example', population_scope='preview')
    try:
        aggregate_pack(pack, query, ['source.not_a_field'])
    except ValueError as error:
        assert 'Unknown aggregation field' in str(error)
    else:
        raise AssertionError('an unregistered aggregation field must be rejected')


def test_aggregate_endpoint_matches_the_query_semantics(workspace):
    response = client(workspace).post('/api/v1/aggregate/fixture', json={
        'query': {'snapshot_id': 's1', 'unit': 'example', 'population_scope': 'preview'},
        'field_ids': ['source.label'],
    })
    assert response.status_code == 200
    body = response.json()
    assert body['count_status'] == 'exact'
    assert body['population_scope'] == 'preview'
    assert body['results'][0]['counts'] == [{'value': 'A', 'count': 2}, {'value': 'B', 'count': 1}]


def test_aggregate_endpoint_rejects_a_stale_snapshot(workspace):
    response = client(workspace).post('/api/v1/aggregate/fixture', json={
        'query': {'snapshot_id': 'not-the-snapshot', 'unit': 'example', 'population_scope': 'preview'},
        'field_ids': ['source.label'],
    })
    assert response.status_code == 422


def test_thumbnails_use_active_prepared_pack_and_follow_activation(workspace):
    import json, shutil
    original = workspace / 'work/packs/fixture/pack.json'
    base = workspace / 'work/prepared/fixture'
    first = base / 'first'; (first / 'pack').mkdir(parents=True)
    document = json.loads(original.read_text())
    (first / 'pack/pack.json').write_text(json.dumps(document))
    (first / 'dataset.json').write_text(json.dumps(document['dataset']))
    (base / 'active.json').write_text(json.dumps({'version': 'first'}))
    original.unlink()
    app = client(workspace)
    response = app.get('/api/v1/catalogue/thumbnails')
    assert response.status_code == 200 and response.json()['datasets']['fixture']['tiles']
    second = base / 'second'; shutil.copytree(first, second)
    for record in document['records']:
        record['assets'] = []; record['asset_ids'] = []; record['question'] = 'New active preview'
    (second / 'pack/pack.json').write_text(json.dumps(document))
    (base / 'active.json').write_text(json.dumps({'version': 'second'}))
    tiles = app.get('/api/v1/catalogue/thumbnails').json()['datasets']['fixture']['tiles']
    assert tiles[0]['kind'] == 'text' and tiles[0]['text'] == 'New active preview'
