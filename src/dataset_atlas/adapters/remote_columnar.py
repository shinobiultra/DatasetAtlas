"""Index complete remote Parquet annotations while deferring embedded image columns."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import io
import json
import re
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
from dataset_atlas.models import Asset,stable_id
from dataset_atlas.storage import BoundedCache
from dataset_atlas.storage.ranges import HttpsRangeReader,SmallReadBuffer
from .core import DatasetAdapter,SourceDescription,RecordBatch,MediaHandle
from .embedded_parquet import _encoding


class RemoteColumnarAdapter(DatasetAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        import copy
        self.config=copy.deepcopy(dataset.adapter_config)
        self.files=self.config['remote_files']
        if not self.files:raise ValueError('Remote Parquet files are required')
        self.bytes_fetched=0
        self.transfer_limit=self.config.get('metadata_transfer_bytes',100_000_000)
        self.cancel=None
        self.cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',1_000_000_000))
        self._layouts={}

    def probe(self):
        return SourceDescription('remote_columnar',self.files[0]['url'],True,self.revision,sum(f['bytes'] for f in self.files),
            True,True,True,False,True,('Complete annotations indexed through HTTPS ranges; embedded images fetched on inspection.',))

    @contextmanager
    def _parquet(self,index,budget=None):
        entry=self.files[index]
        limit=budget if budget is not None else self.transfer_limit-self.bytes_fetched
        if limit<=0:raise ValueError('Remote metadata transfer budget exhausted')
        with HttpsRangeReader(entry['url'],size=entry['bytes'],etag=entry['etag'],allowed_hosts=self.config['allowed_hosts'],
                              byte_budget=limit,cache=self.cache,cancel=self.cancel) as source:
            try:
                # Disable speculative reads spanning omitted image columns.
                buffer=SmallReadBuffer(source) if budget is None else source
                parquet=pq.ParquetFile(buffer,pre_buffer=False,buffer_size=0)
                parquet._atlas_buffer=buffer
                yield parquet
            finally:
                if budget is None:self.bytes_fetched+=source.bytes_fetched

    def _layout(self,index):
        if index not in self._layouts:
            with self._parquet(index) as parquet:
                schema=parquet.schema_arrow;media={};columns=[]
                for field in schema:
                    dtype=field.type;is_list=pa.types.is_list(dtype) or pa.types.is_large_list(dtype)
                    if is_list:dtype=dtype.value_type
                    if pa.types.is_struct(dtype) and 'bytes' in [f.name for f in dtype]:
                        if 'path' not in [f.name for f in dtype]:raise ValueError(f'Remote media column {field.name} needs a path leaf to preserve slots without reading bytes')
                        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',field.name):raise ValueError('Remote media field name is unsupported')
                        media[field.name]=is_list
                    elif pa.types.is_binary(dtype) or pa.types.is_large_binary(dtype):
                        raise ValueError(f'Remote binary column {field.name} requires the full-download adapter; slot availability cannot be inferred')
                for i in range(len(parquet.schema)):
                    path=parquet.schema.column(i).path
                    if path.split('.')[0] not in media or path.endswith('.path'):columns.append(path)
                groups=[parquet.metadata.row_group(i).num_rows for i in range(parquet.num_row_groups)]
                self._layouts[index]=(schema,media,columns,groups)
        return self._layouts[index]

    @property
    def count(self):return sum(sum(self._layout(i)[3]) for i in range(len(self.files)))

    def source_field_types(self):
        types={'_atlas_origin':{'object'}}
        for i in range(len(self.files)):
            schema,media,_,_=self._layout(i)
            for field in schema:
                dtype=field.type
                if pa.types.is_null(dtype):continue
                kind=('array' if pa.types.is_list(dtype) or pa.types.is_large_list(dtype) else 'boolean' if pa.types.is_boolean(dtype)
                      else 'number' if pa.types.is_floating(dtype) or (pa.types.is_integer(dtype) and dtype.bit_width<=32)
                      else 'string' if pa.types.is_string(dtype) or pa.types.is_large_string(dtype) else 'object')
                types.setdefault(field.name,set()).add(kind)
        return {name:next(iter(kinds)) if len(kinds)==1 else 'object' for name,kinds in types.items()}

    def _record(self,row,file_index,row_index):
        if '_atlas_origin' in row:raise ValueError('Source collides with reserved provenance field')
        _,media,_,_=self._layout(file_index);entry=self.files[file_index];row=dict(row);assets=[]
        for column,is_list in media.items():
            value=row.get(column)
            if value is None:continue
            values=value if is_list else [value]
            descriptors=[]
            for slot,item in enumerate(values):
                if item is None:
                    descriptors.append(None);continue
                ref=f'remote/{file_index}/{row_index}/{column}/{slot}.png'
                origin={'source_path':item.get('path'),'representation':'original embedded image on request','availability':'unchecked embedded bytes',
                        'source_file':entry['source_name'],'source_row':row_index,'source_field':column,'source_slot':slot,'source_etag':entry['etag']}
                assets.append(Asset(id=stable_id(self.dataset.id,self.revision,'asset',ref),dataset_id=self.dataset.id,release_id=self.revision,
                                    modality='image',uri=ref,metadata=origin))
                descriptors.append(origin)
            row[column]=descriptors if is_list else descriptors[0] if descriptors else None
        self.config['mapping']={**self.config.get('mapping',{}),'id':None,'media':None}
        for key,candidates in {'text':['text','sentence','caption','content'],'question':['question','Question'],'choices':['choices','options']}.items():
            if self.config['mapping'].get(key) not in row:self.config['mapping'][key]=next((name for name in candidates if name in row),None)
        record=DatasetAdapter._record(self,row,f'{entry["source_name"]}:{row_index}')
        record.assets=assets;record.asset_ids=[a.id for a in assets]
        record.source['_atlas_origin']={'file':entry['source_name'],'row':row_index,'upstream_sha256':entry['sha256'],
            'etag':entry['etag'],'integrity':'Strong ETag-bound ranges; full shard SHA-256 not computed locally.'}
        return record

    @staticmethod
    def _prefetch_metadata(parquet, group, columns):
        # Selected column chunks are contiguous in common multimodal shards.
        # Merge touching intervals only: skipped image bytes are never included.
        metadata=parquet.metadata.row_group(group);selected=set(columns);ranges=[]
        for index in range(metadata.num_columns):
            column=metadata.column(index)
            if column.path_in_schema not in selected:continue
            offsets=[offset for offset in (column.dictionary_page_offset,column.data_page_offset) if offset is not None and offset>=0]
            if not offsets:raise ValueError('Parquet column has no page offset')
            start=min(offsets);end=start+column.total_compressed_size
            if end>start:ranges.append((start,end))
        merged=[]
        for start,end in sorted(ranges):
            if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],end))
            else:merged.append((start,end))
        parquet._atlas_buffer.prefetch(merged)

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0);size=min(limit or source.limit,source.limit)
        if start<0:raise ValueError('Negative cursor')
        offset=0;records=[]
        for index in range(len(self.files)):
            _,_,columns,groups=self._layout(index);count=sum(groups)
            if offset+count<=start:offset+=count;continue
            with self._parquet(index) as parquet:
                group_start=0
                for group,count in enumerate(groups):
                    if offset+group_start+count<=start:group_start+=count;continue
                    self._prefetch_metadata(parquet,group,columns)
                    batch_start=group_start
                    for batch in parquet.iter_batches(batch_size=1000,row_groups=[group],columns=columns):
                        skip=max(0,start-offset-batch_start)
                        if skip<batch.num_rows:
                            rows=batch.slice(skip,min(size-len(records),batch.num_rows-skip)).to_pylist()
                            for local,row in enumerate(rows,batch_start+skip):
                                record=self._record(row,index,local);source.charge(len(record.model_dump_json().encode()));records.append(record)
                        batch_start+=batch.num_rows
                        if len(records)==size:break
                    group_start+=count
                    if len(records)==size:break
            offset+=sum(groups)
            if len(records)==size:break
        end=start+len(records)
        return RecordBatch(records,str(end) if end<self.count else None,len(records))

    def resolve_asset(self,source,asset_ref):
        match=re.fullmatch(r'remote/(\d+)/(\d+)/([A-Za-z_][A-Za-z_0-9]*)/(\d+)\.png',asset_ref)
        if not match:raise ValueError('Invalid remote Parquet image reference')
        index,row,column,slot=int(match[1]),int(match[2]),match[3],int(match[4])
        if index>=len(self.files):raise ValueError('Remote shard outside declared population')
        _,media,_,groups=self._layout(index)
        if column not in media:raise ValueError('Unknown remote media column')
        offset=0
        for group,count in enumerate(groups):
            if row<offset+count:break
            offset+=count
        else:raise ValueError('Remote media row outside declared population')
        with self._parquet(index,budget=self.config.get('media_transfer_bytes',250_000_000)) as parquet:
            metadata=parquet.metadata.row_group(group)
            media_bytes=sum(metadata.column(i).total_compressed_size for i in range(metadata.num_columns) if metadata.column(i).path_in_schema.split('.')[0]==column)
            decoded_bytes=sum(metadata.column(i).total_uncompressed_size for i in range(metadata.num_columns) if metadata.column(i).path_in_schema.split('.')[0]==column)
            if decoded_bytes>self.config.get('media_decode_bytes',512_000_000):raise ValueError('Image row group exceeds decoded memory budget')
            if media_bytes>self.config.get('media_transfer_bytes',250_000_000):raise ValueError('Image row group exceeds media transfer budget; mount or download this shard')
            value=parquet.read_row_group(group,columns=[column]).slice(row-offset,1).to_pylist()[0][column]
        values=value if media[column] else [value]
        if values is None or slot>=len(values) or not values[slot] or not values[slot].get('bytes'):raise FileNotFoundError('Source has no embedded image bytes for this slot')
        data=values[slot]['bytes'];source.charge(len(data));_,mime=_encoding(data)
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('Embedded image exceeds pixel budget')
            image.verify()
        return MediaHandle(data,mime,hashlib.sha256(data).hexdigest(),asset_ref)
