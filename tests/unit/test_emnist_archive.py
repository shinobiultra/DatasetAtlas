import gzip
import io
import struct
import zipfile
import numpy as np
from PIL import Image
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters import get_adapter


def fixture(tmp_path, corrupt=False):
    path=tmp_path/'gzip.zip';pixels=np.arange(784,dtype=np.uint8).reshape(28,28)
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('gzip/emnist-letters-mapping.txt','1 65 97\n2 66 98\n')
        for split in ['train','test']:
            data=struct.pack('>IIII',2051,1,28,28)+pixels.tobytes()
            archive.writestr(f'gzip/emnist-letters-{split}-images-idx3-ubyte.gz',gzip.compress(data[:-1] if corrupt else data))
            archive.writestr(f'gzip/emnist-letters-{split}-labels-idx1-ubyte.gz',gzip.compress(struct.pack('>II',2049,1)+b'\x01'))
    return get_adapter(Dataset(id='emnist',name='Fixture',release='r',snapshot_id='s',adapter='emnist_archive',adapter_config={
        'path':str(path),'configurations':['letters'],'counts':{'letters':{'train':1,'test':1}}})),pixels


def test_emnist_native_labels_splits_transpose_and_late_access(tmp_path):
    a,pixels=fixture(tmp_path);source=a.prepare(a.plan(10,10000));records=a.iter_records(source).records
    assert len(records)==a.count==2 and records[0].id!=records[1].id
    assert records[0].source['label']==1 and records[0].source['characters']=='A / a'
    assert records[1].source['split']=='test'
    image=Image.open(io.BytesIO(a.resolve_asset(source,records[1].assets[0].uri).data))
    np.testing.assert_array_equal(np.asarray(image),pixels.T)
    assert records[1].assets[0].metadata['display_transform']=='transpose'
    with pytest.raises(ValueError,match='outside'):a.resolve_asset(source,'letters/test/1.png')


def test_emnist_detects_truncated_pixels_on_access(tmp_path):
    a,_=fixture(tmp_path,corrupt=True);source=a.prepare(a.plan(10,10000))
    with pytest.raises(ValueError,match='payload length'):a.resolve_asset(source,'letters/train/0.png')


def test_emnist_respects_decoded_partition_limit(tmp_path):
    a,_=fixture(tmp_path);a.config['max_decoded_partition_bytes']=100
    with pytest.raises(ValueError,match='decoded byte budget'):
        a.resolve_asset(a.prepare(a.plan(10,10000)),'letters/train/0.png')
