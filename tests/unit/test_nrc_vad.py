import zipfile
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.nrc_vad import NRCVADAdapter


def fixture(tmp_path, *, duplicate=False):
    old, new = tmp_path/'v1.zip', tmp_path/'v2.zip'
    with zipfile.ZipFile(old, 'w') as archive:
        archive.writestr('v1/main.txt', 'synthetic\t0.8\t0.5\t0.2\n')
        archive.writestr('v1/NRC-VAD-Lexicon-ForVariousLanguages.txt', 'English Word\tValence\tArousal\tDominance\tTest Language\nsynthetic\t0.8\t0.5\t0.2\ttranslation\n')
        archive.writestr('v1/BipolarScale/PolarSubset/valence-synthetic.txt', 'synthetic\t0.8\n' * (2 if duplicate else 1))
    with zipfile.ZipFile(new, 'w') as archive:
        archive.writestr('v2/main.txt', 'term\tvalence\tarousal\tdominance\n"synthetic phrase"\t-0.2\t0.1\t0.4\n')
        archive.writestr('v2/valence-synthetic.txt', 'term\tvalence\n"synthetic phrase"\t-0.2\n')
    return NRCVADAdapter(Dataset(id='fixture', name='Synthetic lexicon fixture', release='test', snapshot_id='s',
        adapter='nrc_vad', adapter_config={'old':str(old), 'new':str(new), 'annotations':[
            {'version':'1','prefix':'v1/','main_member':'main.txt','path_key':'old'},
            {'version':'2.1','prefix':'v2/','main_member':'main.txt','path_key':'new'}]}))


def test_native_versions_quotes_translations_and_misnamed_scale_are_preserved(tmp_path):
    adapter = fixture(tmp_path)
    # Use native dimension filename semantics in the synthetic directory.
    rows = adapter._rows()
    assert len(rows) == 2
    assert rows[0]['score_scale'] == [0, 1] and rows[1]['score_scale'] == [-1, 1]
    assert rows[1]['term'] == '"synthetic phrase"'
    assert rows[0]['translations'] == {'Test Language':'translation'}
    assert rows[0]['native_exports']['BipolarScale/PolarSubset/valence-synthetic.txt']['fields']['valence'] == '0.8'
    assert 'native_score_disagreements' not in rows[0]


def test_duplicate_export_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='duplicate'):
        fixture(tmp_path, duplicate=True)._rows()
