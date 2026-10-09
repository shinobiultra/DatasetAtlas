"""The page the workbench serves must be the workbench, without a query string to remember."""
from fastapi.testclient import TestClient

from dataset_atlas.api.app import create_app

INDEX = '<!doctype html><html><head><title>Atlas</title></head><body><div id="root"></div></body></html>'


def test_served_page_announces_workbench_mode(workspace):
    (workspace / 'apps/web/dist').mkdir(parents=True)
    (workspace / 'apps/web/dist/index.html').write_text(INDEX)
    page = TestClient(create_app(workspace)).get('/')
    assert page.status_code == 200
    assert page.text.count('<meta name="atlas-mode" content="workbench" />') == 1
    assert '<title>Atlas</title>' in page.text
    assert page.headers['cache-control'] == 'no-cache'


def test_static_assets_are_still_served_beside_the_marked_page(workspace):
    (workspace / 'apps/web/dist/assets').mkdir(parents=True)
    (workspace / 'apps/web/dist/index.html').write_text(INDEX)
    (workspace / 'apps/web/dist/assets/app.js').write_text('console.log(1)')
    assert TestClient(create_app(workspace)).get('/assets/app.js').text == 'console.log(1)'


def test_missing_frontend_says_how_to_build_it(workspace, monkeypatch):
    # A tracked source checkout without a build must explain itself instead of serving a blank page.
    import dataset_atlas.api.app as app_module
    monkeypatch.setattr(app_module.Path, 'is_dir', lambda self: False if self.name in {'dist', 'web'} else True)
    body = TestClient(create_app(workspace)).get('/').json()
    assert 'npm ci' in body['message']
