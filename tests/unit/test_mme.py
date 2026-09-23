import zipfile

import pytest

from dataset_atlas.adapters.mme import MMEAdapter
from dataset_atlas.models import Dataset


def test_mme_preserves_paired_questions_and_filters_named_categories(tmp_path):
    path = tmp_path / 'mme.zip'
    with zipfile.ZipFile(path, 'w') as z:
        for category in ['artwork', 'color']:
            base = category + ('/questions_answers_YN' if category == 'artwork' else '')
            z.writestr(base+'/one.txt', 'Is this blue?\tYes\nIs this red?\tNo\n')
            z.writestr(base.replace('/questions_answers_YN', '/images')+'/one.jpg', b'fixture')
    config = {'path': str(path), 'archive_prefix': '', 'dataset_kind': 'mme', 'mapping': {'question': 'question', 'answer': 'answer'}}
    dataset = Dataset(id='mme', name='Fixture', adapter='mme', adapter_config=config)
    adapter = MMEAdapter(dataset)
    records = adapter.iter_records(adapter.prepare(adapter.plan(10, 100000))).records
    assert len(records) == 4
    assert records[0].id != records[1].id
    assert records[0].source['pair_id'] == records[1].source['pair_id']
    assert records[0].assets[0].id == records[1].assets[0].id
    assert [r.source['answer'] for r in records[:2]] == ['Yes', 'No']
    dataset.adapter_config['categories'] = ['color']
    assert MMEAdapter(dataset).count == 2
    dataset.adapter_config['categories'] = ['absent']
    with pytest.raises(ValueError, match='not present'):
        MMEAdapter(dataset)._rows()
