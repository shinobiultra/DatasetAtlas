import zipfile

import pytest
import yaml

from dataset_atlas.adapters.sad import SADStructsAdapter
from dataset_atlas.models import Dataset


def make_adapter(tmp_path, batch):
    path = tmp_path/'synthetic.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('batch/synthetic.yaml', yaml.safe_dump(batch))
        archive.writestr('sampletemplates/context.yaml', yaml.safe_dump({'id':'synthetic-template'}))
    return SADStructsAdapter(Dataset(id='fixture',name='Synthetic SAD fixture',release='test',snapshot_id='s',
        adapter='sad_structs',adapter_config={'path':str(path),'public_archive_password':'fixture',
            'annotations':[{'path_key':'path','task':'synthetic'}], 'mapping':{'question':'body'}}))


def test_template_variables_and_native_answers_are_not_executed(tmp_path):
    value = make_adapter(tmp_path, {'id':'batch','samples':[
        {'id':'original','body':'Synthetic {model_name} template','choices_right':['right'],
         'choices_wrong':['wrong'],'extra_template_vars':{'model_name':'unexpanded'}}]})
    source=value.prepare(value.plan(5,10000))
    record=value.iter_records(source).records[0]
    assert record.question == 'Synthetic {model_name} template'
    assert record.source['choices_right']==['right']
    assert record.source['extra_template_vars']=={'model_name':'unexpanded'}
    assert record.source['native_batch']=={'id':'batch'}
    assert record.source['native_record_kind']=='samples'
    assert record.source['_atlas_origin']['member']=='batch/synthetic.yaml'


def test_trials_remain_explicit_and_source_budget_is_enforced(tmp_path):
    value=make_adapter(tmp_path, {'id':'trial-batch','trials':[{'id':'trial','settings':{'seed':1}}]})
    assert value._rows()[0]['native_record_kind']=='trials'
    value=make_adapter(tmp_path, {'samples':[],'trials':[]})
    with pytest.raises(ValueError,match='exactly'):
        value._rows()
    value=make_adapter(tmp_path, {'samples':[{'id':'test'}]})
    value.config['max_annotation_bytes']=1
    with pytest.raises(ValueError,match='budget'):
        value._rows()
