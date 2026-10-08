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


class MediaLimitError(ValueError):
    """A particular source image cannot be inspected within the media limits."""


class RemoteColumnarAdapter(DatasetAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        import copy
        self.config=copy.deepcopy(dataset.adapter_config)
        self.files=self.config['remote_files']
        if not self.files:raise ValueError('Remote Parquet files are required')
        self.bytes_fetched=0
        self.media_bytes_fetched=0
        self.transfer_limit=self.config.get('metadata_transfer_bytes',100_000_000)
        self.cancel=None
        self.cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',1_000_000_000))
        self._layouts={}
        # Compressed bytes per row group: (selected non-media columns, media columns).
        self._group_bytes={}
        self._binary_media={}

    def probe(self):
        return SourceDescription('remote_columnar',self.files[0]['url'],True,self.revision,sum(f['bytes'] for f in self.files),
            True,True,True,False,True,('Complete annotations indexed through HTTPS ranges; embedded images fetched on inspection.',))

    @contextmanager
    def _parquet(self,index,budget=None):
        entry=self.files[index]
        limit=budget if budget is not None else self.transfer_limit-self.bytes_fetched
        if self.config.get('aggregate_transfer_bytes') is not None:
            limit=min(limit,self.config['aggregate_transfer_bytes']-self.bytes_fetched-self.media_bytes_fetched)
        if limit<=0:raise ValueError('Remote metadata transfer budget exhausted')
        with HttpsRangeReader(entry['url'],size=entry['bytes'],etag=entry['etag'],allowed_hosts=self.config['allowed_hosts'],
                              byte_budget=limit,cache=self.cache,cancel=self.cancel,credential_profile=self.config.get('credential_profile')) as source:
            try:
                # Disable speculative reads spanning omitted image columns.
                buffer=SmallReadBuffer(source) if budget is None else source
                parquet=pq.ParquetFile(buffer,pre_buffer=False,buffer_size=0)
                parquet._atlas_buffer=buffer  # ty: ignore[unresolved-attribute]
                yield parquet
            finally:
                if budget is None:self.bytes_fetched+=source.bytes_fetched
                else:self.media_bytes_fetched+=source.bytes_fetched

    def _layout(self,index):
        if index not in self._layouts:
            with self._parquet(index) as parquet:
                schema=parquet.schema_arrow;media={};columns=[];binary=set()
                for field in schema:
                    dtype=field.type;is_list=pa.types.is_list(dtype) or pa.types.is_large_list(dtype)
                    if is_list:dtype=dtype.value_type
                    if pa.types.is_struct(dtype) and 'bytes' in [f.name for f in dtype]:
                        if 'path' not in [f.name for f in dtype]:raise ValueError(f'Remote media column {field.name} needs a path leaf to preserve slots without reading bytes')
                        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',field.name):raise ValueError('Remote media field name is unsupported')
                        media[field.name]=is_list
                    elif pa.types.is_binary(dtype) or pa.types.is_large_binary(dtype):
                        declared=self.config.get('media_columns',[self.config.get('mapping',{}).get('media','image')])
                        if field.name not in declared:
                            raise ValueError(f'Remote binary column {field.name} must be declared in media_columns')
                        media[field.name]=is_list;binary.add(field.name)
                    elif (pa.types.is_string(dtype) or pa.types.is_large_string(dtype)) and self.config.get('media_encoding')=='base64':
                        declared=self.config.get('media_columns',[])
                        if field.name in declared:media[field.name]=is_list;binary.add(field.name)
                for i in range(len(parquet.schema)):
                    path=parquet.schema.column(i).path
                    if path.split('.')[0] not in media or path.endswith('.path') or path.split('.')[0] in binary:columns.append(path)
                groups=[parquet.metadata.row_group(i).num_rows for i in range(parquet.num_row_groups)]
                selected=set(columns);sizes=[]
                for i in range(parquet.num_row_groups):
                    group=parquet.metadata.row_group(i)
                    chunks=[group.column(c) for c in range(group.num_columns)]
                    sizes.append((sum(c.total_compressed_size for c in chunks if c.path_in_schema in selected),
                                  sum(c.total_compressed_size for c in chunks if c.path_in_schema.split('.')[0] in media)))
                self._group_bytes[index]=sizes
                self._binary_media[index]=binary
                self._layouts[index]=(schema,media,columns,groups)
        return self._layouts[index]

    def group_bytes(self,index):
        """Compressed (annotation, media) bytes of each row group in one shard."""
        self._layout(index)
        return self._group_bytes[index]

    @property
    def count(self):return sum(sum(self._layout(i)[3]) for i in range(len(self.files)))

    def warm_layouts(self, progress=None, workers=8):
        """Read independent footers concurrently under one aggregate byte cap."""
        from concurrent.futures import ThreadPoolExecutor
        if type(workers) is not int or not 1 <= workers <= 8:
            raise ValueError('Remote schema concurrency must be within 1..8')
        missing=[index for index in range(len(self.files)) if index not in self._layouts]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for start in range(0,len(missing),workers):
                if self.cancel:self.cancel()
                batch=missing[start:start+workers]
                # Each reader owns an equal reservation. Their combined network
                # reads cannot exceed the remaining transfer budget, even on error.
                allowance=(self.transfer_limit-self.bytes_fetched)//len(batch)
                if allowance<=0:raise ValueError('Remote metadata transfer budget exhausted')
                def read(index):
                    config={**self.config,'remote_files':[self.files[index]],'metadata_transfer_bytes':allowance}
                    child=RemoteColumnarAdapter(self.dataset.model_copy(update={'adapter_config':config}))
                    child.cancel=self.cancel
                    try:return index,(child._layout(0),child._group_bytes[0],child._binary_media[0]),child.bytes_fetched,None
                    except Exception as error:return index,None,child.bytes_fetched,error
                results=list(pool.map(read,batch))
                self.bytes_fetched+=sum(result[2] for result in results)
                for index,layout,_,error in results:
                    if error is not None:raise error
                    self._layouts[index],self._group_bytes[index],self._binary_media[index]=layout
                    if progress:progress(schema_shards=len(self._layouts),total_shards=len(self.files),downloaded_bytes=self.bytes_fetched)

    def source_field_types(self):
        types={'_atlas_origin':{'object'}}
        if self.config.get('mapping', {}).get('configuration_from_path'):
            types['_atlas_configuration']={'string'}
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

    def _metadata_table(self,table,file_index):
        """Keep binary-list slot counts and nulls without copying image bytes into Python."""
        for column in self._binary_media.get(file_index,set()):
            values=[]
            is_list=self._layout(file_index)[1][column]
            for scalar in table[column]:
                if not scalar.is_valid:values.append(None)
                elif is_list:values.append([{'path':None} if item.is_valid else None for item in scalar.values])
                else:values.append({'path':None})
            replacement=pa.array(values,type=pa.list_(pa.struct([('path',pa.string())])) if is_list else pa.struct([('path',pa.string())]))
            table=table.set_column(table.schema.get_field_index(column),column,replacement)
        return table

    def _source_record(self,row,file_index,row_index):
        if any(name in row for name in ('_atlas_origin','_atlas_configuration')):raise ValueError('Source collides with reserved provenance field')
        _,media,_,_=self._layout(file_index);entry=self.files[file_index];row=dict(row);assets=[]
        for column,is_list in media.items():
            value=row.get(column)
            if value is None:continue
            values=value if is_list else [value]
            descriptors=[]
            for slot,item in enumerate(values):
                if item is None:
                    descriptors.append(None);continue
                ref=f'remote/{file_index+self.config.get("file_index_offset",0)}/{row_index}/{column}/{slot}.png'
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
        pair_column=self.config['mapping'].get('conversation_pairs')
        if pair_column:
            pairs=row.get(pair_column)
            if not isinstance(pairs,list) or any(not isinstance(pair,dict) or
                not isinstance(pair.get('user'),str) or not isinstance(pair.get('assistant'),str) for pair in pairs):
                raise ValueError(f'Invalid user/assistant pairs in source column {pair_column}')
            record.conversation=[message for pair in pairs for message in (
                {'role':'user','content':pair['user']}, {'role':'assistant','content':pair['assistant']})]
            if pairs:record.question=pairs[0]['user']
        if self.config['mapping'].get('configuration_from_path'):
            configuration,separator,_=entry['source_name'].partition('/')
            if not separator:raise ValueError('Source has no configuration directory')
            record.source['_atlas_configuration']=configuration
        record.source['_atlas_origin']={'file':entry['source_name'],'row':row_index,'upstream_sha256':entry['sha256'],
            'etag':entry['etag'],'integrity':'Strong ETag-bound ranges; full shard SHA-256 not computed locally.'}
        return record

    @staticmethod
    def _prefetch_metadata(parquet, group, columns):
        # Selected column chunks are contiguous in common multimodal shards.
        # Small gaps between annotation pages can be fetched in one request;
        # never bridge an omitted column, even when it is small.
        metadata=parquet.metadata.row_group(group);selected=set(columns);ranges=[];omitted=[]
        for index in range(metadata.num_columns):
            column=metadata.column(index)
            offsets=[offset for offset in (column.dictionary_page_offset,column.data_page_offset) if offset is not None and offset>=0]
            if not offsets:raise ValueError('Parquet column has no page offset')
            start=min(offsets);end=start+column.total_compressed_size
            if end>start:
                (ranges if column.path_in_schema in selected else omitted).append((start,end))
        merged=[]
        for start,end in sorted(ranges):
            if merged and start-merged[-1][1]<=4096 and not any(left<start and right>merged[-1][1] for left,right in omitted):
                merged[-1]=(merged[-1][0],max(merged[-1][1],end))
            else:merged.append((start,end))
        parquet._atlas_buffer.prefetch(merged)

    def records_at(self,source,targets):
        """Records at explicit (file index, row group, row within group) positions.

        Each touched row group is read once, annotation columns only; embedded
        image bytes stay remote until an asset is resolved."""
        wanted={}
        for file_index,group,row in targets:
            if not 0<=file_index<len(self.files):raise ValueError('Remote shard outside declared population')
            groups=self._layout(file_index)[3]
            if not 0<=group<len(groups) or not 0<=row<groups[group]:raise ValueError('Remote row outside declared population')
            wanted.setdefault((file_index,group),set()).add(row)
        found={}
        for file_index in sorted({key[0] for key in wanted}):
            _,_,columns,groups=self._layout(file_index)
            with self._parquet(file_index) as parquet:
                for (_,group),rows in sorted((key,value) for key,value in wanted.items() if key[0]==file_index):
                    if self.cancel:self.cancel()
                    first=sum(groups[:group])
                    self._prefetch_metadata(parquet,group,columns)
                    table=parquet.read_row_group(group,columns=columns)
                    for row in sorted(rows):
                        record=self._source_record(self._metadata_table(table.slice(row,1),file_index).to_pylist()[0],file_index,first+row)
                        source.charge(len(record.model_dump_json().encode()))
                        found[(file_index,group,row)]=record
                    del table
        return [found[target] for target in targets]

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
                            rows=self._metadata_table(pa.Table.from_batches([batch.slice(skip,min(size-len(records),batch.num_rows-skip))]),index).to_pylist()
                            for local,row in enumerate(rows,batch_start+skip):
                                record=self._source_record(row,index,local);source.charge(len(record.model_dump_json().encode()));records.append(record)
                        batch_start+=batch.num_rows
                        if len(records)==size:break
                    group_start+=count
                    if len(records)==size:break
            offset+=sum(groups)
            if len(records)==size:break
        end=start+len(records)
        return RecordBatch(records,str(end) if end<self.count else None,len(records))

    def iter_all_records(self, source, workers=4):
        """Overlap shard I/O while yielding the exact original source order.

        Each producer buffers at most 32 MB of encoded records in at most 32
        batches. Each wave reserves disjoint shares of the network allowance.
        These are buffer limits, not a bound on decoded Python process memory.
        """
        from concurrent.futures import ThreadPoolExecutor
        from queue import Queue, Empty, Full
        from threading import Event, Condition
        class BufferedQueue(Queue):
            def __init__(self):
                super().__init__(maxsize=32)
                self.credit=Condition()
                self.buffered=0
        if type(workers) is not int or not 1 <= workers <= 4:
            raise ValueError('Remote record concurrency must be within 1..4')
        stop=Event()
        def check():
            if stop.is_set():raise InterruptedError('Remote shard iteration stopped')
            if self.cancel:self.cancel()
        def put(queue, value):
            records,fetched,error=value
            sizes=[len(record.model_dump_json().encode()) for record in records] if records else []
            if any(size>32_000_000 for size in sizes):raise ValueError('Remote record exceeds 32 MB buffer limit')
            if sum(sizes)>32_000_000:
                chunk=[];used=0
                for record,size in zip(records,sizes):
                    if chunk and used+size>32_000_000:
                        put(queue,(chunk,fetched,None));fetched=0;chunk=[];used=0
                    chunk.append(record);used+=size
                if chunk:put(queue,(chunk,fetched,error))
                return
            encoded_size=sum(sizes)
            with queue.credit:
                while queue.buffered+encoded_size>32_000_000 and not stop.is_set():
                    queue.credit.wait(.1)
                if stop.is_set():return
                queue.buffered+=encoded_size
            while not stop.is_set():
                try:queue.put((records,fetched,error,encoded_size),timeout=.1);return
                except Full:continue
        def read(index, allowance, queue):
            child=None;reported=0
            try:
                config={**self.config,'remote_files':[self.files[index]],'file_index_offset':index,
                        'metadata_transfer_bytes':allowance}
                child=RemoteColumnarAdapter(self.dataset.model_copy(update={'adapter_config':config}))
                child.cancel=check
                child._layouts[0]=self._layout(index)
                child._binary_media[0]=self._binary_media.get(index,set())
                prepared=child.prepare(child.plan(1000,source.max_bytes))
                cursor=None
                while True:
                    check()
                    batch=child.iter_records(prepared,cursor,1000)
                    put(queue,(batch.records,child.bytes_fetched-reported,None))
                    reported=child.bytes_fetched
                    if not batch.next_cursor:break
                    if cursor==batch.next_cursor:raise ValueError('Remote shard repeated cursor')
                    cursor=batch.next_cursor
                put(queue,(None,child.bytes_fetched-reported,None))
            except Exception as error:
                put(queue,(None,(child.bytes_fetched if child else 0)-reported,error))
        # Populate shared layouts before threads access them.
        self.warm_layouts()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            try:
                for start in range(0,len(self.files),workers):
                    check()
                    indices=list(range(start,min(start+workers,len(self.files))))
                    allowance=(self.transfer_limit-self.bytes_fetched)//len(indices)
                    if allowance<=0:raise ValueError('Remote metadata transfer budget exhausted')
                    queues=[BufferedQueue() for _ in indices]
                    futures=[pool.submit(read,index,allowance,queue) for index,queue in zip(indices,queues)]
                    for queue in queues:
                        while True:
                            check()
                            try:records,fetched,error,encoded_size=queue.get(timeout=.1)
                            except Empty:continue
                            with queue.credit:
                                queue.buffered-=encoded_size
                                queue.credit.notify_all()
                            self.bytes_fetched+=fetched
                            if error is not None:raise error
                            if records is None:break
                            for record in records:
                                source.charge(len(record.model_dump_json().encode()))
                                yield record
                    for future in futures:future.result()
            finally:stop.set()

    def resolve_original_asset(self,source,asset_ref):
        """Bounded native bytes, before the separate display/processor pixel check."""
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
            if media_bytes>self.config.get('media_transfer_bytes',250_000_000):raise ValueError('Image row group exceeds media transfer budget; mount or download this shard')
            # Large native row groups need not become one decoded table. Arrow
            # reads column pages under the worker's RSS cap; each exposed batch
            # has its own decoded-byte bound, and only the requested row enters
            # Python. This does not claim a hard bound on Arrow's internal buffers.
            remaining=row-offset
            value=None
            for batch in parquet.iter_batches(batch_size=8,row_groups=[group],columns=[column]):
                if batch.nbytes>self.config.get('media_decode_bytes',512_000_000):raise MediaLimitError('Image batch exceeds decoded memory budget')
                if remaining<batch.num_rows:
                    value=batch.slice(remaining,1).to_pylist()[0][column];break
                remaining-=batch.num_rows
        values=value if media[column] else [value]
        if values is None or slot>=len(values) or not values[slot]:raise FileNotFoundError('Source has no embedded image bytes for this slot')
        item=values[slot]
        if isinstance(item,bytes):data=item
        elif isinstance(item,dict):data=item.get('bytes')
        elif isinstance(item,str) and self.config.get('media_encoding')=='base64':
            import base64,binascii
            remaining=source.max_bytes-source.bytes_read
            if len(item)>((remaining+2)//3)*4:raise MediaLimitError('Base64 original exceeds the decoded-byte budget')
            try:data=base64.b64decode(item,validate=True)
            except (binascii.Error,ValueError):raise ValueError('Native image base64 encoding is invalid') from None
        else:raise ValueError('Embedded image slot has invalid type')
        if not data:raise FileNotFoundError('Source has no embedded image bytes for this slot')
        source.charge(len(data));_,mime=_encoding(data)
        return MediaHandle(data,mime,hashlib.sha256(data).hexdigest(),asset_ref)

    def resolve_asset(self,source,asset_ref):
        original=self.resolve_original_asset(source,asset_ref)
        with Image.open(io.BytesIO(original.data)) as image:
            if image.width*image.height>50_000_000:raise MediaLimitError('Embedded image exceeds pixel budget')
            image.verify()
        return original
