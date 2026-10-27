"""Portable sample browser checks use entirely synthetic publication output."""

import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile

import pytest


@pytest.fixture
def publication(tmp_path):
    site = tmp_path / 'site'
    (site / 'data/media').mkdir(parents=True)
    (site / 'assets').mkdir()
    (site / 'index.html').write_text('<html><head></head><body>Synthetic browser<script src="./assets/app.js"></script></body></html>')
    (site / 'assets/app.js').write_text('/* synthetic browser fixture */')
    catalogue = []
    for dataset_id in ('clevr', 'eurosat', 'pairs'):
        dataset = {'id': dataset_id, 'release': 'synthetic-release', 'snapshot_id': f'synthetic-{dataset_id}'}
        catalogue.append(dataset)
        records = []
        for index in range(100):
            media = f'data/media/{dataset_id}/{index}.png'
            original = f'synthetic original {dataset_id} {index}'.encode()
            path = site / media
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(original)
            records.append({'id': f'{dataset_id}:{index}', 'assets': [{'uri': media, 'sha256': hashlib.sha256(original).hexdigest()}]})
        pack = {'dataset': dataset, 'records': records, 'population_scope': 'preview', 'sampling': {'method': 'synthetic fixture'},
                'artifacts': [{'id': 'synthetic-result', 'ids': [row['id'] for row in records], 'data': {'fixture': True}}]}
        (site / f'data/{dataset_id}.json').write_text(json.dumps(pack))
    catalogue.append({'id': 'metadata-only'})
    (site / 'data/catalogue.json').write_text(json.dumps(catalogue))
    (site / 'data/guide.json').write_text('{}')
    notices = tmp_path / 'notices'
    notices.mkdir()
    (notices / 'dataset-NOTICE.txt').write_text('Synthetic dataset notice; no real data is used by these tests.\n')
    license_path = tmp_path / 'LICENSE'
    license_path.write_text('Synthetic code licence fixture.\n')
    return site, notices, license_path


def build(publication, output, **kwargs):
    from dataset_atlas.exports.sample_bundle import build_sample_bundle
    site, notices, license_path = publication
    return build_sample_bundle(site, output, notices_dir=notices, license_path=license_path, **kwargs)


def unpack(publication, tmp_path):
    output = tmp_path / 'sample.zip'
    build(publication, output)
    destination = tmp_path / 'unpacked'
    with zipfile.ZipFile(output) as archive:
        archive.extractall(destination)
    return destination / 'dataset-atlas-sample'


def check(bundle, *args):
    return subprocess.run([sys.executable, '-I', str(bundle / 'OPEN_ATLAS.py'), '--check', *args],
                          capture_output=True, text=True, cwd=bundle.parent, timeout=20)


