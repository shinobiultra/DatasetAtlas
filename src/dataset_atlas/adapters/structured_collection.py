"""Pinned annotation files with selective original media from remote ZIP archives."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from PIL import Image
from .core import DatasetAdapter,SourceDescription,RecordBatch,MediaHandle,_nested,_safe_relative
from dataset_atlas.storage import BoundedCache, CacheIdentity, HttpsFetcher
from urllib.parse import quote, urlsplit
from dataset_atlas.storage.ranges import HttpsRangeReader, SmallReadBuffer


class _LocalArchive(io.BufferedReader):
    bytes_fetched = 0  # Network transfer only; local reads have their own limit.

    def __init__(self, path, budget):
        super().__init__(io.FileIO(path, 'r'))
        self.remaining = budget
        self.size = Path(path).stat().st_size

    def read(self, size=-1):
        if size < 0:size = max(0, self.size - self.tell())
        if size < 0 or size > self.remaining:
            raise ValueError('Local archive read exceeds byte budget')
        result = super().read(size)
        self.remaining -= len(result)
        return result


class StructuredCollectionAdapter(DatasetAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        import copy
        self.config=copy.deepcopy(dataset.adapter_config)

    def probe(self):
        paths=[Path(self.config[item['path_key']]) for item in self.config['annotations'] if item.get('path_key')]
        paths += [Path(self.config[item['path_key']]) for item in self.config.get('local_archives', {}).values()]
        return SourceDescription('structured_collection',str(paths[0]) if paths else 'remote ZIP annotations',all(p.is_file() for p in paths),self.revision,
            sum(p.stat().st_size for p in set(paths) if p.is_file()),False,True,True,True,True,
            ('Original ZIP media fetched on inspection using bounded, ETag-bound HTTPS ranges.',))

    def prepare(self,plan):
        source=super().prepare(plan)
        for item in self.config.get('source_files',[]):
            with Path(item['path']).open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=item['sha256']:raise ValueError('Annotation file checksum changed')
        for item in self.config.get('local_archives', {}).values():
            path = Path(self.config[item['path_key']])
            expected = self.config.get('derived_archive_checksums', {}).get(item['path_key']) or next((f['sha256'] for f in self.config.get('source_files', []) if Path(f['path']) == path), None)
            if not expected:raise ValueError('Local media archive requires a pinned checksum')
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:raise ValueError('Local media archive checksum changed')
        self._rows()
        return source

    def _rows(self):
        if hasattr(self,'_annotation_rows'):return self._annotation_rows
        rows=[];consumed=0;self._annotation_bytes_fetched=0;maximum=self.config.get('max_annotation_bytes',128_000_000)
        for entry in self.config['annotations']:
            path=Path(self.config[entry['path_key']]) if entry.get('path_key') else None
            if entry.get('remote_archive'):
                with self._remote(entry['remote_archive'],getattr(self,'_annotation_transfer_budget',self.config.get('annotation_transfer_bytes',20_000_000))-self._annotation_bytes_fetched) as remote,zipfile.ZipFile(remote) as archive:
                    info=archive.getinfo(_safe_relative(entry['member']))
                    consumed+=info.file_size
                    if consumed>maximum:raise ValueError('Annotations exceed declared read budget')
                    payload=archive.read(info)
                    self._annotation_bytes_fetched+=remote.bytes_fetched
                if hashlib.sha256(payload).hexdigest()!=entry['sha256']:raise ValueError('Remote annotation checksum changed')
            elif entry.get('member'):
                with zipfile.ZipFile(path) as archive:
                    info=archive.getinfo(_safe_relative(entry['member']))
                    consumed+=info.file_size
                    if consumed>maximum:raise ValueError('Annotations exceed declared read budget')
                    payload=archive.read(info)
            else:
                consumed+=path.stat().st_size
                if consumed>maximum:raise ValueError('Annotations exceed declared read budget')
                payload=path.read_bytes()
            format=entry.get('format','json')
            text=payload.decode('utf-8-sig')
            if format=='csv':data=list(csv.DictReader(io.StringIO(text)))
            elif format=='jsonl':data=[json.loads(line) for line in text.splitlines() if line.strip()]
            elif format=='json':data=json.loads(text)
            elif format=='text':data=[{'text':text}]
            elif format=='text_lines':data=[{'line':number,'text':line} for number,line in enumerate(text.splitlines(),1) if line.strip()]
            else:raise ValueError('Unsupported annotation format')
            if entry.get('records_key'):data=_nested(data,entry['records_key'])
            if entry.get('array_columns'):
                columns = entry['array_columns']
                if not isinstance(data, list) or any(not isinstance(row, list) or len(row) != len(columns) for row in data):
                    raise ValueError('Annotation array width differs from declared columns')
                data = [dict(zip(columns, row)) for row in data]
            if not isinstance(data,list) or any(not isinstance(row,dict) for row in data):raise ValueError('Annotations must contain a list of objects')
            joins=[]
            for spec in entry.get('joins',[]):
                join_path=Path(self.config[spec['path_key']])
                if spec.get('member'):
                    with zipfile.ZipFile(join_path) as archive:
                        info=archive.getinfo(_safe_relative(spec['member']));consumed+=info.file_size
                        if consumed>maximum:raise ValueError('Joined annotations exceed declared read budget')
                        table=json.loads(archive.read(info))
                else:
                    consumed+=join_path.stat().st_size
                    if consumed>maximum:raise ValueError('Joined annotations exceed declared read budget')
                    table=json.loads(join_path.read_text(encoding='utf-8-sig'))
                if spec.get('records_key'):table=_nested(table,spec['records_key'])
                if spec['key']=='@key':
                    if not isinstance(table,dict):raise ValueError('Keyed annotation join requires an object')
                    items=table.items()
                else:
                    if not isinstance(table,list):raise ValueError('Annotation join requires a list of objects')
                    items=((_nested(item,spec['key']),item) for item in table)
                lookup={}
                for key,item in items:
                    if key is None or not isinstance(key,(str,int)):raise ValueError('Duplicate or missing annotation join key')
                    if spec.get('string_keys'):key=str(key)
                    if key in lookup:raise ValueError('Duplicate or missing annotation join key')
                    lookup[key]=item
                joins.append((spec,lookup,set()))
            for ordinal,row in enumerate(data):
                row=dict(row)
                for spec,lookup,used_keys in joins:
                    key=_nested(row,spec['on'])
                    if spec.get('string_keys') and key is not None:key=str(key)
                    if key not in lookup:raise ValueError('Source row has no matching annotation join')
                    if spec['field'] in row:raise ValueError('Annotation join would overwrite a source field')
                    row[spec['field']]=lookup[key];used_keys.add(key)
                if any(key.startswith('_atlas_') for key in row):raise ValueError('Annotation uses reserved provenance fields')
                source_id=_nested(row,self.config.get('mapping',{}).get('id'))
                if self.config.get('identity_fields'):
                    parts=[_nested(row,key) for key in self.config['identity_fields']]
                    if any(part is None for part in parts):raise ValueError('Compound source identity field missing')
                    source_id=json.dumps(parts,ensure_ascii=False,separators=(',',':'))
                identity=f"{entry.get('identity_prefix',entry['split'])}:{source_id if source_id is not None else ordinal}"
                value={**row,'_atlas_origin':{'split':entry['split'],'row':ordinal,'file':entry.get('member',entry.get('path_key')),'identity':identity,'group':entry.get('identity_prefix',entry['split'])}}
                if entry.get('source_status'):value['_atlas_source_status']=entry['source_status']
                if entry.get('choices_columns'):
                    value['_atlas_choices'] = [row[key] for key in entry['choices_columns']]
                elif entry.get('choices_field'):
                    value['_atlas_choices'] = _nested(row, entry['choices_field'])
                if '_atlas_choices' in value:
                    choices = value['_atlas_choices']
                    if not isinstance(choices, list) or any(not isinstance(choice, str) for choice in choices):
                        raise ValueError('Caption options must be an ordered list of strings')
                    if 'correct_choice_index' in entry:
                        correct = entry['correct_choice_index']
                        if type(correct) is not int or not 0 <= correct < len(choices):raise ValueError('Invalid declared correct option')
                        value['_atlas_correct_choice_index'] = correct
                    if entry.get('text_from_first_choice') and choices:value['_atlas_text'] = choices[0]
                if self.config.get('text_parts_field'):
                    parts = _nested(row, self.config['text_parts_field'])
                    if not isinstance(parts, list) or any(not isinstance(part, str) for part in parts):
                        raise ValueError('Text parts field must be an ordered list of strings')
                    value['_atlas_text'] = ''.join(parts)
                templates=entry.get('media_templates',[entry['media_template']] if entry.get('media_template') else [])
                variables=dict(row)
                if entry.get('media_stem_field'):
                    variables['_stem']=str(row[entry['media_stem_field']]).split(entry.get('media_stem_separator','_'))[0]
                    if entry.get('media_stem_width'):
                        width = entry['media_stem_width']
                        if type(width) is not int or not 1 <= width <= 20:raise ValueError('Invalid image stem width')
                        variables['_stem'] = variables['_stem'].zfill(width)
                value['_atlas_media_refs']=[]
                if entry.get('media_paths_field'):
                    paths = _nested(row, entry['media_paths_field'])
                    if paths is None: paths = []
                    if isinstance(paths, str): paths = [paths]
                    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
                        raise ValueError('Media path field must contain strings')
                    for path in paths:
                        prefix = entry.get('media_path_remove_prefix', '')
                        if prefix:
                            if not path.startswith(prefix):raise ValueError('Image path lacks declared source prefix')
                            path = path[len(prefix):]
                        member = _safe_relative(path)
                        value['_atlas_media_refs'].append(f"zip/{entry['media_archive']}/{member}" if entry.get('media_archive') else f'file/{member}')
                if entry.get('media_path_url_field'):
                    # Only use the source URL's path as a join key. The recipe owns
                    # the HTTPS destination; annotation URLs never grant network access.
                    member = _safe_relative(urlsplit(_nested(row,entry['media_path_url_field'])).path.lstrip('/'))
                    remove_prefix=entry.get('media_path_remove_prefix','')
                    if remove_prefix:
                        if not member.startswith(remove_prefix):raise ValueError('Image URL lacks declared source prefix')
                        member=_safe_relative(member[len(remove_prefix):])
                    prefix = member.split('/', 1)[0]
                    key = entry['media_archive_by_prefix'].get(prefix)
                    if key not in self.config['remote_archives']: raise ValueError('Image URL path has no declared archive')
                    value['_atlas_media_refs'].append(f'zip/{key}/{member}')
                for template in templates:
                    member=re.sub(r'\{([A-Za-z0-9_]+)\}',lambda match:str(variables[match[1]]),template)
                    member=_safe_relative(member)
                    value['_atlas_media_refs'].append(f"zip/{entry['media_archive']}/{member}" if entry.get('media_archive') else f'file/{member}')
                if entry.get('media_variants'):
                    value['_atlas_media_conditions']={};value['_atlas_absent_conditions']=[]
                    variables['_prefix']=entry.get('media_prefix','')
                    for variant in entry['media_variants']:
                        absent=variant.get('absent_when')
                        if absent and _nested(row,absent['field']) in absent['values']:
                            value['_atlas_absent_conditions'].append(variant['condition'])
                            continue
                        member=_safe_relative(re.sub(r'\{([A-Za-z0-9_]+)\}',lambda match:str(variables[match[1]]),variant['template']))
                        ref=f'file/{member}'
                        if ref in value['_atlas_media_refs']:raise ValueError('Duplicate media variant')
                        target=_nested(row,variant['target_field']) if 'target_field' in variant else variant.get('target')
                        value['_atlas_media_conditions'][ref]={'condition':variant['condition'],'target':target,
                            'target_provenance':'native field '+variant['target_field'] if 'target_field' in variant else 'release card condition definition'}
                        value['_atlas_media_refs'].append(ref)
                rows.append(value)
            for spec,lookup,used_keys in joins:
                if not spec.get('allow_unused',False) and used_keys!=set(lookup):raise ValueError('Unmatched annotation join rows')
        self._annotation_rows=rows
        return rows

    @property
    def count(self):return len(self._rows())

    def source_field_types(self):
        types={}
        for row in self._rows():
            for key,value in row.items():
                if key=='_atlas_media_refs' or value is None:continue
                kind=('boolean' if isinstance(value,bool) else 'number' if isinstance(value,(int,float)) and abs(value)<=2**53
                      else 'string' if isinstance(value,str) else 'array' if isinstance(value,list) else 'object')
                types.setdefault(key,set()).add(kind)
        return {key:next(iter(values)) if len(values)==1 else 'object' for key,values in types.items()}

    def _remote(self,key,budget):
        if key in self.config.get('local_archives', {}):
            return _LocalArchive(self.config[self.config['local_archives'][key]['path_key']], budget)
        entry=self.config['remote_archives'][key]
        cache=BoundedCache(self.config['remote_cache_root'],max_bytes=self.config.get('remote_cache_bytes',1_000_000_000))
        return HttpsRangeReader(entry['url'],size=entry['bytes'],etag=entry['etag'],allowed_hosts=entry['allowed_hosts'],byte_budget=budget,cache=cache)

    def _inventory(self):
        if not hasattr(self,'_media_inventory'):
            path=Path(self.config['media_inventory_path'])
            if path.stat().st_size>20_000_000:raise ValueError('Media inventory exceeds 20 MB')
            payload=path.read_bytes()
            if hashlib.sha256(payload).hexdigest()!=self.config['media_inventory_sha256']:raise ValueError('Media inventory checksum changed')
            self._media_inventory=json.loads(payload)['files']
            for name,entry in self._media_inventory.items():
                _safe_relative(name)
                if type(entry.get('bytes')) is not int or not 1<=entry['bytes']<=250_000_000:raise ValueError('Invalid inventory image size')
                if not (re.fullmatch(r'[a-f0-9]{64}',entry.get('sha256','')) or re.fullmatch(r'[a-f0-9]{40}',entry.get('git_blob_sha1',''))):raise ValueError('Inventory image requires a content checksum')
        return self._media_inventory

    def validate_media(self,budget,cancel=None):
        """Validate all annotation joins through ZIP directories, without fetching images."""
        self._annotation_transfer_budget=budget
        wanted={};individual=set()
        for row in self._rows():
            for ref in row.get('_atlas_media_refs',[]):
                if ref.startswith('file/'):individual.add(ref[5:])
                else:
                    _,key,member=ref.split('/',2);wanted.setdefault(key,set()).add(member)
        fetched=getattr(self,'_annotation_bytes_fetched',0)
        if individual:
            missing=individual-set(self._inventory())
            if missing:raise ValueError(f'Annotations reference {len(missing)} missing inventory images: {sorted(missing)[:3]}')
        for key,names in wanted.items():
            if cancel:cancel()
            with self._remote(key,budget-fetched) as source,zipfile.ZipFile(source) as archive:
                entries={i.filename:i for i in archive.infolist() if not i.is_dir()}
                missing=names-set(entries)
                if missing:raise ValueError(f'Annotations reference {len(missing)} missing ZIP images in {key}: {sorted(missing)[:3]}')
                fetched+=source.bytes_fetched
        return {'referenced_images':sum(len(names) for names in wanted.values())+len(individual),'archives':len(wanted),'metadata_bytes_fetched':fetched,
                'integrity':('Remote archives: strong ETags and ZIP CRCs, full remote SHA-256 not computed. Local archives: pinned full-file SHA-256 and member CRCs.' if wanted else 'Original image files checked against the pinned SHA-256 or Git blob inventory on access.')}

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative cursor')
        rows=self._rows();end=min(start+min(limit or source.limit,source.limit),len(rows));records=[]
        self.config['mapping']={**self.config.get('mapping',{}),'id':'_atlas_origin.identity','media':'_atlas_media_refs'}
        for ordinal,row in enumerate(rows[start:end],start):
            record=DatasetAdapter._record(self,row,ordinal);record.source.pop('_atlas_media_refs',None)
            for asset in record.assets:
                if asset.uri in row.get('_atlas_media_conditions',{}):asset.metadata.update(row['_atlas_media_conditions'][asset.uri])
                if asset.uri.startswith('file/'):
                    entry=self._inventory()[asset.uri[5:]]
                    asset.sha256=entry.get('sha256')
                    asset.metadata.update({'representation':'original source file','source_checksum':entry})
                    continue
                key=asset.uri.split('/')[1]
                asset.metadata.update({'representation':'original ZIP member'})
                if key in self.config.get('remote_archives', {}):asset.metadata['source_etag']=self.config['remote_archives'][key]['etag']
            source.charge(len(record.model_dump_json().encode()));records.append(record)
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))

    def resolve_asset(self,source,asset_ref):
        if asset_ref.startswith('file/'):
            name=_safe_relative(asset_ref[5:]);entry=self._inventory().get(name)
            if not entry:raise ValueError('Image is absent from pinned inventory')
            remaining=source.max_bytes-source.bytes_read
            if entry['bytes']>remaining:raise ValueError('Source image exceeds byte budget')
            cache=BoundedCache(self.config['remote_cache_root'],max_bytes=self.config.get('remote_cache_bytes',1_000_000_000))
            path=HttpsFetcher(self.config['media_allowed_hosts'],max_bytes=remaining,credential_profile=self.config.get('credential_profile')).fetch(
                self.config['media_base_url'].rstrip('/')+'/'+quote(name,safe='/'),cache,
                CacheIdentity(self.revision,entry.get('sha256',entry.get('git_blob_sha1')),'source-image'),
                expected_sha256=entry.get('sha256'),byte_budget=entry['bytes'])
            data=path.read_bytes()
            if len(data)!=entry['bytes']:raise ValueError('Source image length changed')
            if entry.get('git_blob_sha1') and hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()!=entry['git_blob_sha1']:
                raise ValueError('Source image differs from pinned Git object')
            return self._image_handle(source,data,asset_ref)
        parts=asset_ref.split('/',2)
        if len(parts)!=3 or parts[0]!='zip' or parts[1] not in {*self.config.get('remote_archives', {}), *self.config.get('local_archives', {})}:raise ValueError('Invalid ZIP reference')
        _,key,member=parts;member=_safe_relative(member)
        remaining=source.max_bytes-source.bytes_read
        if key in self.config.get('local_archives', {}):
            from dataset_atlas.storage.zip_members import LOCAL_ZIP_MEMBERS
            path_key=self.config['local_archives'][key]['path_key']
            path=Path(self.config[path_key])
            expected=self.config.get('derived_archive_checksums',{}).get(path_key) or next((item['sha256'] for item in self.config.get('source_files',[]) if Path(item['path'])==path),None)
            if not expected:raise ValueError('Local media archive requires a pinned checksum')
            return self._image_handle(source,LOCAL_ZIP_MEMBERS.read(path,member,remaining,expected),asset_ref)
        with self._remote(key,self.config.get('media_transfer_bytes',40_000_000)) as remote:
            # ZIP local headers, names and small image payloads are adjacent.
            # Coalesce their reads instead of making several HTTP round trips.
            reader = SmallReadBuffer(remote) if isinstance(remote, HttpsRangeReader) else remote
            with zipfile.ZipFile(reader) as archive:
                info=archive.getinfo(member)
                if info.is_dir() or info.file_size>remaining or info.file_size<1:raise ValueError('Remote ZIP image exceeds byte budget')
                data=archive.read(info)  # ZIP CRC validated by zipfile, including decompression.
        return self._image_handle(source,data,asset_ref)

    def _image_handle(self,source,data,asset_ref):
        source.charge(len(data))
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('Remote ZIP image exceeds pixel budget')
            mime=Image.MIME.get(image.format,'application/octet-stream');image.verify()
        return MediaHandle(data,mime,hashlib.sha256(data).hexdigest(),asset_ref)
