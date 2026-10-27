"""A release must not rely on ignored public data left by a previous build."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib
from unittest.mock import patch


def release_script():
    path = Path(__file__).resolve().parents[2] / 'scripts/build_release.py'
    spec = importlib.util.spec_from_file_location('atlas_release_build', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Old script executed on import; keep the regression probe side-effect free.
    with patch('subprocess.run'), patch('shutil.copytree'), patch('shutil.rmtree'):
        spec.loader.exec_module(module)
    return module


def test_package_version_matches_release_metadata():
    from dataset_atlas import __version__
    project = Path(__file__).resolve().parents[2] / 'pyproject.toml'
    assert __version__ == tomllib.loads(project.read_text())['project']['version']


def test_frontend_build_regenerates_approved_data_before_node_build(tmp_path, monkeypatch):
    module = release_script()
    calls = []

    def publish(registry, packs, output, profile):
        assert registry == tmp_path / 'registry'
        assert packs == tmp_path / 'examples/approved-packs'
        assert profile == tmp_path / 'registry/publication.json'
        (output / 'data').mkdir(parents=True)
        (output / 'data/catalogue.json').write_text('[]')
        calls.append('validated-data')
        return 'publication-receipt'

    def run(command, **kwargs):
        assert (tmp_path / 'apps/web/public/data/catalogue.json').is_file()
        assert kwargs['cwd'] == tmp_path / 'apps/web'
        assert kwargs['check'] is True
        if command == ['npm', 'run', 'build']:
            assert kwargs['env']['ATLAS_BASE'] == './'
        calls.append(command)

    monkeypatch.setattr('dataset_atlas.exports.build_publication', publish)
    monkeypatch.setattr(module.subprocess, 'run', run)
    assert module.build_frontend(tmp_path) == 'publication-receipt'
    assert calls == ['validated-data', ['npm', 'ci'], ['npm', 'run', 'build']]


def test_failed_publication_never_builds_or_packages_stale_data(tmp_path, monkeypatch):
    import pytest
    module = release_script()

    def refuse(*args, **kwargs):
        raise ValueError('Unapproved media')

    monkeypatch.setattr('dataset_atlas.exports.build_publication', refuse)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: pytest.fail('Must validate first'))
    with pytest.raises(ValueError, match='Unapproved media'):
        module.build_frontend(tmp_path)


def test_ci_can_reuse_installed_node_dependencies_but_still_validates_inputs(tmp_path, monkeypatch):
    module = release_script()
    calls = []
    monkeypatch.setattr('dataset_atlas.exports.build_publication', lambda *args: calls.append('validate'))
    monkeypatch.setattr(module.subprocess, 'run', lambda command, **kwargs: calls.append(command))
    module.build_frontend(tmp_path, install_dependencies=False)
    assert calls == ['validate', ['npm', 'run', 'build']]
