"""Native Places365 validation labels joined to every original archive image."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re
import sqlite3
import tarfile

from .core import DatasetAdapter, DirectoryArchiveAdapter, RecordBatch


class Places365Adapter(DirectoryArchiveAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.config=copy.deepcopy(dataset.adapter_config)
        self.config['mapping']={'id':'source_id','media':'media_ref','label':'class_name'}

    def _rows(self):
        if hasattr(self,'_native_rows'):return self._native_rows
        path=Path(self.config['annotations_path'])
        expected=self.config.get('annotations_sha256') or next((entry['sha256'] for entry in self.config.get('source_files',[])
            if entry.get('config_key')=='annotations_path'),None)
        if not expected:raise ValueError('Places365 annotations require a pinned native checksum')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Places365 native annotation checksum changed')
        maximum=self.config.get('max_annotation_bytes',8_000_000);consumed=0
        with tarfile.open(path) as archive:
            members=archive.getmembers()
            if len({member.name for member in members})!=len(members):raise ValueError('Duplicate Places365 native archive member')
            def lines(suffix):
                nonlocal consumed
                matching=[member for member in members if member.name.rsplit('/',1)[-1]==suffix and member.isfile()]
                if len(matching)!=1:raise ValueError('Missing or ambiguous Places365 native annotation member')
                member=matching[0];consumed+=member.size
                if consumed>maximum:raise ValueError('Places365 native annotations exceed their read bound')
                source=archive.extractfile(member)
                if source is None:raise ValueError('Places365 annotation member is unavailable')
                with source:
                    payload=source.read(member.size+1)
                if len(payload)!=member.size:raise ValueError('Places365 annotation member length changed')
                return payload.decode('utf-8-sig').splitlines()
            categories={}
            for line in lines('categories_places365.txt'):
                if not line.strip():continue
                name,index=line.rsplit(maxsplit=1);identity=int(index)
                if identity in categories:raise ValueError('Duplicate Places365 native class ID')
                categories[identity]=(name,line)
            count=self.config.get('native_class_count',365)
            if set(categories)!=set(range(count)):raise ValueError('Places365 native class inventory differs')
            rows=[];seen=set();class_counts={identity:0 for identity in categories}
            prefix=self.config.get('archive_member_prefix','val_256/')
            for ordinal,line in enumerate(lines('places365_val.txt')):
                if not line.strip():continue
                filename,label=line.rsplit(maxsplit=1);identity=int(label);name=filename.lstrip('/')
                if not re.fullmatch(r'Places365_val_[0-9]{8}\.jpg',name):raise ValueError('Unsafe Places365 native image filename')
                if name in seen or identity not in categories:raise ValueError('Duplicate or unjoined Places365 validation image')
                seen.add(name);class_counts[identity]+=1
                category,category_line=categories[identity]
                rows.append({'source_id':name,'media_ref':prefix+name,'native_filename':filename,'class_index':identity,
                    'class_name':category,'native_annotation_line':line,'native_category_line':category_line,
                    'native_annotation_row':ordinal,'split':'validation','source_annotation_sha256':expected})
        names=self._names()
        if len(names)!=len(set(names)):raise ValueError('Duplicate Places365 original image member')
        if {row['media_ref'] for row in rows}!=set(names):
            raise ValueError('Places365 validation annotations and original image membership differ')
        expected_per_class=self.config.get('native_images_per_class',100)
        if any(value!=expected_per_class for value in class_counts.values()):
            raise ValueError('Places365 validation class populations differ from the declared release')
        self._member_hashes={}
        if self.config.get('original_access_index'):
            with sqlite3.connect((Path(self.config['original_access_index'])/'members.sqlite').as_uri()+'?mode=ro',uri=True) as db:
                self._member_hashes=dict(db.execute('SELECT name,sha256 FROM members'))
        self._native_rows=rows
        return rows

    def prepare(self,approved_plan):
        source=super().prepare(approved_plan);self._rows();return source

    def prepare_media(self,approved_plan):
        # Member reads verify the immutable retrieval index and original SHA.
        # They do not need to reread the complete annotation/archive population.
        return DatasetAdapter.prepare(self,approved_plan)

    def _native_record(self,row,ordinal):
        record=DatasetAdapter._record(self,row,ordinal)
        for asset in record.assets:
            if asset.uri in self._member_hashes:asset.sha256=self._member_hashes[asset.uri]
        return record

    def iter_sequential(self,source):
        for ordinal,row in enumerate(self._rows()):
            record=self._native_record(row,ordinal);source.charge(len(record.model_dump_json().encode()));yield record

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative Places365 cursor')
        rows=self._rows();end=min(len(rows),start+min(limit or source.limit,source.limit));records=[]
        for ordinal,row in enumerate(rows[start:end],start):
            record=self._native_record(row,ordinal);source.charge(len(record.model_dump_json().encode()));records.append(record)
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))