def test_bundle_keeps_originals_complete_previews_and_artifacts(publication, tmp_path):
    output = tmp_path / 'sample.zip'
    receipt = build(publication, output)
    assert receipt['dataset_count'] == 3 and receipt['record_count'] == 300
    assert receipt['media_files'] == 300 and receipt['catalogue_count'] == 4
    assert receipt['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read('dataset-atlas-sample/manifest.json'))
        assert manifest['population_scope'] == 'preview'
        assert {row['id'] for row in manifest['datasets']} == {'clevr', 'eurosat', 'pairs'}
        assert {row['record_count'] for row in manifest['datasets']} == {100}
        assert set(manifest['files']) | {'manifest.json'} == {name.removeprefix('dataset-atlas-sample/') for name in archive.namelist()}
        for name, info in manifest['files'].items():
            content = archive.read('dataset-atlas-sample/' + name)
            assert len(content) == info['bytes']
            assert hashlib.sha256(content).hexdigest() == info['sha256']
        for original in publication[0].rglob('*'):
            if original.is_file():
                assert archive.read('dataset-atlas-sample/site/' + original.relative_to(publication[0]).as_posix()) == original.read_bytes()
        assert archive.read('dataset-atlas-sample/licenses/dataset-NOTICE.txt') == (publication[1] / 'dataset-NOTICE.txt').read_bytes()
        assert archive.read('dataset-atlas-sample/LICENSE') == publication[2].read_bytes()


def test_bundle_is_deterministic_and_never_overwrites(publication, tmp_path):
    first, second = tmp_path / 'first.zip', tmp_path / 'second.zip'
    build(publication, first)
    for path in publication[0].rglob('*'):
        os.utime(path, (1_700_000_000, 1_700_000_000))
    build(publication, second)
    assert first.read_bytes() == second.read_bytes()
    with pytest.raises(ValueError, match='exist'):
        build(publication, first)


@pytest.mark.parametrize('where', ['site', 'notice', 'license', 'nested-directory', 'media'])
def test_bundle_refuses_symlink_inputs(publication, tmp_path, where):
    site, notices, license_path = publication
    if where in {'site', 'notice', 'license'}:
        index = {'site': 0, 'notice': 1, 'license': 2}[where]
        target = publication[index]
        linked = tmp_path / ('linked-' + target.name)
        linked.symlink_to(target, target_is_directory=target.is_dir())
        publication = tuple(linked if i == index else item for i, item in enumerate(publication))
    elif where == 'nested-directory':
        (site / 'extra').symlink_to(notices, target_is_directory=True)
    else:
        original = site / 'data/media/clevr/0.png'
        original.unlink()
        original.symlink_to(license_path)
    with pytest.raises(ValueError, match='[Ll]ink|symlink'):
        build(publication, tmp_path / 'sample.zip')


@pytest.mark.parametrize('name', ['private.sqlite', '.env', 'work/secret.json', 'media\\escape.png'])
def test_bundle_refuses_private_or_unsafe_site_members(publication, tmp_path, name):
    target = publication[0] / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('synthetic private fixture')
    with pytest.raises(ValueError, match='[Uu]nsafe|[Ff]orbidden|[Pp]rivate'):
        build(publication, tmp_path / 'sample.zip')


def test_bundle_enforces_expanded_budget_without_leaving_output(publication, tmp_path):
    output = tmp_path / 'sample.zip'
    with pytest.raises(ValueError, match='[Bb]udget|[Ll]imit|[Ee]xceed'):
        build(publication, output, max_bytes=100)
    assert not output.exists()


def test_bundle_rejects_an_output_link_without_touching_its_target(publication, tmp_path):
    target = tmp_path / 'retained.zip'
    target.write_bytes(b'retain this file')
    output = tmp_path / 'sample.zip'
    output.symlink_to(target)
    with pytest.raises(ValueError):
        build(publication, output)
    assert target.read_bytes() == b'retain this file'


@pytest.mark.parametrize('mutation', ['missing-pack', 'extra-pack', 'short-preview', 'missing-media', 'changed-media', 'remote-media'])
def test_bundle_refuses_incomplete_or_expanded_sample_scope(publication, tmp_path, mutation):
    site = publication[0]
    pack_path = site / 'data/clevr.json'
    pack = json.loads(pack_path.read_text())
    if mutation == 'missing-pack':
        pack_path.unlink()
    elif mutation == 'extra-pack':
        (site / 'data/unapproved.json').write_text(json.dumps(pack))
    elif mutation == 'short-preview':
        pack['records'].pop()
        pack_path.write_text(json.dumps(pack))
    elif mutation == 'missing-media':
        (site / 'data/media/clevr/0.png').unlink()
    elif mutation == 'changed-media':
        (site / 'data/media/clevr/0.png').write_bytes(b'changed synthetic original')
    else:
        pack['records'][0]['assets'][0]['uri'] = 'https://example.invalid/image.png'
        pack_path.write_text(json.dumps(pack))
    with pytest.raises(ValueError):
        build(publication, tmp_path / 'sample.zip')


def test_dependency_free_launcher_checks_then_detects_tampering(publication, tmp_path):
    bundle = unpack(publication, tmp_path)
    checked = check(bundle)
    assert checked.returncode == 0, checked.stderr
    assert '300' in checked.stdout
    (bundle / 'site/data/media/clevr/0.png').write_bytes(b'tampered')
    assert check(bundle).returncode != 0


@pytest.mark.parametrize('mutation', ['extra', 'empty-extra', 'missing', 'symlink', 'traversal'])
def test_launcher_refuses_unknown_missing_linked_or_escaping_files(publication, tmp_path, mutation):
    bundle = unpack(publication, tmp_path)
    if mutation == 'extra':
        (bundle / 'unexpected.txt').write_text('unexpected')
    elif mutation == 'empty-extra':
        (bundle / 'unexpected').mkdir()
    elif mutation == 'missing':
        (bundle / 'LICENSE').unlink()
    elif mutation == 'symlink':
        target = bundle / 'LICENSE'
        target.unlink()
        target.symlink_to(publication[2])
    else:
        manifest_path = bundle / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files']['../escape.txt'] = {'bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}
        manifest_path.write_text(json.dumps(manifest))
    assert check(bundle).returncode != 0


