"""Pinned analysis weights install only after verification, never overwrite a researcher's settings, and refuse surprises."""
import hashlib
import json
import sys
import types
from pathlib import Path

import pytest
import yaml

from dataset_atlas import models_install
from dataset_atlas.cli import main


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def lab(tmp_path):
    """A workspace whose catalogue lists two small models: a Hugging Face-style folder and a packaged file."""
    root = tmp_path / 'lab'
    (root / 'registry/models').mkdir(parents=True)
    weights, config = b'weights' * 1000, b'{"hidden": 4}'
    (root / 'registry/models/tiny.yaml').write_text(yaml.safe_dump({'id': 'org/tiny', 'install': {
        'dir': 'work/models/tiny', 'files': [
            {'path': 'model.safetensors', 'url': 'https://huggingface.co/org/tiny/resolve/abc/model.safetensors', 'bytes': len(weights), 'sha256': sha(weights)},
            {'path': 'sub/config.json', 'url': 'https://huggingface.co/org/tiny/resolve/abc/sub/config.json', 'bytes': len(config), 'sha256': sha(config)}],
        'processors': {'embed.tiny': {'model_path': '{dir}', 'model_sha256': sha(weights), 'representation': 'text'}}}}))
    packaged = b'onnx-bytes' * 50
    (root / 'registry/models/pkg.yaml').write_text(yaml.safe_dump({'id': 'pkg', 'install': {
        'kind': 'package', 'package': 'fakepkg', 'resource': 'model.onnx', 'dir': 'work/models', 'path': 'pkg.onnx', 'bytes': len(packaged), 'sha256': sha(packaged),
        'processors': {'detect.pkg': {'model_path': '{file}', 'model_sha256': sha(packaged)}}}}))
    (root / 'registry/datasets').mkdir(parents=True)
    return root, {'weights': weights, 'config': config, 'packaged': packaged}


def fake_network(monkeypatch, tmp_path, blobs: dict, corrupt: str | None = None):
    served = []
    def fetch(self, url, cache, identity, expected_sha256=None, byte_budget=None, **kwargs):
        served.append(url)
        name = url.rsplit('/', 1)[1]
        data = {'model.safetensors': blobs['weights'], 'config.json': blobs['config']}[name]
        if corrupt == name:
            data = data[::-1]
        path = tmp_path / 'served' / f'{len(served)}-{name}'
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return path
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch', fetch)
    return served


def fake_package(monkeypatch, tmp_path, data: bytes):
    package = tmp_path / 'fakepkg'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'model.onnx').write_bytes(data)
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop('fakepkg', None)


def test_a_dry_run_reports_sizes_and_changes_nothing(lab, monkeypatch, tmp_path):
    root, blobs = lab
    served = fake_network(monkeypatch, tmp_path, blobs)
    report = models_install.install(root)
    assert report['executed'] is False and report['download_bytes'] == len(blobs['weights']) + len(blobs['config'])
    assert served == [] and not (root / 'work/models').exists() and not (root / 'local-config/recipes.json').exists()


def test_install_verifies_places_files_and_configures_processors_with_absolute_paths(lab, monkeypatch, tmp_path):
    root, blobs = lab
    fake_network(monkeypatch, tmp_path, blobs)
    fake_package(monkeypatch, tmp_path, blobs['packaged'])
    report = models_install.install(root, execute=True)
    assert all(m['installed'] for m in report['models'])
    assert (root / 'work/models/tiny/model.safetensors').read_bytes() == blobs['weights']
    assert (root / 'work/models/tiny/sub/config.json').read_bytes() == blobs['config']
    assert (root / 'work/models/pkg.onnx').read_bytes() == blobs['packaged']
    saved = json.loads((root / 'local-config/recipes.json').read_text())
    assert saved['embed.tiny']['model_path'] == str((root / 'work/models/tiny').resolve())
    assert saved['detect.pkg']['model_path'] == str((root / 'work/models/pkg.onnx').resolve()) and saved['embed.tiny']['representation'] == 'text'
    assert all(row['installed'] and row['configured'] for row in models_install.status(root, verify=True))


def test_a_second_run_downloads_nothing_and_keeps_a_researchers_own_settings(lab, monkeypatch, tmp_path):
    root, blobs = lab
    served = fake_network(monkeypatch, tmp_path, blobs)
    fake_package(monkeypatch, tmp_path, blobs['packaged'])
    models_install.install(root, execute=True)
    recipes = root / 'local-config/recipes.json'
    saved = json.loads(recipes.read_text())
    saved['embed.tiny']['representation'] = 'question'  # the researcher's own choice
    recipes.write_text(json.dumps(saved))
    count = len(served)
    again = models_install.install(root, execute=True)
    assert len(served) == count and again['download_bytes'] == 0
    assert json.loads(recipes.read_text())['embed.tiny']['representation'] == 'question'
    models_install.install(root, execute=True, reconfigure=True)
    assert json.loads(recipes.read_text())['embed.tiny']['representation'] == 'text'


def test_a_download_that_differs_from_its_pinned_checksum_is_never_installed(lab, monkeypatch, tmp_path):
    root, blobs = lab
    fake_network(monkeypatch, tmp_path, blobs, corrupt='model.safetensors')
    with pytest.raises(ValueError, match='does not match its pinned SHA-256'):
        models_install.install(root, ['tiny'], execute=True)
    assert not (root / 'work/models/tiny/model.safetensors').exists()
    assert not (root / 'local-config/recipes.json').exists()


def test_the_download_limit_is_enforced_before_any_request(lab, monkeypatch, tmp_path):
    root, blobs = lab
    served = fake_network(monkeypatch, tmp_path, blobs)
    with pytest.raises(ValueError, match='raise --max-download-bytes'):
        models_install.install(root, ['tiny'], execute=True, max_download_bytes=100)
    assert served == []


def test_a_missing_package_says_which_extra_to_install(lab, monkeypatch, tmp_path):
    root, blobs = lab
    sys.modules.pop('fakepkg', None)
    with pytest.raises(ValueError, match='Install the fakepkg package'):
        models_install.install(root, ['pkg'], execute=True)


def test_unknown_models_and_unsafe_paths_are_refused(lab, tmp_path):
    root, _ = lab
    with pytest.raises(KeyError, match='nope'):
        models_install.plan(root, ['nope'])
    (root / 'registry/models/evil.yaml').write_text(yaml.safe_dump({'id': 'evil', 'install': {'dir': 'work/models/evil', 'files': [
        {'path': '../../escape', 'url': 'https://huggingface.co/x', 'bytes': 1, 'sha256': '0' * 64}], 'processors': {}}}))
    with pytest.raises(ValueError, match='Unsafe model file path'):
        models_install.plan(root, ['evil'])


def test_cli_status_and_fetch_dry_run(lab, capsys):
    root, _ = lab
    assert main(['--root', str(root), 'models', 'status']) == 0
    rows = json.loads(capsys.readouterr().out)
    assert {r['model'] for r in rows} == {'tiny', 'pkg'} and not any(r['installed'] for r in rows)
    assert main(['--root', str(root), 'models', 'fetch', '--model', 'tiny']) == 0
    assert json.loads(capsys.readouterr().out)['executed'] is False
