"""Reproduce existing retained visual tables from checksum-pinned native releases."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import RowDigest, converter, file_sha256
from dataset_atlas.adapters.embedded_parquet import _encoding


def output_limit(params, runtime_limit):
    declared=params.get('max_output_bytes',1_000_000_000)
    if type(declared) is not int or not 1<=declared<=1_000_000_000_000:
        raise ValueError('A bounded conversion output declaration is required')
    if runtime_limit is not None and (type(runtime_limit) is not int or runtime_limit<1):
        raise ValueError('Conversion output reservation is exhausted')
    return min(declared,runtime_limit) if runtime_limit is not None else declared


class BoundedOutput(io.BufferedWriter):
    def __init__(self,path,maximum):
        super().__init__(io.FileIO(path,'w'))
        self.maximum=maximum

    def write(self,data):
        if self.tell()+len(data)>self.maximum:
            raise ValueError('Converted bytes exceed the remaining output reservation')
        return super().write(data)


def binary_fingerprint(value):
    """Canonical row evidence retains binary identity without JSON-encoding pixels."""
    if isinstance(value, bytes):
        return {'_atlas_binary_sha256':hashlib.sha256(value).hexdigest(),'_atlas_binary_bytes':len(value)}
    if isinstance(value, dict):return {key:binary_fingerprint(item) for key,item in value.items()}
    if isinstance(value, list):return [binary_fingerprint(item) for item in value]
    return value


def parquet_row_digest(path):
    digest=RowDigest()
    for batch in pq.ParquetFile(path).iter_batches(batch_size=32):
        for row in batch.to_pylist():digest.add(binary_fingerprint(row))
    return {'count':digest.count,'rows_sha256':digest.hexdigest()}


@converter('retained_visual_parquet', bounded_output=True)
def retained_visual_parquet(params, inputs, output_dir, check, *, max_output_bytes=None):
    """Preserve the established BLINK / RealWorldQA / SB table and image identities."""
    maximum=output_limit(params,max_output_bytes)
    mode=params['mode'];sources=params['sources']
    if mode not in {'blink','realworldqa','sbbench_concat'} or not isinstance(sources,list) or not sources:
        raise ValueError('A supported retained table mode and ordered native sources are required')
    keys=[entry['key'] for entry in sources]
    if len(set(keys))!=len(keys) or set(keys)!=set(inputs):raise ValueError('Native source inventory must account for every input exactly once')
    output=Path(output_dir)/'records.parquet';output.parent.mkdir(parents=True,exist_ok=True)
    digest=RowDigest();seen=set();writer=None
    if mode=='blink':
        image=pa.struct([pa.field('bytes',pa.binary()),pa.field('path',pa.string())])
        schema=pa.schema([('source_id',pa.string()),('task',pa.string()),('split',pa.string()),
            ('source_file',pa.string()),('idx',pa.string()),('question',pa.string()),('sub_task',pa.string()),
            ('choices',pa.list_(pa.string())),('answer',pa.string()),('prompt',pa.string()),
            ('explanation',pa.string()),('source_image_columns',pa.list_(pa.string())),('images',pa.list_(image))])
    else:schema=None
    sink=BoundedOutput(output,maximum)
    try:
        for source_index,entry in enumerate(sources):
            check();parquet=pq.ParquetFile(inputs[entry['key']]);offset=0
            for batch in parquet.iter_batches(batch_size=32 if mode=='blink' else 8):
                check();native=batch.to_pylist();rows=[]
                if mode=='blink':
                    task,filename=entry['native_path'].split('/',1);split=filename.split('-',1)[0]
                    if split not in {'test','val'}:raise ValueError('Unexpected native BLINK split')
                    for row in native:
                        images=[];columns=[]
                        for column in ('image_1','image_2','image_3','image_4'):
                            item=row.get(column)
                            if item is None:continue
                            data=item.get('bytes')
                            if (not isinstance(data,bytes) or not 1<=len(data)<=10_000_000
                                or not data.startswith((b'\xff\xd8\xff',b'\x89PNG\r\n\x1a\n'))):
                                raise ValueError('BLINK native image is missing, oversized or unsupported')
                            images.append(item);columns.append(column)
                        if not 1<=len(images)<=4:raise ValueError('BLINK rows require their original 1-4 images')
                        identity=f"{task}:{split}:{row['idx']}"
                        if identity in seen:raise ValueError('Duplicate native BLINK identity')
                        seen.add(identity)
                        rows.append({'source_id':identity,'task':task,'split':split,'source_file':entry['native_path'],
                            'idx':row['idx'],'question':row['question'],'sub_task':row['sub_task'],'choices':row['choices'],
                            'answer':row['answer'],'prompt':row['prompt'],'explanation':row['explanation'],
                            'source_image_columns':columns,'images':images})
                    table=pa.Table.from_pylist(rows,schema=schema)
                else:
                    table=pa.Table.from_batches([batch]);length=table.num_rows
                    if mode=='realworldqa':
                        table=table.append_column('source_id',pa.array([f'{source_index}:{offset+i}' for i in range(length)]))
                    table=table.append_column('source_shard',pa.array([Path(entry['native_path']).name]*length))
                    table=table.append_column('source_row',pa.array(range(offset,offset+length),type=pa.int64()))
                    rows=table.to_pylist();offset+=length
                if writer is None:
                    writer=pq.ParquetWriter(sink,table.schema,compression='zstd',
                        **({'compression_level':5} if mode=='blink' else {}))
                writer.write_table(table)
                for row in rows:digest.add(binary_fingerprint(row))
    finally:
        try:
            if writer is not None:writer.close()
        finally:sink.close()
    if not digest.count:raise ValueError('Native visual table is empty')
    return {'path':output,'format':'parquet','count':digest.count,'rows_sha256':digest.hexdigest(),
            'file_sha256':file_sha256(output)}


@converter('retained_visual_image_jsonl', bounded_output=True)
def retained_visual_image_jsonl(params, inputs, output_dir, check, *, max_output_bytes=None):
    """Retain canonical metadata; read original image bytes lazily from their Parquet."""
    if set(inputs)!={'source'}:raise ValueError('One pinned native visual Parquet is required')
    maximum=output_limit(params,max_output_bytes)
    output=Path(output_dir)/'records.jsonl';output.parent.mkdir(parents=True,exist_ok=True)
    digest=RowDigest();media_rows={};written=0;ordinal=0
    with output.open('wb') as stream:
        for batch in pq.ParquetFile(inputs['source']).iter_batches(batch_size=32):
            for native in batch.to_pylist():
                check();row=dict(native);image=row.pop('image');data=image.get('bytes') if image else None
                if not isinstance(data,bytes) or not 1<=len(data)<=10_000_000:raise ValueError('Native image is absent or exceeds 10 MB')
                extension,_=_encoding(data)
                if extension not in {'jpg','png','webp'}:raise ValueError('Unsupported retained source image encoding')
                sha=hashlib.sha256(data).hexdigest();relative='images/'+sha+'.'+extension
                media_rows.setdefault(relative,ordinal);ordinal+=1
                row['source_image_path']=image.get('path');row['media_path']=relative;row['image_sha256']=sha
                encoded=(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode()
                if written+len(encoded)>maximum:raise ValueError('Converted bytes exceed the remaining output reservation')
                stream.write(encoded);written+=len(encoded)
                digest.add(row)
    return {'path':output,'format':'jsonl','count':digest.count,'rows_sha256':digest.hexdigest(),
            'file_sha256':file_sha256(output),'adapter_config':{'media_root':None,
                'original_parquet_path':str(inputs['source']),'original_parquet_sha256':file_sha256(inputs['source']),
                'original_parquet_bytes':Path(inputs['source']).stat().st_size,
                'original_image_column':'image','original_media_rows':media_rows}}