def test_launcher_allows_only_conventional_python_cache_extras(publication, tmp_path):
    bundle = unpack(publication, tmp_path)
    cache = bundle / '__pycache__'
    cache.mkdir()
    (cache / 'OPEN_ATLAS.cpython-312.pyc').write_bytes(b'synthetic cache')
    assert check(bundle).returncode == 0
    (cache / 'private.txt').write_text('not Python bytecode')
    assert check(bundle).returncode != 0


@pytest.mark.parametrize('local_build', [False, True])
def test_launcher_serves_only_static_site_from_loopback(publication, tmp_path, local_build):
    bundle = unpack(publication, tmp_path)
    command = [sys.executable, '-I', str(bundle / 'OPEN_ATLAS.py'), '--no-browser', '--port', '0']
    if local_build:
        command += ['--site', str(publication[0])]
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=bundle.parent)
    try:
        assert process.stdout is not None and process.stderr is not None
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            assert ready.select(timeout=15), 'launcher did not announce its loopback address'
        line = process.stdout.readline().strip()
        assert 'http://127.0.0.1:' in line, process.stderr.read() if process.poll() is not None else line
        url = line[line.index('http://'):]
        with urllib.request.urlopen(url, timeout=5) as response:
            assert b'Synthetic browser' in response.read()
        with urllib.request.urlopen(url + 'data/media/clevr/0.png', timeout=5) as response:
            assert response.read() == b'synthetic original clevr 0'
        port = urlsplit(url).port
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Host': f'localhost:{port}'}), timeout=5) as response:
            assert response.status == 200
        for host in ('attacker.invalid', 'localhost', f'127.0.0.1:{port}.attacker.invalid', '127.0.0.1:1'):
            for method in ('GET', 'HEAD'):
                request = urllib.request.Request(url, headers={'Host': host}, method=method)
                with pytest.raises(urllib.error.HTTPError) as refused:
                    urllib.request.urlopen(request, timeout=5)
                assert refused.value.code in {400, 403}
        with pytest.raises(urllib.error.HTTPError) as rejected:
            urllib.request.urlopen(url + '../LICENSE', timeout=5)
        assert rejected.value.code in {403, 404}
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_local_launcher_requires_explicit_site_without_bundle_manifest(tmp_path):
    from dataset_atlas.sample_launcher import main
    site = tmp_path / 'site'
    site.mkdir()
    (site / 'index.html').write_text('synthetic site')
    # Checking is a bundle operation: a plain local build cannot masquerade as an attested bundle.
    assert main(['--site', str(site), '--check']) != 0


def test_default_serve_and_cli_reuse_one_origin_without_claiming_port_8767(tmp_path, monkeypatch, capsys):
    from dataset_atlas import sample_launcher
    site = tmp_path / 'site'
    site.mkdir()
    (site / 'index.html').write_text('synthetic site')

    class ServerWithoutSocket:
        def __init__(self, address, handler):
            # Model OS assignment for explicit port 0 while leaving the real
            # default port untouched, so parallel test runs cannot fight over it.
            self.server_address = (address[0], address[1] or 49152)
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            pass
        def serve_forever(self):
            pass

    monkeypatch.setattr(sample_launcher, 'ThreadingHTTPServer', ServerWithoutSocket)
    sample_launcher.serve(site, open_browser=False)
    assert sample_launcher.main(['--site', str(site), '--no-browser']) == 0
    assert capsys.readouterr().out.splitlines() == [
        'Dataset Atlas sample: http://127.0.0.1:8767/',
        'Dataset Atlas sample: http://127.0.0.1:8767/',
    ]
    assert sample_launcher.main(['--site', str(site), '--port', '0', '--no-browser']) == 0
    assert 'http://127.0.0.1:49152/' in capsys.readouterr().out
