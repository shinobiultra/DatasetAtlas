"""Pinned Parquet image structs, decoded selectively without executing dataset code."""
from __future__ import annotations
import hashlib
import base64
import io
import json
import re
from pathlib import Path
from PIL import Image
import pyarrow.parquet as pq
from dataset_atlas.models import Asset,stable_id
from .core import StructuredAdapter,DatasetAdapter,MediaHandle,RecordBatch


def _encoding(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):return 'png','image/png'
    if data.startswith(b'\xff\xd8\xff'):return 'jpg','image/jpeg'
    if data[:4]==b'RIFF' and data[8:12]==b'WEBP':return 'webp','image/webp'
    if data[:6] in {b'GIF87a',b'GIF89a'}:return 'gif','image/gif'
    if data[4:8]==b'ftyp' and data[8:12] in {b'avif',b'avis'}:return 'avif','image/avif'
    raise ValueError('Embedded image encoding is unsupported')

class EmbeddedParquetAdapter(StructuredAdapter):
    """One pinned file. media_columns names top-level image structs or lists."""
    def __init__(self,dataset):
        super().__init__(dataset)
        self.config={**self.config,'format':'parquet'}
        columns=self.config.get('media_columns',[self.config.get('mapping',{}).get('media','image')])
        if not isinstance(columns,list) or not columns or any(not isinstance(key,str) or not key or '.' in key for key in columns):raise ValueError('media_columns must name top-level Parquet fields')
        if len(columns)>16:raise ValueError('Too many embedded image columns')
        self.media_columns=columns
        if not re.fullmatch('[a-f0-9]{64}',self.config.get('sha256','')):raise ValueError('Embedded Parquet requires a pinned source SHA-256')
        self.config['mapping']={**self.config.get('mapping',{}),'media':'_atlas_embedded_refs'}

    def _entries(self,row):
        entries=[]
        for column in self.media_columns:
            value=row.get(column)
            if value is None:continue
            values=value if isinstance(value,list) else [value]
            for index,item in enumerate(values):
                if isinstance(item,str) and self.config.get('media_encoding') == 'base64':
                    if len(item)>13_333_336:raise ValueError('Encoded image exceeds 10 MB decoded budget')
                    item={'bytes':base64.b64decode(item,validate=True),'path':None}
                if isinstance(item,(bytes,bytearray)):item={'bytes':bytes(item),'path':None}
                if item is None:item={'bytes':None,'path':None}
                if not isinstance(item,dict):raise ValueError('Embedded image must be bytes or a bytes/path struct')
                data=item.get('bytes')
                if data is not None and not isinstance(data,bytes):raise ValueError('Embedded image bytes have invalid type')
                if data and len(data)>10_000_000:raise ValueError('Embedded image exceeds 10 MB')
                entries.append((column,index,item,data))
        if len(entries)>32:raise ValueError('Record exceeds 32 embedded images')
        if sum(len(data) for _,_,_,data in entries if data)>20_000_000:raise ValueError('Record exceeds 20 MB embedded image budget')
        return entries

    def _record(self,row,ordinal):
        normalized=dict(row);refs=[];assets=[];metadata={column:[] for column in self.media_columns}
        for slot,(column,index,item,data) in enumerate(self._entries(row)):
            digest=hashlib.sha256(data).hexdigest() if data else None
            suffix,_=_encoding(data) if data else ('png','image/png')
            ref=f'embedded/{ordinal}/{slot}.{suffix}' if data else None
            value={'source_path':item.get('path'),'sha256':digest,'bytes':len(data) if data else 0,'status':'embedded' if data else 'missing_embedded_bytes'}
            if self.config.get('media_encoding'):value['source_encoding']=self.config['media_encoding']
            metadata[column].append(value)
            if ref:refs.append(ref)
            assets.append(Asset(id=stable_id(self.dataset.id,self.revision,'asset',digest or f'missing:{ordinal}:{slot}'),dataset_id=self.dataset.id,release_id=self.revision,modality='image',uri=ref,sha256=digest,metadata={**value,'source_field':column,'source_slot':index,'source_row':ordinal}))
        for column,values in metadata.items():
            if column not in row:continue
            normalized[column]=values if isinstance(row.get(column),list) else values[0] if values else None
        normalized['_atlas_embedded_refs']=refs
        record=DatasetAdapter._record(self,normalized,ordinal)
        record.assets=assets;record.asset_ids=[asset.id for asset in assets]
        record.source.pop('_atlas_embedded_refs',None)
        return record

    def _slice(self,start,limit):
        parquet=pq.ParquetFile(self._path());offset=0
        for group in range(parquet.num_row_groups):
            count=parquet.metadata.row_group(group).num_rows
            if offset+count<=start:offset+=count;continue
            for batch in parquet.iter_batches(batch_size=8,row_groups=[group]):
                if offset+batch.num_rows<=start:offset+=batch.num_rows;continue
                skip=max(0,start-offset)
                sliced=batch.slice(skip,min(limit,batch.num_rows-skip))
                for row in sliced.to_pylist():yield row
                limit-=sliced.num_rows;offset+=batch.num_rows
                if limit==0:return

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0);size=min(limit or source.limit,source.limit)
        if start<0:raise ValueError('Negative cursor')
        records=[]
        for ordinal,row in enumerate(self._slice(start,size),start):
            record=self._record(row,ordinal)
            source.charge(sum(len(data) for _,_,_,data in self._entries(row) if data)+len(record.model_dump_json().encode()))
            records.append(record)
        total=pq.read_metadata(self._path()).num_rows
        return RecordBatch(records,str(start+len(records)) if start+len(records)<total else None,len(records))

    def resolve_asset(self,source,asset_ref):
        match=re.fullmatch(r'embedded/([0-9]{1,12})/([0-9]{1,2})\.(png|jpg|webp|gif|avif)',asset_ref)
        if not match:raise ValueError('Invalid embedded image reference')
        row_index,slot=int(match[1]),int(match[2]);rows=list(self._slice(row_index,1))
        if not rows:raise FileNotFoundError('Embedded source row does not exist')
        entries=self._entries(rows[0])
        if slot>=len(entries) or not entries[slot][3]:raise FileNotFoundError('Embedded source image is missing')
        data=entries[slot][3];source.charge(len(data));suffix,mime=_encoding(data)
        if suffix!=match[3]:raise ValueError('Image reference encoding differs from source')
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('Embedded image pixel budget exceeded')
            image.verify()
        return MediaHandle(data,mime,hashlib.sha256(data).hexdigest(),asset_ref)
