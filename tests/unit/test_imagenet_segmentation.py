import hashlib
import io

import h5py
import numpy as np
from PIL import Image

from dataset_atlas.adapters.imagenet_segmentation import ImageNetSegmentationAdapter
from dataset_atlas.models import Dataset


def test_native_matlab_axes_additional_masks_and_independent_geometry(tmp_path):
    path=tmp_path/'fixture.mat';original=np.arange(18,dtype=np.uint8).reshape(3,2,3)
    with h5py.File(path,'w') as f:
        refs=f.create_group('#refs#');value=f.create_group('value')
        img=refs.create_dataset('image',data=original)
        masks=[refs.create_dataset('mask0',data=np.array([[0,1],[1,0]],dtype='uint8')),
               refs.create_dataset('mask1',data=np.array([[1,0,1]],dtype='uint8'))]
        gt=refs.create_dataset('gt',shape=(2,1),dtype=h5py.ref_dtype)
        for i,mask in enumerate(masks):gt[i,0]=mask.ref
        for key,text in [('id','fixture-native'),('target','n00000001')]:
            ds=refs.create_dataset(key,data=np.frombuffer(text.encode('utf-16-le'),dtype='<u2').reshape(-1,1));ds.attrs['MATLAB_class']=np.bytes_('char')
            link=value.create_dataset(key,shape=(1,1),dtype=h5py.ref_dtype);link[0,0]=ds.ref
        for key,ds in [('img',img),('gt',gt)]:
            link=value.create_dataset(key,shape=(1,1),dtype=h5py.ref_dtype);link[0,0]=ds.ref
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    adapter=ImageNetSegmentationAdapter(Dataset(id='fixture',name='fixture',release='fixture',adapter='imagenet_segmentation',adapter_config={'mat_path':str(path),'mat_sha256':sha}))
    source=adapter.prepare(adapter.plan(1,1000000));record=adapter.iter_records(source).records[0]
    assert len(record.assets)==3 and not record.source['native_geometry_matches']
    assert record.assets[1].metadata['used_by_pinned_author_loader']
    assert not record.assets[2].metadata['used_by_pinned_author_loader']
    with Image.open(io.BytesIO(adapter.resolve_asset(source,record.assets[0].uri).data)) as image:
        np.testing.assert_array_equal(np.asarray(image),original.transpose(2,1,0))
    with Image.open(io.BytesIO(adapter.resolve_asset(source,record.assets[2].uri).data)) as mask:
        np.testing.assert_array_equal(np.asarray(mask),np.array([[1],[0],[1]],dtype='uint8'))
