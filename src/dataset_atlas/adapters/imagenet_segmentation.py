"""Exact native MATLAB v7.3 image/mask references used by CLIP text-span."""
import hashlib
import io
from pathlib import Path
import re

import numpy as np
from PIL import Image

from .core import DatasetAdapter,SourceDescription,RecordBatch,MediaHandle


class ImageNetSegmentationAdapter(DatasetAdapter):
    def _path(self):return Path(self.config['mat_path'])

    def probe(self):
        path=self._path()
        return SourceDescription('native MATLAB v7.3',str(path),path.is_file(),self.revision,
            path.stat().st_size if path.is_file() else None,True,True,True,True,True,
            ('MATLAB axes follow the pinned author loader. PNGs preserve native image/mask pixels; the MAT source remains intact.',))

    def prepare(self,approved_plan):
        source=super().prepare(approved_plan)
        expected=self.config['mat_sha256']
        if getattr(self,'verified',None)!=expected:
            with self._path().open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Native segmentation MAT checksum changed')
            self.verified=expected
        self._rows();return source

    def _rows(self):
        if hasattr(self,'rows'):return self.rows
        import h5py
        from importlib import import_module
        # h5o is a runtime C extension; its exported symbols are not Python stubs.
        object_info=import_module('h5py.h5o').get_info
        rows=[];seen=set()
        with h5py.File(self._path(),'r') as f:
            # HDF5's name lookup for a dereferenced object scans links repeatedly.
            # Resolve native addresses once, rather than once per image/mask.
            names={object_info(f['#refs#'][key].id).addr:'#refs#/'+key for key in f['#refs#']}
            def name_of(dataset):return '/'+names[object_info(dataset.id).addr]
            count=len(f['value/img'])
            if any(f['value/'+key].shape!=(count,1) for key in ('img','gt','id','target')):
                raise ValueError('Native segmentation reference populations disagree')
            def text(reference):
                dataset=f[reference]
                if dataset.dtype!=np.dtype('uint16') or dataset.size>1024 or dataset.attrs.get('MATLAB_class')!=b'char':
                    raise ValueError('Native segmentation identity must be a bounded MATLAB character array')
                return np.asarray(dataset,dtype='<u2').tobytes().decode('utf-16-le')
            for ordinal in range(count):
                name=text(f['value/id'][ordinal,0]);target=text(f['value/target'][ordinal,0])
                if name in seen:raise ValueError('Duplicate native segmentation identity')
                seen.add(name);image=f[f['value/img'][ordinal,0]];labels=f[f['value/gt'][ordinal,0]]
                if labels.ndim!=2 or not 1<=labels.size<=32:raise ValueError('Native segmentation groundtruth references exceed limits')
                mask=f[labels[0,0]]
                if image.ndim!=3 or image.shape[0]!=3 or image.dtype!=np.dtype('uint8') or mask.ndim!=2:
                    raise ValueError('Native segmentation image/mask dimensions or types disagree')
                if mask.dtype not in (np.dtype('uint8'),np.dtype('uint16')) or image.size>150_000_000 or mask.size>50_000_000:
                    raise ValueError('Native segmentation pixel budget or mask dtype exceeded')
                rows.append({'source_id':name,'native_row':ordinal,'class_wnid':target,
                    'native_image_dataset':name_of(image),'native_mask_dataset':name_of(mask),
                    'width':image.shape[1],'height':image.shape[2],'native_mask_dtype':str(mask.dtype),
                    'mask_width':mask.shape[0],'mask_height':mask.shape[1],
                    'native_geometry_matches':mask.shape==image.shape[1:],
                    'media_refs':[f'mat/{ordinal}/image.png',f'mat/{ordinal}/mask.png'],
                    'source_mat_sha256':self.config['mat_sha256']})
                masks=[]
                for position in np.ndindex(labels.shape):
                    value=f[labels[position]]
                    if value.ndim!=2 or value.dtype!=np.dtype('uint8') or value.size>50_000_000:
                        raise ValueError('Native segmentation mask dimensions or dtype exceed limits')
                    masks.append({'dataset':name_of(value),'native_cell':list(position),
                        'width':value.shape[0],'height':value.shape[1],
                        'geometry_matches':value.shape==image.shape[1:]})
                rows[-1]['native_masks']=masks
                rows[-1]['media_refs']=[f'mat/{ordinal}/image.png']+[f'mat/{ordinal}/mask'+('' if i==0 else '-'+str(i))+'.png' for i in range(len(masks))]
        self.rows=rows;return rows

    @property
    def count(self):return len(self._rows())

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative native cursor')
        rows=self._rows();end=min(len(rows),start+min(limit or source.limit,source.limit));records=[]
        self.config['mapping']={'id':'source_id','media':'media_refs','label':'class_wnid'}
        for i,row in enumerate(rows[start:end],start):
            record=self._record(row,i)
            for asset in record.assets:
                if asset.uri is None:continue
                mask_match=re.search(r'/mask(?:-([0-9]+))?\.png$',asset.uri)
                mask=mask_match is not None
                info=row['native_masks'][int(mask_match[1] or 0)] if mask_match else None
                asset.metadata.update(purpose='mask' if mask else 'image',
                    width=info['width'] if info else row['width'],height=info['height'] if info else row['height'],
                    native_geometry_matches=info['geometry_matches'] if info else row['native_geometry_matches'],
                    native_cell=info['native_cell'] if info else None,
                    binary_label_mask=bool(info),
                    used_by_pinned_author_loader=not info or info['native_cell']==[0,0],
                    representation='lossless PNG from original MATLAB pixels',source_mat_sha256=self.config['mat_sha256'],
                    native_dataset=info['dataset'] if info else row['native_image_dataset'],
                    native_axes='transpose(1,0)' if mask else 'transpose(2,1,0)',native_mask_dtype=row['native_mask_dtype'] if mask else None)
            source.charge(len(record.model_dump_json().encode()));records.append(record)
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))

    def resolve_asset(self,source,asset_ref):
        import h5py
        match=re.fullmatch(r'mat/([0-9]+)/(image|mask)(?:-([0-9]+))?\.png',asset_ref)
        if not match:raise ValueError('Invalid native segmentation asset reference')
        ordinal=int(match[1]);rows=self._rows()
        if ordinal>=len(rows):raise ValueError('Native segmentation asset row out of bounds')
        mask_index=int(match[3] or 0)
        if match[2]=='image' and match[3] is not None:raise ValueError('Native image cannot have a mask ordinal')
        if mask_index>=len(rows[ordinal]['native_masks']):raise ValueError('Native mask ordinal out of bounds')
        key=rows[ordinal]['native_image_dataset'] if match[2]=='image' else rows[ordinal]['native_masks'][mask_index]['dataset']
        with h5py.File(self._path(),'r') as f:array=np.asarray(f[key])
        pixels=array.transpose((2,1,0)) if match[2]=='image' else array.transpose((1,0))
        if match[2]=='mask' and not np.isin(pixels,[0,1]).all():raise ValueError('Native groundtruth contains unexpected binary label values')
        output=io.BytesIO();Image.fromarray(pixels).save(output,format='PNG')
        data=output.getvalue()
        source.charge(len(data))
        return MediaHandle(data,'image/png',hashlib.sha256(data).hexdigest(),asset_ref)
