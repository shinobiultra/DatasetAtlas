"""Complete native corruption populations over verified original TAR indices."""
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3

from PIL import Image

from .core import DatasetAdapter,SourceDescription,RecordBatch,MediaHandle
from dataset_atlas.storage import BoundedCache
from dataset_atlas.storage.indexed_tar import read_tar_member


class ImageNetCAdapter(DatasetAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.indices=[Path(value) for value in self.config.get('indices',[])]
        self.bytes_fetched=0
        self.preparation_transfer_limit: int | None=None
        self._count=None
        self._counts=[]

    def probe(self):
        present=bool(self.indices) and all((path/'receipt.json').is_file() for path in self.indices)
        return SourceDescription('indexed native ImageNet-C',str(self.indices[0]) if self.indices else 'unprepared native TARs',present,
            self.revision,None,True,True,True,True,True,('Original members verified through whole-block SHA-256 HTTPS ranges.',))

    @property
    def count(self):
        if self._count is None:
            total=0
            for path in self.indices:
                with sqlite3.connect((path/'members.sqlite').as_uri()+'?mode=ro',uri=True) as db:
                    count=db.execute("SELECT count(*) FROM members WHERE name LIKE '%.JPEG'").fetchone()[0]
                    self._counts.append(count);total+=count
            self._count=total
        return self._count

    def _native_record(self,path,receipt,name,size,sha):
        match=re.fullmatch(r'([^/]+)/([1-5])/(n[0-9]{8})/([^/]+\.JPEG)',name)
        if not match:raise ValueError('Native corruption/class/severity path changed')
        corruption,severity,wnid,filename=match.groups()
        ref=path.name+'/'+name
        row={'source_id':ref,'archive':path.name,'member':name,'corruption':corruption,
             'severity':int(severity),'class_wnid':wnid,'source_filename':filename,
             'bytes':size,'sha256':sha,'source_archive_sha256':receipt['source_sha256'],'media_ref':ref}
        record=self._record(row,ref)
        for asset in record.assets:
            asset.sha256=sha
            asset.metadata.update(representation='original corruption JPEG',original_bytes=size,
                source_integrity='Complete native archive and member SHA-256; fetched compressed blocks are SHA-256 checked.')
        return record

    def _records(self,source,start=0,limit=None):
        self.count
        for path in self.indices:
            count=self._counts[self.indices.index(path)]
            if start>=count:start-=count;continue
            receipt=json.loads((path/'receipt.json').read_text())
            with sqlite3.connect((path/'members.sqlite').as_uri()+'?mode=ro',uri=True) as db:
                query="SELECT name,bytes,sha256 FROM members WHERE name LIKE '%.JPEG' ORDER BY offset LIMIT ? OFFSET ?"
                for name,size,sha in db.execute(query,(-1 if limit is None else limit,start)):
                    record=self._native_record(path,receipt,name,size,sha)
                    source.charge(len(record.model_dump_json().encode()))
                    yield record
                    if limit is not None:
                        limit-=1
                        if limit==0:return
            start=0

    def iter_sequential(self,source):
        yield from self._records(source)

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative cursor')
        size=min(limit or source.limit,source.limit)
        if size<1:raise ValueError('Positive page size required')
        records=list(self._records(source,start,size))
        end=start+len(records)
        return RecordBatch(records,str(end) if end<self.count else None,len(records))

    def resolve_asset(self,source,asset_ref):
        parts=asset_ref.split('/',1)
        index=next((path for path in self.indices if path.name==parts[0]),None)
        if index is None or len(parts)!=2:raise ValueError('Unknown native corruption archive')
        limit=self.config.get('media_transfer_bytes',64_000_000)
        if self.preparation_transfer_limit is not None:limit=min(limit,self.preparation_transfer_limit-self.bytes_fetched)
        if limit<1:raise ValueError('Native original transfer budget exhausted')
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',200_000_000))
        data,proof=read_tar_member(index,parts[1],max_bytes=source.max_bytes-source.bytes_read,transfer_bytes=limit,cache=cache)
        self.bytes_fetched+=proof['transferred_bytes']
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('Original corruption image exceeds pixel budget')
            image.verify()
        source.charge(len(data))
        return MediaHandle(data,'image/jpeg',hashlib.sha256(data).hexdigest(),asset_ref)
