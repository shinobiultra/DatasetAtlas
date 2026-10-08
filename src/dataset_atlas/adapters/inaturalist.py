"""Native iNaturalist challenge taxonomy and image originals over checked TARs."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3

from PIL import Image

from .core import DatasetAdapter,SourceDescription,RecordBatch,MediaHandle,_safe_relative
from dataset_atlas.storage import BoundedCache
from dataset_atlas.storage.indexed_tar import read_tar_member


class INaturalistAdapter(DatasetAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.indices={Path(value).name:Path(value) for value in self.config.get('indices',[])}
        self.bytes_fetched=0
        self.preparation_transfer_limit: int | None=None
        self._native=None
        self._joined=None

    def probe(self):
        names=[self.config.get('annotation_archive_name'),self.config.get('image_archive_name')]
        present=all(name in self.indices and (self.indices[name]/'receipt.json').is_file() for name in names)
        return SourceDescription('native iNaturalist archive annotations','pinned native challenge TARs',present,
            self.revision,None,True,True,True,True,True,('Per-image native licences and complete taxonomy are preserved.',))

    def prepare(self,approved_plan):
        source=super().prepare(approved_plan)
        for index in self.indices.values():
            receipt=json.loads((index/'receipt.json').read_text())
            for name,digest in receipt['checksums'].items():
                with (index/name).open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:raise ValueError('Native iNaturalist index checksum changed')
        return source

    def _read(self,index,member,max_bytes):
        remaining=self.config.get('media_transfer_bytes',100_000_000)
        if self.preparation_transfer_limit is not None:remaining=min(remaining,self.preparation_transfer_limit-self.bytes_fetched)
        if remaining<1:raise ValueError('Native iNaturalist aggregate transfer budget exhausted')
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',200_000_000))
        data,proof=read_tar_member(index,member,max_bytes=max_bytes,transfer_bytes=remaining,cache=cache)
        self.bytes_fetched+=proof['transferred_bytes']
        return data,proof

    def _population(self):
        if self._joined is not None:return self._joined
        native,proof=self._read(self.indices[self.config['annotation_archive_name']],self.config['annotation_member'],80_000_000)
        document=json.loads(native)
        if not isinstance(document,dict) or set(document)!={'info','images','categories','annotations','licenses'}:
            raise ValueError('Native iNaturalist annotation topology changed')
        def keyed(name):
            entries=document[name]
            if not isinstance(entries,list) or len(entries)>1_000_000:raise ValueError('Native annotation list exceeds the declared bound')
            result={}
            for item in entries:
                if not isinstance(item,dict) or type(item.get('id')) is not int or item['id'] in result:raise ValueError('Missing or duplicate native annotation identity')
                result[item['id']]=item
            return result
        images=keyed('images');categories=keyed('categories');licenses=keyed('licenses');annotations=keyed('annotations')
        by_image={}
        for annotation in annotations.values():
            identity=annotation.get('image_id')
            if identity not in images or identity in by_image or annotation.get('category_id') not in categories:
                raise ValueError('Native annotation join is missing, duplicate or orphaned')
            by_image[identity]=annotation
        if set(by_image)!=set(images):raise ValueError('Native image lacks its taxonomy annotation')
        index=self.indices[self.config['image_archive_name']]
        with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            members={name:(size,sha) for name,size,sha in db.execute("SELECT name,bytes,sha256 FROM members WHERE lower(name) LIKE '%.jpg'")}
        rows=[];used=set()
        for image in document['images']:
            filename=_safe_relative(image.get('file_name',''))
            if filename not in members or filename in used or image.get('license') not in licenses:
                raise ValueError('Native image archive or licence join differs from annotations')
            annotation=by_image[image['id']];size,sha=members[filename];used.add(filename)
            rows.append({'source_id':str(image['id']),'image':image,'annotation':annotation,
                'category':categories[annotation['category_id']],'license':licenses[image['license']],
                'media_ref':index.name+'/'+filename,'source_member':filename,'original_bytes':size,'original_sha256':sha,
                'annotation_sha256':proof['sha256'],'source_info':document['info']})
        if used!=set(members):raise ValueError('Native image archive contains undeclared image members')
        self._joined=rows
        return rows

    def validate_media(self,max_bytes,cancel):
        cancel();rows=self._population();cancel()
        return {'records':len(rows),'native_image_references':len(rows),'native_category_count':len({r['category']['id'] for r in rows}),
            'all_archive_image_members_joined':True,'media_scope':'partial','note':'Full original archive and every member hashed; selected previews decode locally. Exact paper population remains unidentified.'}

    def _native_record(self,row):
        record=self._record(row,row['source_id'])
        for asset in record.assets:
            asset.sha256=row['original_sha256']
            asset.metadata.update(original_bytes=row['original_bytes'],native_license=row['license'],representation='original',
                source_integrity='Complete native archive and member SHA-256; fetched compressed blocks are SHA-256 checked.')
        return record

    def iter_sequential(self,source):
        for row in self._population():
            record=self._native_record(row);source.charge(len(record.model_dump_json().encode()));yield record

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0);size=min(limit or source.limit,source.limit)
        if start<0 or size<1:raise ValueError('Invalid native record page')
        rows=self._population();records=[]
        for row in rows[start:start+size]:
            record=self._native_record(row);source.charge(len(record.model_dump_json().encode()));records.append(record)
        end=start+len(records)
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))

    def resolve_asset(self,source,asset_ref):
        archive,member=asset_ref.split('/',1)
        if archive!=self.config['image_archive_name']:raise ValueError('Unknown native iNaturalist image archive')
        _safe_relative(member)
        data,proof=self._read(self.indices[archive],member,source.max_bytes-source.bytes_read)
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('Native image exceeds decoded pixel budget')
            if image.format!='JPEG':raise ValueError('Native iNaturalist image encoding changed')
            image.verify()
        source.charge(len(data))
        return MediaHandle(data,'image/jpeg',hashlib.sha256(data).hexdigest(),asset_ref)
