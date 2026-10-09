import zipfile

import pytest

from dataset_atlas.adapters.text_pairs import TextPairsAdapter
from dataset_atlas.models import Dataset


def adapter(tmp_path, members):
    path = tmp_path/'text.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return TextPairsAdapter(Dataset(id='synthetic',name='Synthetic paired text',release='test',snapshot_id='test',
        adapter='text_pairs',adapter_config={'path':str(path),'encoding':'cp1252','mapping':{'id':'native_id','text':'text'}}))


def test_native_encoding_labels_and_resume_cursor(tmp_path):
    value = adapter(tmp_path, {'b.txt':b'Second\r\ntext', 'b.lab':b'Two\nThree',
                              'a.txt':b'Example\x92s text', 'a.lab':b'One'})
    source = value.prepare(value.plan(1, 10000))
    first = value.iter_records(source)
    assert first.records[0].text == 'Example\u2019s text'
    assert first.records[0].source['native_id'] == 'a'
    last = value.iter_records(source, first.next_cursor)
    assert last.next_cursor is None and last.records[0].source['labels'] == ['Two','Three']
    assert last.records[0].source['labels_raw'] == 'Two\nThree'
    assert last.records[0].text.encode('cp1252') == b'Second\r\ntext'
    assert len(last.records[0].source['source_members']['b.txt']['sha256']) == 64


def test_unpaired_native_files_and_budgets_fail(tmp_path):
    value = adapter(tmp_path, {'a.txt':b'Unpaired'})
    with pytest.raises(ValueError,match='pair exactly'):
        value.prepare(value.plan(1,10000))
    value = adapter(tmp_path, {'a.txt':b'Text','a.lab':b'Label'})
    value.config['max_member_bytes'] = 2
    with pytest.raises(ValueError,match='member exceeds'):
        value.prepare(value.plan(1,10000))
