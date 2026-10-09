import json

from dataset_atlas.cli import main
from dataset_atlas.providers import ProviderService
from dataset_atlas.providers.schemas import CapabilityResult, ProviderConfig, ProviderView


def test_doctor_selected_provider_probe_is_explicit_benign_and_failure_is_actionable(workspace, monkeypatch, capsys):
    calls = []
    status = ['supported']
    def probe(self, identity, capabilities):
        calls.append((identity, capabilities))
        return ProviderView(config=ProviderConfig(id=identity, base_url='http://127.0.0.1:1234/v1', model='fixture'),
                            capabilities={'text_generation': CapabilityResult(status=status[0], detail='synthetic connection receipt')})
    monkeypatch.setattr(ProviderService, 'probe', probe)
    assert main(['--root', str(workspace), 'doctor']) == 0
    assert calls == []
    capsys.readouterr()
    assert main(['--root', str(workspace), 'doctor', '--probe-provider', 'local']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['downloads'] == 0 and report['providers'][0]['probe_input'] == 'generated benign text only'
    assert calls == [('local', ['text_generation'])]
    status[0] = 'unsupported'
    assert main(['--root', str(workspace), 'doctor', '--probe-provider', 'local']) == 1
    report = json.loads(capsys.readouterr().out)
    assert 'did not pass' in report['issues'][0]
