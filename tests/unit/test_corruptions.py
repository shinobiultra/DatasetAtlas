import hashlib,io,tarfile
import numpy as np
from PIL import Image
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.corruptions import CIFARCorruptionsAdapter


def make(tmp_path,labels=None,corruption=None):
    path=tmp_path/'source.tar'
    image=np.zeros((6,32,32,3),dtype=np.uint8)
    for i in range(6):image[i]=i*10
    with tarfile.open(path,'w') as tar:
        for name,value in {'labels':np.array([0,1]*3) if labels is None else labels,'noise':image if corruption is None else corruption,'blur':image}.items():
            stream=io.BytesIO();np.save(stream,value,allow_pickle=False);data=stream.getvalue()
            member=tarfile.TarInfo(f'CIFAR-10-C/{name}.npy');member.size=len(data);tar.addfile(member,io.BytesIO(data))
    dataset=Dataset(id='corrupted',name='Corrupted',release='r',snapshot_id='s',adapter='cifar_c_npy',adapter_config={
        'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'examples_per_severity':2,'severities':3,'corruptions':['noise','blur']})
    return CIFARCorruptionsAdapter(dataset)


def test_every_corruption_severity_and_original_pixels(tmp_path):
    adapter=make(tmp_path);source=adapter.prepare(adapter.plan(4,1000000))
    assert adapter.count==12
    first=adapter.iter_records(source,'5',4)
    assert first.next_cursor=='9'
    assert [(r.source['corruption'],r.source['severity'],r.source['label']) for r in first.records]==[('blur',3,1),('noise',1,0),('noise',1,1),('noise',2,0)]
    data=adapter.resolve_asset(source,first.records[0].assets[0].uri).data
    with Image.open(io.BytesIO(data)) as image:assert np.array_equal(np.asarray(image),np.full((32,32,3),50,dtype=np.uint8))
    assert adapter.iter_records(source,'11').records[0].source['original_test_index']==1
    assert not (tmp_path/'CIFAR-10-C').exists()


def test_corruption_labels_shapes_and_unsafe_refs(tmp_path):
    adapter=make(tmp_path,labels=np.array([0,1,1,1,0,1]))
    with pytest.raises(ValueError,match='change across'):adapter.count
    adapter=make(tmp_path,corruption=np.zeros((6,16,16,3),dtype=np.uint8))
    with pytest.raises(ValueError,match='dimensions'):adapter.count
    adapter=make(tmp_path);source=adapter.prepare(adapter.plan(2,1000000))
    for ref in ('../labels.npy','noise/999.png','blur/-1.png'):
        with pytest.raises(ValueError):adapter.resolve_asset(source,ref)
