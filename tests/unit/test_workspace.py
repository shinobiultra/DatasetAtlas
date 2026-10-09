"""`atlas init` turns an installed package into a workspace without ever touching a researcher's own data."""
import pytest

from dataset_atlas.cli import main
from dataset_atlas.workspace import init_workspace, initialised, seed_available


@pytest.fixture
def seed(tmp_path):
    root = tmp_path / 'seed'
    (root / 'registry/datasets').mkdir(parents=True)
    (root / 'registry/datasets/alpha.yaml').write_text('id: alpha\nname: Alpha\n')
    (root / 'registry/datasets/beta.yaml').write_text('id: beta\nname: Beta\n')
    (root / 'schemas').mkdir()
    (root / 'schemas/atlas.schema.json').write_text('{}')
    return root


def test_init_creates_a_workspace_with_the_shipped_catalogue(tmp_path, seed):
    result = init_workspace(tmp_path / 'ws', seed=seed)
    assert result['datasets'] == 2 and result['replaced'] == []
    assert initialised(tmp_path / 'ws') and (tmp_path / 'ws/work').is_dir() and (tmp_path / 'ws/local-config').is_dir()


def test_init_refuses_to_overwrite_an_existing_workspace(tmp_path, seed):
    init_workspace(tmp_path / 'ws', seed=seed)
    with pytest.raises(ValueError, match='already a workspace'):
        init_workspace(tmp_path / 'ws', seed=seed)


def test_update_replaces_only_the_shipped_catalogue(tmp_path, seed):
    ws = tmp_path / 'ws'
    init_workspace(ws, seed=seed)
    # Everything a researcher creates sits outside the shipped catalogue.
    (ws / 'work/prepared/alpha').mkdir(parents=True)
    (ws / 'work/prepared/alpha/active.json').write_text('{"version": "v1"}')
    (ws / 'local-config/registry/datasets').mkdir(parents=True)
    (ws / 'local-config/registry/datasets/mine.yaml').write_text('id: mine\n')
    (seed / 'registry/datasets/gamma.yaml').write_text('id: gamma\nname: Gamma\n')
    (seed / 'registry/datasets/alpha.yaml').write_text('id: alpha\nname: Alpha v2\n')
    result = init_workspace(ws, update=True, seed=seed)
    assert result['datasets'] == 3 and result['replaced'] == ['registry', 'schemas']
    assert 'Alpha v2' in (ws / 'registry/datasets/alpha.yaml').read_text()
    assert (ws / 'work/prepared/alpha/active.json').read_text() == '{"version": "v1"}'
    assert (ws / 'local-config/registry/datasets/mine.yaml').read_text() == 'id: mine\n'
    assert not [p for p in ws.iterdir() if p.name.startswith('.') and ('incoming' in p.name or 'retired' in p.name)]


def test_update_needs_an_existing_workspace(tmp_path, seed):
    with pytest.raises(ValueError, match='not a workspace yet'):
        init_workspace(tmp_path / 'nope', update=True, seed=seed)


def test_installation_without_a_catalogue_says_what_to_do(tmp_path):
    assert not seed_available(tmp_path / 'empty')
    with pytest.raises(ValueError, match='no catalogue'):
        init_workspace(tmp_path / 'ws', seed=tmp_path / 'empty')


def test_commands_in_an_uninitialised_directory_point_at_init(tmp_path, capsys):
    assert main(['--root', str(tmp_path), 'serve']) == 1
    assert 'atlas init' in capsys.readouterr().err
    assert main(['--root', str(tmp_path), 'previews', 'status']) == 1


def test_doctor_reports_actionable_issues_and_exits_nonzero(tmp_path, capsys):
    import json
    (tmp_path / 'registry/datasets').mkdir(parents=True)
    (tmp_path / 'local-config').mkdir()
    (tmp_path / 'local-config/storage.json').write_text(json.dumps({
        'target_bytes': 10, 'ceiling_bytes': 20, 'optimized_cache_bytes': 5, 'enforce_preparation_ceiling': True,
        'external_roots': [str(tmp_path / 'a-model-folder-that-was-removed')]}))
    assert main(['--root', str(tmp_path), 'doctor']) == 1
    report = json.loads(capsys.readouterr().out)
    assert any('a-model-folder-that-was-removed' in issue and 'atlas storage configure' in issue for issue in report['issues'])
    assert report['datasets'] == 0 and report['downloads'] == 0


def test_doctor_in_an_uninitialised_directory_points_at_init(tmp_path, capsys):
    import json
    assert main(['--root', str(tmp_path), 'doctor']) == 1
    assert any('atlas init' in issue for issue in json.loads(capsys.readouterr().out)['issues'])
