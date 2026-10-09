import json

from fastapi.testclient import TestClient

from dataset_atlas.api import create_app


def test_publication_api_fixed_profile_and_output_with_mutation_guard(workspace):
    profile = workspace / 'registry/publication.json'
    profile.write_text(json.dumps({'schema_version': '1.0', 'datasets': {}}))
    with TestClient(create_app(workspace)) as client:
        headers = {'X-Atlas-Request': '1'}
        assert client.post('/api/v1/publication/build', json={}).status_code == 403
        result = client.post('/api/v1/publication/validate', headers=headers, json={})
        assert result.status_code == 200, result.text
        report = result.json()
        assert report['profile'] == 'public' and report['built'] is False
        assert report['remote_published'] is False and report['published_packs'] == []
        assert not (workspace / 'work/publication/data').exists()
        assert client.post('/api/v1/publication/build', headers=headers, json={}).status_code == 200
        assert (workspace / 'work/publication/data/catalogue.json').is_file()
        assert client.post('/api/v1/publication/build', headers=headers, json={'output_dir': '/tmp/other'}).status_code == 422
        assert client.post('/api/v1/publication/build', headers=headers, json={'max_bytes': 1}).status_code == 422
        profile.write_text(json.dumps({'schema_version': '1.0', 'datasets': {'fixture': {'records': True}}}))
        assert client.post('/api/v1/publication/build', headers=headers, json={}).status_code == 422
