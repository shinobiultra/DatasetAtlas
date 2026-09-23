import hashlib,json
import PIL
import sys
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.pathways_shapes import PathwaysShapesAdapter,materialize,REVISION


def dataset(task):
    return Dataset(id='shapes',name='Author generator test',release='r',snapshot_id='s',adapter='pathways_shapes',adapter_config={
        'shape_task':task,'n_pairs':3,'image_size':128,'shape_size':12,'seed':42,'renderer_version':PIL.__version__,'python_version':'.'.join(map(str,sys.version_info[:2])),'generator_revision':REVISION})


@pytest.mark.parametrize('task',['recognition','localization','relations'])
def test_pair_identity_pixels_resume_and_integrity(tmp_path,task):
    d=dataset(task);proof=materialize(d,tmp_path/'rendered',1_000_000,lambda:None)
    assert proof['records']==6
    assert materialize(d,tmp_path/'rendered',1_000_000,lambda:None)==proof
    adapter=PathwaysShapesAdapter(d);source=adapter.prepare(adapter.plan(6,1_000_000));records=adapter.iter_records(source).records
    assert len(records)==6 and records[0].relations[0].object_id==records[1].id
    assert records[0].source['pair_id']==records[1].source['pair_id']==0
    assert adapter.resolve_asset(source,records[-1].assets[0].uri).sha256==records[-1].assets[0].sha256
    assert adapter.iter_records(source,'5',1).records[0].id==records[-1].id
    row=records[0].source;other=records[1].source
    if task=='recognition':assert row['obj1_position']==other['obj1_position'] and row['preposition']!=other['preposition']
    else:assert row['objects']==other['objects'] and row['obj1_position']!=other['obj1_position']
    (tmp_path/'rendered'/records[-1].assets[0].uri).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum changed'):materialize(d,tmp_path/'rendered',1_000_000,lambda:None)


def test_output_bound_cleanup_and_reproducibility_inputs(tmp_path):
    d=dataset('recognition')
    with pytest.raises(ValueError,match='output budget'):materialize(d,tmp_path/'rendered',1,lambda:None)
    assert not (tmp_path/'rendered').exists() and not (tmp_path/'rendered.partial').exists()
    d.adapter_config['n_pairs']=100000
    with pytest.raises(ValueError,match='bounds'):PathwaysShapesAdapter(d).probe()
    d=dataset('recognition');d.adapter_config['renderer_version']='unknown'
    with pytest.raises(ValueError,match='Pillow'):PathwaysShapesAdapter(d).probe()
