"""CIFAR-C numpy arrays addressed directly inside the uncompressed source tar."""
from __future__ import annotations
import io
import math
from pathlib import Path
import re
import tarfile
import numpy as np
from PIL import Image
from .core import DatasetAdapter,DirectoryArchiveAdapter,RecordBatch,MediaHandle


class CIFARCorruptionsAdapter(DirectoryArchiveAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        import copy
        self.config=copy.deepcopy(dataset.adapter_config)

    def _arrays(self):
        if hasattr(self,'_data_arrays'):return self._data_arrays
        arrays={}
        # No pickle and no archive extraction. The mmap points at verified source bytes.
        with tarfile.open(self._path(),'r:') as archive:
            for member in archive:
                if not member.isfile() or not member.name.endswith('.npy'):continue
                name=Path(member.name).stem
                if name in arrays or not re.fullmatch('[a-z_]+',name):raise ValueError('Duplicate or invalid corruption array')
                with self._path().open('rb') as stream:
                    stream.seek(member.offset_data)
                    version=np.lib.format.read_magic(stream)
                    if version==(1,0):shape,order,dtype=np.lib.format.read_array_header_1_0(stream)
                    elif version==(2,0):shape,order,dtype=np.lib.format.read_array_header_2_0(stream)
                    else:raise ValueError('Unsupported numpy header version')
                    offset=stream.tell()
                if dtype.hasobject or order:raise ValueError('Object arrays and Fortran order are unsupported')
                expected_bytes=math.prod(shape)*dtype.itemsize
                if offset-member.offset_data+expected_bytes!=member.size:raise ValueError('Corruption array is truncated or has trailing bytes')
                arrays[name]=np.memmap(self._path(),mode='r',dtype=dtype,offset=offset,shape=shape)
        labels=arrays.pop('labels',None)
        if labels is None or labels.ndim!=1 or not np.issubdtype(labels.dtype,np.integer):raise ValueError('Corruption labels are missing or invalid')
        per_severity=int(self.config.get('examples_per_severity',10000))
        severities=int(self.config.get('severities',5))
        if per_severity<1 or severities<1:raise ValueError('Invalid corruption population')
        expected=per_severity*severities
        if len(labels) not in (per_severity,expected):raise ValueError('Labels disagree with corruption population')
        if len(labels)==expected and any(not np.array_equal(labels[:per_severity],labels[i*per_severity:(i+1)*per_severity]) for i in range(severities)):
            raise ValueError('Source labels change across severities')
        declared=self.config.get('corruptions')
        if declared is not None and set(arrays)!=set(declared):raise ValueError('Corruption types disagree with declared release')
        if not arrays:raise ValueError('No corruption images')
        for name,array in arrays.items():
            if array.dtype!=np.uint8 or array.shape!=(expected,32,32,3):raise ValueError(f'Invalid corruption dimensions: {name}')
        if np.any(labels<0) or np.any(labels>=int(self.config.get('class_count',10))):raise ValueError('Corruption labels outside class range')
        self._data_arrays=dict(sorted(arrays.items()));self._labels=labels;self._per_severity=per_severity
        return self._data_arrays

    @property
    def count(self):return sum(len(a) for a in self._arrays().values())

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative cursor')
        end=min(start+min(limit or source.limit,source.limit),self.count)
        arrays=self._arrays();names=list(arrays);rows=[]
        per_corruption=len(arrays[names[0]])
        self.config['mapping']={'id':'corrupted_id','media':'image'}
        for ordinal in range(start,end):
            corruption=names[ordinal//per_corruption];index=ordinal%per_corruption
            image_id=index%self._per_severity
            row={'corrupted_id':f'{corruption}:{index}','corruption':corruption,'severity':index//self._per_severity+1,
                 'original_test_index':image_id,'label':int(self._labels[image_id]),'image':f'{corruption}/{index}.png',
                 'representation':'lossless PNG rendering of source uint8 RGB array'}
            record=DatasetAdapter._record(self,row,ordinal);source.charge(len(record.model_dump_json().encode()));rows.append(record)
        return RecordBatch(rows,str(end) if end<self.count else None,len(rows))

    def resolve_asset(self,source,asset_ref):
        match=re.fullmatch(r'([a-z_]+)/([0-9]+)\.png',asset_ref)
        arrays=self._arrays()
        if not match or match[1] not in arrays:raise ValueError('Invalid corruption media reference')
        index=int(match[2]);array=arrays[match[1]]
        if index>=len(array):raise ValueError('Corruption media row out of range')
        stream=io.BytesIO();Image.fromarray(np.asarray(array[index])).save(stream,format='PNG');data=stream.getvalue();source.charge(len(data))
        import hashlib
        return MediaHandle(data,'image/png',hashlib.sha256(data).hexdigest(),asset_ref)
