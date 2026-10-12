from __future__ import annotations
import json
import os
import re
import sqlite3
import secrets
import hashlib
from collections import OrderedDict
from threading import RLock, BoundedSemaphore
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi import Query as QueryParam
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from dataset_atlas.models import Capabilities, Pack, Query, Selection, Record, content_id
from dataset_atlas.registry import Registry
from dataset_atlas.queries import query_pack,materialize_records
from dataset_atlas.runtime import analysis_config, roots_for

class RunRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    selection_id: str
    processor_id: str
    config: dict = Field(default_factory=dict)
    estimate_digest: str | None = None

class SimilarityRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    artifact_id: str
    record_id: str | None = None
    text: str | None = Field(default=None,max_length=4000)
    query: Query
    limit: int = Field(default=20,ge=1,le=100)

class AggregateRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query: Query
    field_ids: list[str] = Field(min_length=1, max_length=12)
    top: int = Field(default=24, ge=1, le=200)

class PreparationPlanRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    max_download_bytes: int = Field(ge=1)
    max_output_bytes: int = Field(ge=1)
    source_mode: str = Field(default='download', pattern='^(auto|download|selective|sample)$')

class LocalDatasetRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source: str = Field(min_length=1, max_length=2000)
    name: str|None = Field(default=None, max_length=120)
    dataset_id: str|None = Field(default=None, max_length=63)
    description: str = Field(default='', max_length=2000)
    options: dict[str,str|None] = Field(default_factory=dict)
    replace: bool = False

class RecordRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    ids: list[str] = Field(min_length=1, max_length=1000)
    snapshot_ids: list[str] | None = Field(default=None,min_length=1,max_length=1000)

class PopulationRequest(BaseModel):
    """Select every record a query matches, on the server, without moving the ids through the browser."""
    model_config=ConfigDict(extra='forbid')
    dataset_id: str
    query: Query
    name: str = Field(default='',max_length=200)
    limit: int = Field(default=1_000_000,ge=1,le=2_000_000)

class PublicationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    max_bytes: int = Field(default=100_000_000,ge=1,le=1_000_000_000)

class MediaHandles:
    """Bound metadata retained by browsing; old complete-data URLs require requery."""
    def __init__(self, capacity=10000):
        self.capacity=capacity
        self.values=OrderedDict()
        self.lock=RLock()
    def __setitem__(self,key,value):
        with self.lock:
            self.values[key]=value
            self.values.move_to_end(key)
            while len(self.values)>self.capacity:self.values.popitem(last=False)
    def get(self,key):
        with self.lock:
            value=self.values.get(key)
            if value is not None:self.values.move_to_end(key)
            return value

def media_byte_limit(asset):
    if asset.modality=='image' and (asset.metadata.get('source_format')=='TIFF16'
        or asset.metadata.get('representation')=='original 16-bit expert TIFF'):return 150_000_000
    return 250_000_000 if asset.modality=='video' else 100_000_000 if asset.modality=='audio' else 50_000_000

_SAFE_VIEW_CACHE=OrderedDict()
_SAFE_VIEW_CACHE_BYTES=[0]
_SAFE_VIEW_CACHE_LIMIT=100_000_000
_SAFE_VIEW_LOCK=RLock()
_VIDEO_DISPLAY_SLOT=BoundedSemaphore(1)

def cached_video_display(data:bytes)->bytes:
    from dataset_atlas.storage.video import browser_video_render
    key='video-display:'+hashlib.sha256(data).hexdigest()
    with _SAFE_VIEW_LOCK:
        cached=_SAFE_VIEW_CACHE.get(key)
        if cached is not None:
            _SAFE_VIEW_CACHE.move_to_end(key)
            return cached
    if not _VIDEO_DISPLAY_SLOT.acquire(timeout=30):raise ValueError('Video display queue exceeded its wait bound')
    try:
        with _SAFE_VIEW_LOCK:
            cached=_SAFE_VIEW_CACHE.get(key)
            if cached is not None:
                _SAFE_VIEW_CACHE.move_to_end(key)
                return cached
        derived,_=browser_video_render(data)
        with _SAFE_VIEW_LOCK:
            _SAFE_VIEW_CACHE[key]=derived
            _SAFE_VIEW_CACHE_BYTES[0]+=len(derived)
            while _SAFE_VIEW_CACHE_BYTES[0]>_SAFE_VIEW_CACHE_LIMIT and len(_SAFE_VIEW_CACHE)>1:
                _,evicted=_SAFE_VIEW_CACHE.popitem(last=False)
                _SAFE_VIEW_CACHE_BYTES[0]-=len(evicted)
        return derived
    finally:_VIDEO_DISPLAY_SLOT.release()

def cached_display(data:bytes)->bytes:
    """Browser renderings of non-browser formats are pure functions of the original bytes; share the derivative cache."""
    from dataset_atlas.storage.display import browser_render
    key='display:'+hashlib.sha256(data).hexdigest()
    with _SAFE_VIEW_LOCK:
        cached=_SAFE_VIEW_CACHE.get(key)
        if cached is not None:
            _SAFE_VIEW_CACHE.move_to_end(key)
            return cached
    derived=browser_render(data)
    with _SAFE_VIEW_LOCK:
        _SAFE_VIEW_CACHE[key]=derived
        _SAFE_VIEW_CACHE_BYTES[0]+=len(derived)
        while _SAFE_VIEW_CACHE_BYTES[0]>_SAFE_VIEW_CACHE_LIMIT and len(_SAFE_VIEW_CACHE)>1:
            _,evicted=_SAFE_VIEW_CACHE.popitem(last=False)
            _SAFE_VIEW_CACHE_BYTES[0]-=len(evicted)
    return derived

def cached_safe_view(data:bytes)->bytes:
    """Display derivatives are pure functions of the original bytes; keep recent ones."""
    from dataset_atlas.storage.display import safe_view
    key=hashlib.sha256(data).hexdigest()
    with _SAFE_VIEW_LOCK:
        cached=_SAFE_VIEW_CACHE.get(key)
        if cached is not None:
            _SAFE_VIEW_CACHE.move_to_end(key)
            return cached
    derived=safe_view(data)
    with _SAFE_VIEW_LOCK:
        _SAFE_VIEW_CACHE[key]=derived
        _SAFE_VIEW_CACHE_BYTES[0]+=len(derived)
        while _SAFE_VIEW_CACHE_BYTES[0]>_SAFE_VIEW_CACHE_LIMIT and len(_SAFE_VIEW_CACHE)>1:
            _,evicted=_SAFE_VIEW_CACHE.popitem(last=False)
            _SAFE_VIEW_CACHE_BYTES[0]-=len(evicted)
    return derived

def media_response(data:bytes,media_type:str,request:Request):
    """Serve bounded, already safely read bytes with native media seeking."""
    representation=request.query_params.get('representation','original')
    original_sha256=hashlib.sha256(data).hexdigest()
    if representation not in {'original','safe-view','compact','optimized','display'}:raise ValueError('Unknown display representation')
    if representation=='display':
        # An adapter that cannot name a format reports application/octet-stream; the decoder, not the label, decides whether it is an image.
        if media_type == 'video/x-msvideo':
            data=cached_video_display(data)
            media_type='video/mp4'
        else:
            if not (media_type.startswith('image/') or media_type=='application/octet-stream'):raise ValueError('Unsupported display rendering')
            data=cached_display(data)
            media_type='image/png'
    if representation=='safe-view':
        if not media_type.startswith('image/'):raise ValueError('Safe-view derivatives support images only')
        data=cached_safe_view(data)
        media_type='image/png'
    size=len(data)
    etag='"'+hashlib.sha256(data).hexdigest()+'"'
    headers={'Accept-Ranges':'bytes','ETag':etag,'Cache-Control':'private, max-age=3600'}
    if representation=='display':
        headers['X-Atlas-Media-Representation']='display'
        headers['X-Atlas-Original-SHA256']=original_sha256
    if request.headers.get('if-none-match')==etag and not request.headers.get('range'):
        return Response(status_code=304,headers=headers)
    requested=request.headers.get('range')
    if request.headers.get('if-range',etag)!=etag:requested=None
    status=200
    if requested:
        match=re.fullmatch(r'bytes=([0-9]{0,20})-([0-9]{0,20})',requested)
        if not match or not any(match.groups()) or size==0:
            return Response(status_code=416,headers={**headers,'Content-Range':f'bytes */{size}'})
        first,last=match.groups()
        start=int(first) if first else max(0,size-int(last))
        end=min(size-1,int(last)) if first and last else size-1
        if start>=size or end<start:
            return Response(status_code=416,headers={**headers,'Content-Range':f'bytes */{size}'})
        headers['Content-Range']=f'bytes {start}-{end}/{size}'
        data=data[start:end+1]
        status=206
    headers['Content-Length']=str(len(data))
    return Response(b'' if request.method=='HEAD' else data,status_code=status,media_type=media_type,headers=headers)

INLINE_SELECTION_IDS=10_000  # larger selections keep their ids in a side file and list only a summary

class State:
    def __init__(self,path):
        self.path=Path(path)
        self.ids_dir=self.path.parent/'selection-ids'
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS selections (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS selection_ids (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, count INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    def connection(self):
        db=sqlite3.connect(self.path);db.execute('PRAGMA journal_mode=WAL');return db
    def list(self):
        """Every selection; large ones as summaries (empty `ids`, `size` set)."""
        with self.connection() as db:return [Selection.model_validate_json(row[0]) for row in db.execute('SELECT body FROM selections ORDER BY id')]
    def get(self,id,ids=True):
        with self.connection() as db:
            row=db.execute('SELECT body FROM selections WHERE id=?',(id,)).fetchone()
            side=db.execute('SELECT sha256,count FROM selection_ids WHERE id=?',(id,)).fetchone()
        if not row:raise KeyError(id)
        selection=Selection.model_validate_json(row[0])
        if side and ids:
            payload=(self.ids_dir/f'{id}.json').read_bytes()
            if hashlib.sha256(payload).hexdigest()!=side[0]:raise ValueError('Stored selection ids do not match their checksum')
            values=json.loads(payload)
            if len(values)!=side[1]:raise ValueError('Stored selection id count disagrees with its record')
            selection=selection.model_copy(update={'ids':values})
        return selection
    @staticmethod
    def summary(selection):
        """What listings and responses carry: large selections without their ids."""
        if len(selection.ids)>INLINE_SELECTION_IDS:return selection.model_copy(update={'ids':[],'size':len(selection.ids)})
        return selection
    def put(self,selection):
        large=len(selection.ids)>INLINE_SELECTION_IDS
        stored=self.summary(selection)
        with self.connection() as db:
            old=db.execute('SELECT body FROM selections WHERE id=?',(selection.id,)).fetchone()
            body=stored.model_dump_json()
            if old and old[0]!=body:raise ValueError('Selections are immutable; create a new selection')
            if large:
                if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',selection.id):raise ValueError('Invalid selection id')
                payload=json.dumps(selection.ids,ensure_ascii=False,separators=(',',':')).encode()
                self.ids_dir.mkdir(exist_ok=True)
                target=self.ids_dir/f'{selection.id}.json'
                if not target.exists():
                    temporary=target.with_name(target.name+'.tmp')
                    temporary.write_bytes(payload);os.replace(temporary,target)
                db.execute('INSERT OR IGNORE INTO selection_ids VALUES (?,?,?)',(selection.id,hashlib.sha256(payload).hexdigest(),len(selection.ids)))
            db.execute('INSERT OR IGNORE INTO selections VALUES (?,?)',(selection.id,body))

def create_app(root: str|Path|None=None, *, allowed_roots: list[Path]|None=None, allowed_hosts: list[str]|None=None) -> FastAPI:
    root=Path(root or os.environ.get('ATLAS_ROOT',Path.cwd())).resolve()
    work=root/'work';work.mkdir(parents=True,exist_ok=True)
    registry=Registry(root);state=State(work/'atlas.sqlite')
    roots=[p.resolve() for p in (allowed_roots or roots_for(root,'data_roots'))]
    media_handles=MediaHandles()
    snapshot_cache={}
    thumbnail_cache={}
    pack_cache={}
    def indexed_pack(pack_path):
        """A parsed pack and its record index, cached on the file's on-disk revision.

        Selections, exports and model contexts resolve many IDs in a row; parsing
        the whole pack per ID made a 100-record selection take over a second."""
        stat=pack_path.stat()
        if stat.st_size>100_000_000:raise ValueError('Pack exceeds the interactive metadata read limit')
        signature=(stat.st_mtime_ns,stat.st_size)
        cached=pack_cache.get(str(pack_path))
        if cached is None or cached[0]!=signature:
            pack=Pack.model_validate_json(pack_path.read_text())
            index={record.id:record for record in pack.records+materialize_records(pack,'asset')}
            cached=(signature,pack,index)
            pack_cache[str(pack_path)]=cached
        return cached[1],cached[2]
    def complete_snapshot(dataset_id):
        if not registry.has(registry.resolve(dataset_id)):raise KeyError(dataset_id)
        path=registry.snapshot_path(dataset_id)
        if not (path/'manifest.json').exists():raise ValueError('Complete-data index not prepared; run atlas datasets index with the verified full count')
        if str(path) not in snapshot_cache:
            from dataset_atlas.queries.parquet import ParquetSnapshot
            snapshot_cache[str(path)]=ParquetSnapshot(path.parent,path)
        return snapshot_cache[str(path)]
    hosts=set(allowed_hosts or ['localhost','127.0.0.1','::1','testserver'])
    jobs=None
    service=None
    publication_lock=RLock()
    try:
        from dataset_atlas.jobs import JobManager
        jobs=JobManager(work)
    except ImportError:pass
    @asynccontextmanager
    async def lifespan(app):
        if jobs and hasattr(jobs,'start'):jobs.start()
        if jobs:
            # Parse registered artifacts once in the background so the first dataset view is not the one to pay for it.
            import threading
            threading.Thread(target=jobs.list_artifacts,name='atlas-artifact-warmup',daemon=True).start()
        yield
        if service is not None:service.close()
        if jobs and hasattr(jobs,'close'):jobs.close()
    app=FastAPI(title='Dataset Atlas',version='1.0',lifespan=lifespan)
    app.state.registry=registry;app.state.jobs=jobs
    @app.middleware('http')
    async def security(request: Request, call_next):
        host=request.url.hostname
        if host not in hosts:return JSONResponse({'detail':'Unapproved host'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/')!=f'{request.url.scheme}://{request.headers.get("host")}':return JSONResponse({'detail':'Cross-origin requests are disabled'},status_code=403)
        if request.method not in {'GET','HEAD','OPTIONS'} and request.headers.get('x-atlas-request')!='1':return JSONResponse({'detail':'State-changing requests require X-Atlas-Request: 1'},status_code=403)
        length=request.headers.get('content-length','0')
        try:
            if int(length)>10_000_000:return JSONResponse({'detail':'Request exceeds 10 MB'},status_code=413)
        except ValueError:return JSONResponse({'detail':'Invalid content length'},status_code=400)
        if request.method not in {'GET','HEAD','OPTIONS'}:
            chunks=[];received=0
            async for chunk in request.stream():
                received+=len(chunk)
                if received>10_000_000:return JSONResponse({'detail':'Request exceeds 10 MB'},status_code=413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        path=request.url.path
        if not path.startswith('/api/'):
            # The shell must revalidate so a rebuilt frontend is picked up; hashed bundles never change.
            response.headers['Cache-Control']='public, max-age=31536000, immutable' if path.startswith('/assets/') else 'no-cache'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: https:; media-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        return response
    from fastapi.exceptions import RequestValidationError
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return JSONResponse({'detail':[{'type':e['type'],'loc':list(e['loc']),'msg':e['msg']} for e in exc.errors()]},status_code=422)
    @app.exception_handler(ValueError)
    async def value_error(request,exc):return JSONResponse({'detail':str(exc)},status_code=422)
    @app.exception_handler(KeyError)
    async def key_error(request,exc):return JSONResponse({'detail':'Unknown identity: '+str(exc)},status_code=404)
    @app.exception_handler(FileNotFoundError)
    async def file_error(request,exc):return JSONResponse({'detail':'Prepared source or artifact is unavailable; inspect coverage and preparation requirements.'},status_code=409)
    def verify_selected_original(asset,data):
        if asset.sha256 and hashlib.sha256(data).hexdigest()!=asset.sha256:
            raise ValueError('Resolved original differs from selected asset checksum')
    def verified_cached_original(data,sha,suffix):
        from dataset_atlas.storage.local import SafeRoots
        from dataset_atlas.adapters.core import _write_rooted_atomic
        if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Resolved original content checksum changed')
        relative='work/media-cache/'+sha+suffix
        cached=root/relative;valid=False
        try:
            with SafeRoots({'workspace':root}).open('workspace',relative) as stream:
                valid=(os.fstat(stream.fileno()).st_size==len(data)
                       and hashlib.file_digest(stream,'sha256').hexdigest()==sha)
        except (OSError,ValueError):pass
        if not valid:_write_rooted_atomic(root,relative,data)
        return cached
    def pinned_preview_original(dataset_id, asset):
        """A local file holding a preview original pinned in the compact store, for processors that read paths.

        Only a protected original qualifies: a compressed browsing copy is never handed to a processor. The file is content-addressed in the
        media cache, so repeated runs reuse it and its name states the hash of what the processor will read."""
        from dataset_atlas.storage.compact import read_compact
        snapshot_id = asset.metadata.get('_compact_snapshot_id')
        if not snapshot_id or asset.modality != 'image': return None
        found = read_compact(root, dataset_id, snapshot_id, asset.metadata.get('source_ref', asset.uri), media_byte_limit(asset))
        if not found or found[2].get('representation') != 'original' or not found[2].get('protected_preview'): return None
        verify_selected_original(asset,found[0])
        suffix = {"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/gif":".gif","image/tiff":".tif"}.get(found[1])
        if not suffix: return None
        sha = hashlib.sha256(found[0]).hexdigest()
        return verified_cached_original(found[0],sha,suffix)
    def prepared_record(record, dataset, *, allow_source_read=True):
        resolved=record.model_copy(deep=True)
        for asset in resolved.assets:
            if not asset.uri or asset.uri.startswith(('http://','https://','data:')):continue
            asset.metadata['_compact_snapshot_id'] = record.snapshot_id
            retained = retained_preview_media(dataset.id, asset)
            if retained is not None:
                verify_selected_original(asset,retained[0])
                asset.uri = str(retained[2])
                continue
            pinned = pinned_preview_original(dataset.id, asset)
            if pinned is not None:
                asset.metadata['source_ref'] = asset.uri
                asset.uri = str(pinned)
                continue
            path=asset_path(asset)
            if path.is_file() or not dataset.adapter_config:
                if not path.is_file() and not allow_source_read:
                    raise FileNotFoundError('Original media is not retained locally')
                if path.is_file() and asset.sha256:
                    from dataset_atlas.storage import read_rooted_file
                    verify_selected_original(asset,read_rooted_file(path,roots,media_byte_limit(asset)))
                asset.uri=str(path)
                continue
            if dataset.adapter_config.get('media_base_url'):
                source_root=dataset.adapter_config.get('media_root')
                local_source=Path(source_root)/asset.uri if source_root else None
                if local_source is None or not local_source.is_file():
                    asset.metadata['source_ref']=asset.uri
                    asset.uri=str(path)
                    continue
            from dataset_atlas.adapters import resolve_dataset_asset
            handle=resolve_dataset_asset(dataset,asset.uri,max_bytes=media_byte_limit(asset),cache_root=work/'media-cache/decoded',workspace_root=root,allow_source_read=allow_source_read)
            verify_selected_original(asset,handle.data)
            suffix={"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/gif":".gif","image/avif":".avif","image/tiff":".tif","image/bmp":".bmp","video/mp4":".mp4","video/webm":".webm","video/x-msvideo":".avi","audio/mpeg":".mp3","audio/wav":".wav","audio/ogg":".ogg","audio/flac":".flac"}.get(handle.media_type)
            if not suffix:raise ValueError('Prepared analysis media type is unsupported')
            cached=verified_cached_original(handle.data,handle.sha256,suffix)
            asset.metadata['source_ref']=asset.uri
            asset.uri=str(cached)
        return resolved
    def find_record(record_id: str,prepare_media=True,snapshot_ids=None):
        # Record IDs are namespaced by dataset; only fall back to a catalogue sweep for foreign IDs.
        prefix=record_id.split(':',1)[0]
        candidates=[prefix] if registry.has(prefix) else registry.ids()
        for dataset_id in candidates:
            for dataset,pack_path,snapshot_path in registry.versions(dataset_id):
                if snapshot_ids and dataset.snapshot_id not in snapshot_ids:continue
                if not pack_path.is_file():continue
                _,index=indexed_pack(pack_path)
                record=index.get(record_id)
                if record is not None:return prepared_record(record,dataset) if prepare_media else record.model_copy(deep=True)
                if (snapshot_path/'manifest.json').exists():
                    from dataset_atlas.queries.parquet import ParquetSnapshot
                    if str(snapshot_path) not in snapshot_cache:snapshot_cache[str(snapshot_path)]=ParquetSnapshot(snapshot_path.parent,snapshot_path)
                    snap=snapshot_cache[str(snapshot_path)]
                    response=snap.query(Query(snapshot_id=snap.snapshot_id,population_scope='complete',unit=snap.unit,filter={'field_id':'id','op':'eq','value':record_id},limit=1))
                    if response.records:return prepared_record(response.records[0],dataset) if prepare_media else response.records[0]
        return None
    def bulk_records(selection,prepare_media):
        """Records of a large selection with one scan per dataset version, not one query per id."""
        wanted=list(selection.ids);found={}
        for dataset_id in selection.dataset_ids:
            if not registry.has(dataset_id):continue
            for dataset,pack_path,snapshot_path in registry.versions(dataset_id):
                if dataset.snapshot_id not in selection.snapshot_ids:continue
                if pack_path.is_file():
                    _,index=indexed_pack(pack_path)
                    for identity in wanted:
                        record=index.get(identity) if identity not in found else None
                        if record is not None:found[identity]=prepared_record(record,dataset) if prepare_media else record.model_copy(deep=True)
                remaining=[identity for identity in wanted if identity not in found]
                if remaining and (snapshot_path/'manifest.json').exists():
                    from dataset_atlas.queries.parquet import ParquetSnapshot
                    if str(snapshot_path) not in snapshot_cache:snapshot_cache[str(snapshot_path)]=ParquetSnapshot(snapshot_path.parent,snapshot_path)
                    for identity,record in snapshot_cache[str(snapshot_path)].records(remaining,missing_ok=True).items():
                        found[identity]=prepared_record(record,dataset) if prepare_media else record
        for identity in wanted:
            if identity not in found:raise ValueError(f'Selected record unavailable: {identity}')
        return [found[identity] for identity in wanted]
    resolved_population={}  # selection id -> (expiry, records): estimate and create resolve the same large selection back to back
    def selection_records(selection,prepare_media=True):
        records=[]
        if len(selection.ids)>500:
            import time
            key=(selection.id,prepare_media,hash(tuple(selection.ids)))  # the ids themselves, not just the id: a copy with other ids must not hit
            hit=resolved_population.get(key)
            if hit and hit[0]>time.monotonic():records=hit[1]
            else:
                records=bulk_records(selection,prepare_media)
                resolved_population.clear();resolved_population[key]=(time.monotonic()+300,records)
        else:
            for identity in selection.ids:
                record=find_record(identity,prepare_media=prepare_media,snapshot_ids=selection.snapshot_ids)
                if record is None:raise ValueError(f'Selected record unavailable: {identity}')
                records.append(record)
        for record in records:
            if record.snapshot_id not in selection.snapshot_ids or record.dataset_id not in selection.dataset_ids or record.unit!=selection.unit:raise ValueError('Selection identity, unit or snapshot mismatch')
        result_ids=selection.query.get('result_snapshot_ids',[])
        if result_ids:
            from dataset_atlas.models import Pack
            from dataset_atlas.queries.results import attach_results
            joined={}
            for dataset_id in selection.dataset_ids:
                rows=[r for r in records if r.dataset_id==dataset_id]
                if not rows:continue
                dataset=registry.dataset(dataset_id).model_copy(update={'snapshot_id':rows[0].snapshot_id})
                chosen=[a for a in selected_artifacts(result_ids) if rows[0].snapshot_id in a.snapshot_ids]
                pack=attach_results(Pack(dataset=dataset,fields=[],records=rows),chosen)
                joined.update({r.id:r for r in pack.records})
            records=[joined.get(r.id,r) for r in records]
        return records
    def asset_path(asset):
        uri=asset.uri
        if not uri:raise FileNotFoundError('Asset has no local representation')
        parsed=urlparse(uri)
        if parsed.scheme in {'http','https'}:raise ValueError('Remote media must be prepared within the approved source budget')
        if parsed.scheme and parsed.scheme!='file':raise ValueError('Unsupported asset scheme')
        candidate=Path(parsed.path if parsed.scheme=='file' else uri)
        if not candidate.is_absolute():
            # Pack-local paths only, never arbitrary cwd.
            candidate=work/'packs'/asset.dataset_id/candidate
        resolved=candidate.resolve()
        if not any(resolved.is_relative_to(p) for p in roots):raise ValueError('Media outside configured roots')
        if resolved.is_file() and resolved.suffix.lower() not in {'.jpg','.jpeg','.png','.webp','.gif','.avif','.tif','.tiff','.mp3','.wav','.ogg','.mp4','.webm','.avi','.flac'}:raise ValueError('Unsupported media type')
        return resolved
    preview_asset_ids={}
    def is_preview_asset(dataset_id, asset_id, snapshot_id):
        try:
            preview = registry.pack(dataset_id)
            if preview.dataset.snapshot_id == snapshot_id:
                path = None
                signature = ('active', id(preview))
            else:
                path = next(p for d,p,_ in registry.versions(dataset_id) if d.snapshot_id == snapshot_id)
                stat = path.stat()
                signature = (str(path), stat.st_mtime_ns, stat.st_size)
            key = (dataset_id, snapshot_id)
            cached = preview_asset_ids.get(key)
            if cached is None or cached[0] != signature or (path is None and cached[2] is not preview):
                if path is not None:preview = Pack.model_validate_json(path.read_text())
                cached = (signature, frozenset(a.id for r in preview.records for a in r.assets), preview if path is None else None)
                preview_asset_ids[key] = cached
            return asset_id in cached[1]
        except (FileNotFoundError, StopIteration):
            return True
    def expose_asset(dataset_id, asset, snapshot_id, *, allow_compact=True):
        from dataset_atlas.storage.compact import compact_entry
        entry = compact_entry(root, dataset_id, snapshot_id, asset.uri)
        token = content_id([dataset_id, snapshot_id, asset.id])
        if asset.modality == 'image' and Path(urlparse(asset.uri).path).suffix.lower() in {'.tif', '.tiff'}:
            # Packs prepared before the adapter flagged TIFF media carry no marker; the file name alone says a browser cannot decode it.
            asset.metadata.setdefault('browser_render_required', True)
            asset.metadata.setdefault('source_format', 'TIFF')
        original = asset.model_copy(deep=True)
        original.metadata['_compact_snapshot_id'] = snapshot_id
        media_handles[token] = (dataset_id, original)
        asset.uri = '/api/v1/media/' + token
        if allow_compact and entry and entry['representation'] == 'compressed_avif':
            asset.metadata['original_uri'] = asset.uri + '?representation=original'
            asset.metadata['compression'] = entry
            asset.representation = 'compressed_avif'
            asset.sha256 = entry['sha256']
            asset.uri += '?representation=compact'
        elif allow_compact and not entry and asset.modality == 'image':
            from dataset_atlas.storage.optimized import storage_policy
            from PIL import features
            policy = storage_policy(root)
            if policy and policy.get('optimize_on_demand') and 'avif' in features.get_supported():
                # Preview membership is based on stable asset identity, including
                # legacy packs that materialize the same image under another URI.
                protected = is_preview_asset(dataset_id, asset.id, snapshot_id)
                if not protected:
                    asset.metadata['original_uri'] = asset.uri + '?representation=original'
                    asset.representation = 'optimized_on_demand'
                    asset.sha256 = None  # The derivative does not have the original's checksum.
                    asset.uri += '?representation=optimized'

    browser_packs=OrderedDict()
    asset_fields={}
    browser_pack_lock=RLock()
    def browser_pack(dataset_id,result_ids=None):
        """The browser-facing preview pack with the chosen runs attached.

        Built once per (pack revision, attached runs) and shared read-only by
        queries, fields and aggregates; rebuilding and re-exposing every asset
        on each request made ordinary browsing requests cost 100+ ms each.
        Media handles are re-bound on every use because their LRU is bounded."""
        from dataset_atlas.queries.results import attach_results
        base=registry.pack(dataset_id)
        candidates={a.id:a for a in base.artifacts}
        if jobs:
            candidates.update({a.id:a for a in jobs.list_artifacts({base.dataset.snapshot_id})})
        if result_ids is None: result_ids=list(candidates)
        if any(id not in candidates for id in result_ids):raise ValueError('Requested result snapshot is unavailable')
        key=(dataset_id,tuple(result_ids))
        with browser_pack_lock:
            cached=browser_packs.get(key)
            if cached is not None and cached[0] is base:
                browser_packs.move_to_end(key)
                for token,value in cached[2]:media_handles[token]=value
                return cached[1]
        pack=attach_results(base,[candidates[id] for id in result_ids])
        pack.dataset.adapter_config={}
        handles=[]
        for record in pack.records:
            for asset in record.assets:
                if asset.uri and not asset.uri.startswith(('https://','http://','data:')):
                    expose_asset(dataset_id, asset, record.snapshot_id, allow_compact=False)
                    token=asset.uri.rsplit('/',1)[-1].split('?',1)[0]
                    handles.append((token,media_handles.get(token)))
        with browser_pack_lock:
            browser_packs[key]=(base,pack,handles)
            browser_packs.move_to_end(key)
            while len(browser_packs)>24:browser_packs.popitem(last=False)
        return pack
    from dataset_atlas.preparation import PreparationManager
    preparation=PreparationManager(root)
    @app.post('/api/v1/datasets/{dataset_id}/preparation/plan')
    def preparation_plan(dataset_id:str, body:PreparationPlanRequest):
        return preparation.plan(dataset_id,body.max_download_bytes,body.max_output_bytes,body.source_mode)
    def describe_source(inspection):
        # Local paths stay server-side: the interface needs what was found, not where the files live.
        return {key:value for key,value in inspection.items() if key!='adapter_config'}
    @app.post('/api/v1/local-datasets/inspect')
    def local_dataset_inspect(body:LocalDatasetRequest):
        from dataset_atlas.registry.user import inspect_source
        return describe_source(inspect_source(body.source,body.options))
    @app.post('/api/v1/local-datasets')
    def local_dataset_add(body:LocalDatasetRequest):
        from dataset_atlas.registry.user import inspect_source,register
        inspection=inspect_source(body.source,body.options)
        entry=register(root,inspection,name=body.name or inspection['suggested']['name'],dataset_id=body.dataset_id,description=body.description,replace=body.replace)
        registry.refresh()
        return {'dataset':present(registry.dataset(entry.id)),'inspection':describe_source(inspection)}
    @app.delete('/api/v1/local-datasets/{dataset_id}')
    def local_dataset_remove(dataset_id:str,purge:bool=False):
        from dataset_atlas.registry.user import unregister
        result=unregister(root,dataset_id,purge=purge)
        registry.refresh()
        return result
    @app.get('/api/v1/preparation')
    def preparation_list(dataset_id:str|None=None):return preparation.list(dataset_id)
    @app.post('/api/v1/preparation/{plan_id}/start')
    def preparation_start(plan_id:str):return preparation.start(plan_id)
    @app.get('/api/v1/preparation/{plan_id}')
    def preparation_status(plan_id:str):return preparation.status(plan_id)
    @app.post('/api/v1/preparation/{plan_id}/cancel')
    def preparation_cancel(plan_id:str):return preparation.cancel(plan_id)
    @app.get('/api/v1/capabilities')
    def capabilities():
        return Capabilities(mode='workbench',operations=['catalogue','query','selection','export','artifacts','providers','conversations','conversation-jobs','publication']+(['analysis','jobs'] if jobs else []))
    def present(dataset):
        """Public view of a dataset: no local adapter paths, and coverage corrected to what this workspace holds."""
        from dataset_atlas.catalogue import with_availability
        return with_availability(dataset.model_copy(update={'adapter_config':{}}),*registry.local_state(dataset.id))
    @app.get('/api/v1/datasets')
    def datasets():
        return [present(d) for d in registry.datasets()]
    @app.get('/api/v1/catalogue/thumbnails')
    def catalogue_thumbnails():
        """Real preview tiles per dataset so the catalogue never fabricates media.

        Derived from already-prepared packs and cached per pack revision. Media
        handles are re-bound on every request because the handle LRU is bounded.
        A dataset with no prepared preview simply has no entry."""
        from dataset_atlas.catalogue import summarize_records, thumbnails_document
        entries={}
        for dataset in registry.datasets():
            if not (dataset.coverage.preview_count or 0):continue
            active=registry.active_directory(dataset.id)
            path=active/'pack/pack.json' if active else work/'packs'/dataset.id/'pack.json'
            try:signature=(str(path),path.stat().st_mtime_ns,path.stat().st_size)
            except OSError:continue
            cached=thumbnail_cache.get(dataset.id)
            if cached is None or cached[0]!=signature:
                try:pack=registry.pack(dataset.id)
                except (FileNotFoundError,ValueError):continue
                summary=summarize_records(pack.records[:40])
                assets={a.id:a for record in pack.records for a in record.assets}
                tiles=[]
                for tile in summary['tiles']:
                    if tile['kind']!='image':tiles.append(dict(tile));continue
                    asset=next((a for a in assets.values() if a.uri==tile['uri']),None)
                    if asset is None:continue
                    tiles.append({'kind':'image','asset':asset.model_copy(deep=True)})
                cached=(signature,{'modality':summary['modality'],'tiles':tiles})
                thumbnail_cache[dataset.id]=cached
            resolved=[]
            for tile in cached[1]['tiles']:
                if tile['kind']!='image':resolved.append(tile);continue
                asset=tile['asset']
                if asset.uri and not asset.uri.startswith(('https://','http://','data:')):
                    token=content_id([dataset.id,dataset.snapshot_id,asset.id])
                    original=asset.model_copy(deep=True);original.metadata['_compact_snapshot_id']=dataset.snapshot_id
                    media_handles[token]=(dataset.id,original)
                    resolved.append({'kind':'image','uri':'/api/v1/media/'+token})
                else:
                    resolved.append({'kind':'image','uri':asset.uri})
            entries[dataset.id]={'modality':cached[1]['modality'],'tiles':resolved}
        return thumbnails_document(entries)
    @app.get('/api/v1/datasets/{dataset_id}')
    def dataset(dataset_id:str):return present(registry.dataset(dataset_id))
    def selected_artifacts(ids):
        if not ids:return []
        available={a.id:a for a in artifacts(artifact_ids=set(ids))}
        if len(set(ids))!=len(ids) or any(id not in available for id in ids):raise ValueError("Requested result snapshot is unavailable or duplicated")
        return [available[id] for id in ids]
    def complete_fields(dataset_id):
        snap=complete_snapshot(dataset_id)
        compatible=[a for a in artifacts({snap.snapshot_id}) if a.snapshot_ids==[snap.snapshot_id] and a.unit==snap.unit]
        fields=[f.model_copy(deep=True) for f in snap.query_fields(compatible)]
        try:
            descriptors={f.id:f for f in registry.pack(dataset_id).fields}
            for f in fields:
                if f.id in descriptors:f.values=descriptors[f.id].values
        except FileNotFoundError:pass
        return fields
    @app.get('/api/v1/datasets/{dataset_id}/complete')
    def complete_info(dataset_id:str):
        snap=complete_snapshot(dataset_id)
        return {'snapshot_id':snap.snapshot_id,'unit':snap.unit,'population_scope':snap.population_scope,'count_status':'exact','record_count':snap.record_count,'fields':complete_fields(dataset_id)}
    @app.get('/api/v1/datasets/{dataset_id}/pack')
    def pack(dataset_id:str):return browser_pack(dataset_id)
    @app.get('/api/v1/datasets/{dataset_id}/fields')
    def fields(dataset_id:str,unit:str='example',population_scope:str='preview',snapshot_id:str|None=None):
        if snapshot_id is not None:
            version=next((item for item in registry.versions(dataset_id) if item[0].snapshot_id==snapshot_id),None)
            if version is None:raise KeyError('Requested snapshot metadata unavailable')
            frozen=Pack.model_validate_json(version[1].read_text())
            if population_scope=='complete':
                from dataset_atlas.queries.parquet import ParquetSnapshot
                return ParquetSnapshot(version[2].parent,version[2]).query_fields([])
            if unit=='asset':
                from dataset_atlas.models import FieldDescriptor
                keys=sorted({key for row in materialize_records(frozen,'asset') for key in row.source})
                return [FieldDescriptor(id='source.'+key,name=key,unit='asset') for key in keys]
            return frozen.fields
        if population_scope=='complete':return complete_fields(dataset_id)
        pack=browser_pack(dataset_id)
        if unit!='asset':return pack.fields
        cached=asset_fields.get(dataset_id)
        if cached is None or cached[0] is not pack:
            from dataset_atlas.models import FieldDescriptor
            keys=sorted({key for row in materialize_records(pack,'asset') for key in row.source})
            cached=(pack,[FieldDescriptor(id='source.'+key,name=key,unit='asset') for key in keys])
            asset_fields[dataset_id]=cached
        return cached[1]
    @app.post('/api/v1/queries/{dataset_id}')
    def query(dataset_id:str,query:Query):
        if query.population_scope=='preview':return query_pack(browser_pack(dataset_id,query.result_snapshot_ids),query)
        response=complete_snapshot(dataset_id).query(query,selected_artifacts(query.result_snapshot_ids))
        for record in response.records:
            for asset in record.assets:
                if asset.uri:
                    expose_asset(dataset_id, asset, record.snapshot_id)
        return response
    @app.post('/api/v1/aggregate/{dataset_id}')
    def aggregate(dataset_id:str,body:AggregateRequest):
        """Distributions over the population a browsing query matched.

        The dataset overview uses this so its charts describe the real
        filtered population instead of whichever page happened to load."""
        from dataset_atlas.queries import aggregate_pack
        if body.query.population_scope=='preview':
            return aggregate_pack(browser_pack(dataset_id,body.query.result_snapshot_ids),body.query,body.field_ids,top=body.top)
        return complete_snapshot(dataset_id).aggregate(body.query,body.field_ids,selected_artifacts(body.query.result_snapshot_ids),top=body.top)
    @app.post('/api/v1/similarity/{dataset_id}')
    def similarity(dataset_id:str,body:SimilarityRequest):
        artifact=None
        if jobs:
            try:artifact=jobs.get_artifact(body.artifact_id)
            except KeyError:pass
        if artifact is None:artifact=selected_artifacts([body.artifact_id])[0]
        if body.query.snapshot_id not in artifact.snapshot_ids or body.query.unit!=artifact.unit:raise ValueError('Embedding artifact and query snapshot/unit differ')
        query_document=body.query.model_copy(update={'limit':1000,'cursor':None})
        if bool(body.record_id)==bool(body.text):raise ValueError('Choose exactly one query record or text query')
        if body.query.population_scope=='preview':
            import time
            deadline=time.monotonic()+30
            eligible_ids=[]
            while True:
                eligible=query_pack(browser_pack(dataset_id,body.query.result_snapshot_ids),query_document)
                eligible_ids.extend(r.id for r in eligible.records)
                if not eligible.cursor:break
                if time.monotonic()>deadline:raise ValueError('Retrieval population resolution exceeded 30 seconds; narrow the filter')
                query_document=query_document.model_copy(update={'cursor':eligible.cursor})
            population_scope,filtered=eligible.population_scope,eligible.matched_count
        else:  # a whole complete population is resolved as ids in one scan, not paged through as records
            eligible_ids=complete_snapshot(dataset_id).ids(query_document,selected_artifacts(body.query.result_snapshot_ids),timeout_seconds=30)
            population_scope,filtered='complete',len(eligible_ids)
        from dataset_atlas.queries.similarity import similar_records
        vector=None
        if body.text:
            from dataset_atlas.processors import encode_text_query
            if artifact.kind=='import.research':raise ValueError('Imported vectors have no executable encoder; query with a record from the registered space')
            if artifact.kind=='embed.api':
                saved=artifact.provenance.get('processor_provenance',{}).get('provider') or {}
                vector=encode_text_query(artifact,{},body.text,provider=loopback_provider(str(saved.get('id') or '')))
            else:
                if not jobs or not artifact.run_id:raise ValueError('Text query requires a retained encoder run')
                run=jobs.get_run(artifact.run_id)
                vector=encode_text_query(artifact,analysis_config(root,run.config,roots),body.text)
        result=similar_records(artifact,body.record_id,eligible_ids,body.limit,work/'vector-cache',query_vector=vector,artifact_dir=jobs.artifact_dir if jobs else None)
        result['population_scope']=population_scope
        result['coverage']={'filtered_records':filtered,'embedded_eligible_records':result['eligible_count']}
        return result
    def serve_asset(dataset_id,asset,request):
        from dataset_atlas.storage.compact import read_compact
        snapshot_id = asset.metadata.get('_compact_snapshot_id') or registry.dataset_version(dataset_id,asset.release_id).snapshot_id
        compact = read_compact(root, dataset_id, snapshot_id, asset.metadata.get('source_ref',asset.uri), media_byte_limit(asset))
        if compact and (request.query_params.get('representation') in {'compact', 'safe-view'} or compact[2]['representation'] == 'original'):
            response = media_response(compact[0], compact[1], request)
            requested = request.query_params.get('representation')
            response.headers['X-Atlas-Media-Representation'] = requested if requested in {'safe-view','display'} else compact[2]['representation']
            response.headers['X-Atlas-Original-SHA256'] = compact[2]['original_sha256']
            return response
        if request.query_params.get('representation') == 'compact':
            raise FileNotFoundError('Compressed browsing copy is not prepared')
        if request.query_params.get('representation') == 'optimized':
            if asset.modality != 'image': raise ValueError('Optimized browsing supports images only')
            from dataset_atlas.storage.optimized import optimized_image, storage_policy
            policy = storage_policy(root)
            if not policy or not policy.get('optimize_on_demand'): raise ValueError('On-demand compression is not enabled')
            if is_preview_asset(dataset_id, asset.id, snapshot_id):
                data, mime = original_media(dataset_id, asset)
                response = media_response(data, mime, request)
                response.headers['X-Atlas-Media-Representation'] = 'original'
                return response
            data, mime, proof = optimized_image(root, dataset_id, snapshot_id, asset.metadata.get('source_ref', asset.uri),
                                               lambda: original_media(dataset_id, asset)[0], cache_bytes=policy['optimized_cache_bytes'])
            response = media_response(data, mime, request)
            response.headers['X-Atlas-Media-Representation'] = proof['representation']
            response.headers['X-Atlas-Original-SHA256'] = proof['original_sha256']
            return response
        data, mime = original_media(dataset_id, asset)
        return media_response(data, mime, request)
    def retained_preview_media(dataset_id, asset):
        # Sampled remote previews materialize originals inside their immutable
        # version. Resolve that pack before considering native remote references.
        if asset.uri and not urlparse(asset.uri).scheme and not Path(asset.uri).is_absolute():
            try: preview = registry.pack(dataset_id)
            except FileNotFoundError: preview = None
            snapshot_id = asset.metadata.get('_compact_snapshot_id')
            if preview is not None and preview.dataset.release == asset.release_id and (not snapshot_id or preview.dataset.snapshot_id == snapshot_id):
                directory = registry.active_directory(dataset_id)
                pack_path = directory/'pack/pack.json' if directory else work/'packs'/dataset_id/'pack.json'
            else:
                version = next(((d, p) for d, p, _ in registry.versions(dataset_id)
                                if d.release == asset.release_id and (not snapshot_id or d.snapshot_id == snapshot_id)), None)
                if version is None: raise KeyError('Dataset preview version is not prepared')
                pack_path = version[1]
                if pack_path.is_file(): preview, _ = indexed_pack(pack_path)
                else: preview = None
            if preview is not None and asset.uri in preview.checksums:
                parent = pack_path.parent.resolve()
                path = (parent/asset.uri).resolve()
                if not path.is_relative_to(parent): raise ValueError('Preview media escapes its pack')
                from dataset_atlas.storage import read_rooted_file
                data = read_rooted_file(path, roots, media_byte_limit(asset))
                if hashlib.sha256(data).hexdigest() != preview.checksums[asset.uri]:
                    raise ValueError('Prepared preview media checksum changed')
                import mimetypes
                mime = mimetypes.guess_type(path.name)[0]
                if mime is None and asset.modality == 'image':
                    from PIL import Image
                    import io
                    with Image.open(io.BytesIO(data)) as image:
                        mime = Image.MIME.get(image.format)
                if mime is None and asset.modality == 'model3d':mime='model/gltf-binary'
                if mime is None and data.startswith(b'BM'):mime='image/bmp'
                if mime is None and asset.modality == 'video':
                    # Retained previews are stored under their content hash, without an extension, so the type comes from the container signature.
                    if data[4:8] == b'ftyp':mime='video/mp4'
                    elif data.startswith(b'\x1aE\xdf\xa3'):mime='video/webm'
                    elif data.startswith(b'RIFF') and data[8:12] == b'AVI ':mime='video/x-msvideo'
                if mime is None and asset.modality == 'audio':
                    declared=asset.metadata.get('original_media_type')
                    if declared in {'audio/ogg','audio/wav','audio/mpeg','audio/flac'}:mime=declared
                    elif data.startswith(b'OggS'):mime='audio/ogg'
                    elif data.startswith(b'fLaC'):mime='audio/flac'
                    elif data.startswith(b'RIFF') and data[8:12]==b'WAVE':mime='audio/wav'
                return data, mime or 'application/octet-stream', path
        return None
    def original_media(dataset_id, asset):
        retained = retained_preview_media(dataset_id, asset)
        if retained is not None:
            verify_selected_original(asset,retained[0])
            return retained[0], retained[1]
        path=asset_path(asset)
        if path.is_file():
            import mimetypes
            from dataset_atlas.storage import read_rooted_file
            data=read_rooted_file(path,roots,media_byte_limit(asset));verify_selected_original(asset,data)
            return data,mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        from dataset_atlas.adapters import resolve_dataset_asset
        handle=resolve_dataset_asset(registry.dataset_version(dataset_id,asset.release_id,asset.metadata.get('_compact_snapshot_id')),asset.metadata.get('source_ref',asset.uri),max_bytes=media_byte_limit(asset),cache_root=work/'media-cache/decoded',workspace_root=root)
        verify_selected_original(asset,handle.data)
        return handle.data,handle.media_type
    @app.api_route('/api/v1/media/{token}',methods=['GET','HEAD'])
    def media(token:str,request:Request):
        handle_entry=media_handles.get(token)
        if handle_entry is not None:
            dataset_id,asset=handle_entry
            return serve_asset(dataset_id,asset,request)
        for dataset_id in registry.ids():
            for dataset,path,_ in registry.versions(dataset_id):
                if not path.is_file():continue
                pack,_=indexed_pack(path)
                for record in pack.records:
                    for asset in record.assets:
                        if secrets.compare_digest(content_id([dataset.id,record.snapshot_id,asset.id]),token):
                            asset=asset.model_copy(deep=True);asset.metadata['_compact_snapshot_id']=record.snapshot_id
                            return serve_asset(dataset.id,asset,request)
        raise KeyError(token)
    @app.post('/api/v1/records')
    def get_records(body:RecordRequest):
        result=[]
        for id in body.ids:
            # Media is served lazily by token from the route below, exactly as for query pages;
            # materializing every asset here made a 100-record lookup cost seconds.
            original=find_record(id,prepare_media=False,snapshot_ids=body.snapshot_ids)
            if original is None:raise KeyError(id)
            record=original.model_copy(deep=True)
            for asset in record.assets:
                if asset.uri and not asset.uri.startswith(('https://','http://','data:')):
                    expose_asset(record.dataset_id, asset, record.snapshot_id)
            result.append(record)
        return result
    @app.get('/api/v1/selections')
    def selections():return state.list()
    @app.post('/api/v1/selections/population')
    def population_selection(body:PopulationRequest):
        dataset=registry.dataset(body.dataset_id)
        query=body.query
        if query.sample:raise ValueError('A sampled query selects through its pages; clear the sample to select the whole population')
        if query.population_scope=='complete':
            snapshot=complete_snapshot(body.dataset_id)
            ids=snapshot.ids(query,selected_artifacts(query.result_snapshot_ids),limit=body.limit)
        else:
            import time
            deadline=time.monotonic()+30
            ids=[];page=query
            while True:
                found=query_pack(browser_pack(body.dataset_id,query.result_snapshot_ids),page)
                ids.extend(record.id for record in found.records)
                if not found.cursor:break
                if len(ids)>body.limit:raise ValueError(f'The filter matches more than {body.limit:,} records; narrow it first')
                if time.monotonic()>deadline:raise ValueError('Resolving the population exceeded 30 seconds; narrow the filter')
                page=page.model_copy(update={'cursor':found.cursor,'limit':1000})
        if not ids:raise ValueError('The filter matches no records')
        selection=Selection(id='',name=body.name.strip() or f'{dataset.name} — {len(ids):,} {query.unit} records',ids=ids,unit=query.unit,snapshot_ids=[query.snapshot_id],
            dataset_ids=[body.dataset_id],method='population',query=query.model_dump(mode='json'),created_at=datetime.now(timezone.utc).isoformat(),size=len(ids))
        selection.id=content_id(selection.model_dump(exclude={'id'}),'selection-')
        state.put(selection);return state.summary(selection)
    @app.post('/api/v1/selections/import')
    def import_selection_payload(payload:dict):
        expected={'schema_version','selection','records','checksum','checksum_algorithm','notice'}
        if set(payload)-expected or payload.get('schema_version')!='1.0':raise ValueError('Unsupported selection exchange schema')
        contents={key:payload.get(key) for key in ('schema_version','selection','records')}
        from dataset_atlas.api.checksums import ALGORITHM,exchange_checksum
        algorithm=payload.get('checksum_algorithm')
        if algorithm not in {None,ALGORITHM}:raise ValueError('Unsupported selection checksum algorithm')
        actual=exchange_checksum(contents) if algorithm else hashlib.sha256(json.dumps(contents,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        if not secrets.compare_digest(actual,str(payload.get('checksum',''))):raise ValueError('Selection exchange checksum mismatch')
        selection=Selection.model_validate(contents['selection'])
        supplied=contents['records']
        if not isinstance(supplied,list) or not 1<=len(supplied)<=10000:raise ValueError('Selection import requires 1..10000 records')
        from dataset_atlas.exports import selection_export_payload
        # Validate supplied identities, then resolve trusted local records. Importing
        # a selection never overwrites source annotations with exchange contents.
        selection_export_payload(selection,[Record.model_validate(row) for row in supplied])
        selection_records(selection,prepare_media=False)
        state.put(selection)
        return selection
    @app.post('/api/v1/selections')
    def save_selection(selection:Selection):
        if not selection.ids or len(selection.ids)>10000:raise ValueError('Selection requires 1..10000 IDs')
        if len(set(selection.ids))!=len(selection.ids):raise ValueError('Duplicate selected IDs')
        selection_records(selection,prepare_media=False)
        if not selection.id:selection.id=content_id(selection.model_dump(exclude={'id'}),'selection-')
        state.put(selection);return selection
    @app.get('/api/v1/selections/{selection_id}')
    def get_selection(selection_id:str):return state.summary(state.get(selection_id))
    @app.get('/api/v1/selections/{selection_id}/export')
    def export_selection(selection_id:str):
        selection=state.get(selection_id)
        if len(selection.ids)>INLINE_SELECTION_IDS:raise ValueError(f'Portable export is limited to {INLINE_SELECTION_IDS:,} records; export a smaller selection or use the CLI')
        records=selection_records(selection,prepare_media=False)
        from dataset_atlas.exports import selection_export_payload
        payload=selection_export_payload(selection,records)
        from dataset_atlas.api.checksums import ALGORITHM,exchange_checksum
        payload['checksum']=exchange_checksum(payload)
        payload['checksum_algorithm']=ALGORITHM
        payload['notice']='Media omitted. Use CLI export for a checksummed portable pack.'
        return payload
    COLUMNAR={'project.pca','project.umap','cluster.kmeans','cluster.hdbscan','cluster.agglomerative','outlier.knn','embed.minilm','embed.siglip2'}
    MODEL_RUNS={'vlm.answer','vlm.tag','vlm.judge','embed.api'}  # talk to a local model server; always columnar
    SAVED_TEXT={'vlm.judge':'candidate_artifact_id','score.vqa_accuracy':'answers_artifact_id'}
    COLUMNAR_AUTO_ROWS=5000
    def loopback_provider(provider_id):
        """A configured model server as run settings; dataset contents only ever go to a loopback one."""
        from dataset_atlas.vlm.client import is_loopback
        if not service:raise ValueError('Model connections are unavailable')
        cfg=service.get_provider(provider_id).config
        if not is_loopback(cfg.base_url):raise ValueError('Dataset contents are sent only to a loopback model server; this provider is external')
        return {'id':cfg.id,'base_url':cfg.base_url,'model':cfg.model,'timeout_seconds':cfg.timeout_seconds,'max_output_tokens':cfg.max_output_tokens,
            'max_input_characters':cfg.max_input_characters,'max_images':cfg.max_images,'api_key_env':cfg.api_key_env}
    def run_config(processor_id,config,selection=None):
        path=root/'local-config/recipes.json'
        defaults=json.loads(path.read_text()) if path.exists() else {}
        merged={**defaults.get(processor_id,{}),**config}
        merged.pop('vector_source',None)  # only ever set below, from a registered artifact
        merged.pop('text_source',None)
        merged.pop('provider',None)
        if processor_id in MODEL_RUNS:
            provider_id=merged.pop('provider_id',None)
            if not provider_id:raise ValueError('Choose a model server for this run')
            merged['provider']=loopback_provider(provider_id)
            merged['resource_class']='network';merged['storage']='arrays'
        if processor_id in SAVED_TEXT:
            saved=merged.pop(SAVED_TEXT[processor_id],None)
            if saved:
                from dataset_atlas.queries.embedding_space import bulk_directory
                artifact=selected_artifacts([saved])[0]
                bulk=artifact.data.get('bulk')
                column=str(merged.get('answer_column','answer'))
                if not isinstance(bulk,dict) or column not in bulk.get('texts',{}):raise ValueError(f'Choose saved results with a {column!r} text column')
                merged['text_source']={'artifact_id':artifact.id,'dir':str(bulk_directory(artifact,jobs.artifact_dir)),'column':column,'manifest':{k:bulk[k] for k in ('count','ids','texts')}}
                merged['answers_artifact_id']=artifact.id
            merged['storage']='arrays'
        if processor_id=='score.vqa_accuracy':
            merged.setdefault('answers_field','source.answers');merged.setdefault('group_fields',['source.question_type','source.answer_type'])
        if processor_id in MODEL_RUNS or processor_id in SAVED_TEXT:
            from dataset_atlas.vlm.tasks import referenced_fields
            merged['record_fields']=referenced_fields(merged)  # the only record fields the run freezes beyond text and assets
        detector=merged.pop('detector_artifact_id',None)
        if processor_id=='detect.view':
            if not detector:raise ValueError('Choose a retained detector artifact')
            artifact=selected_artifacts([detector])[0]
            merged['detector_artifact']=artifact.model_dump(mode='json')
        elif detector:raise ValueError('Detector artifact input is only supported by threshold views')
        upstream=merged.pop('embedding_artifact_id',None)
        if upstream:
            from dataset_atlas.queries.embedding_space import embedding_source,embedding_vectors
            artifact=selected_artifacts([upstream])[0]
            if artifact.data.get('bulk'):
                source,provenance,metric=embedding_source(artifact,jobs.artifact_dir)
                merged['vector_source']=source
                merged['storage']='arrays'  # vectors by reference only make sense for a columnar run
            else:
                vectors,provenance,metric=embedding_vectors(artifact)
                merged['vectors']=vectors
            merged['embedding_space_id']=provenance.get('embedding_space_id')
            merged['embedding_run_id']=artifact.run_id or artifact.id
            merged['embedding_artifact_id']=artifact.id
            merged['embedding_snapshot_ids']=artifact.snapshot_ids
            merged['embedding_unit']=artifact.unit
            merged.setdefault('metric',metric)
        if selection is not None and processor_id in COLUMNAR and 'storage' not in merged and len(selection.ids)>COLUMNAR_AUTO_ROWS:
            merged['storage']='arrays'  # thousands of records are stored as arrays, not one JSON file each
        return analysis_config(root,merged,roots)
    app.state.selection_records=selection_records
    app.state.selection_by_id=lambda identity:state.get(identity)
    app.state.selection_ids=lambda identity:state.get(identity).ids
    app.state.run_config=run_config
    @app.get('/api/v1/processors')
    def processors():
        from dataset_atlas.processors import describe_processors
        descriptions=describe_processors()
        defaults_path=root/'local-config/recipes.json'
        defaults=json.loads(defaults_path.read_text()) if defaults_path.exists() else {}
        for descriptor in descriptions:
            descriptor['configured_recipe']=descriptor['id'] in defaults or not descriptor.get('requires_local_model',False)
        return descriptions

    def publication_operation(body, build=False):
        from dataclasses import asdict
        from dataset_atlas.exports import build_publication, validate_publication
        destination=work/'publication'
        if destination.is_symlink() or not destination.resolve().is_relative_to(work.resolve()):raise ValueError('Publication output must remain inside the workspace')
        operation=build_publication if build else validate_publication
        with publication_lock:
            result=operation(registry_dir=root/'registry', packs_dir=(root/'examples/approved-packs' if (root/'examples/approved-packs').is_dir() else root/'work/packs'),
                             output_dir=destination, profile_path=root/'registry/publication.json', max_bytes=body.max_bytes)
        return {**asdict(result),'output_dir':str(result.output_dir), 'profile':'public', 'remote_published':False, 'built':build}

    @app.post('/api/v1/publication/validate')
    def publication_validate(body:PublicationRequest):
        return publication_operation(body)

    @app.post('/api/v1/publication/build')
    def publication_build(body:PublicationRequest):
        return publication_operation(body,build=True)
    @app.get('/api/v1/runs')
    def runs():return jobs.list_runs() if jobs else []
    @app.post('/api/v1/runs/estimate')
    def estimate_run(body:RunRequest):
        if not jobs:raise HTTPException(503,'Job coordinator unavailable')
        selection=state.get(body.selection_id)
        config=run_config(body.processor_id,body.config,selection)
        return jobs.estimate(selection,local_run_records(selection,body.processor_id,config),body.processor_id,config)
    def local_run_records(selection,processor_id,config):
        if config.get('storage')=='arrays' and selection.method=='population' and processor_id.startswith(('project.','cluster.','outlier.')) and len(selection.dataset_ids)==1 and len(selection.snapshot_ids)==1:
            # These read vectors by id and never touch record content, and a population selection came from the snapshot itself:
            # its identity is the snapshot's, so no record needs to be read at all.
            try:snapshot=complete_snapshot(selection.dataset_ids[0])
            except (ValueError,FileNotFoundError,KeyError):snapshot=None
            if snapshot is not None and snapshot.snapshot_id==selection.snapshot_ids[0] and snapshot.unit==selection.unit:
                from dataset_atlas.models import Record as IdentityRecord
                return [IdentityRecord(id=identity,dataset_id=snapshot.dataset_id,release_id=snapshot.release_id,snapshot_id=snapshot.snapshot_id,unit=snapshot.unit) for identity in selection.ids]
        records=selection_records(selection,prepare_media=False)
        from dataset_atlas.vlm.tasks import PRESETS
        sends_images=processor_id.startswith('vlm.') and bool(config.get('use_images',PRESETS[processor_id.split('.',1)[1]]['use_images']))
        image_input=processor_id in {'quality.basic','detect.nudenet','detect.coco_v1'} or (processor_id=='embed.siglip2' and config.get('representation','image')=='image') or sends_images
        if not image_input:return records
        try:
            return [prepared_record(record,registry.dataset_version(record.dataset_id,record.release_id,record.snapshot_id),allow_source_read=False) for record in records]
        except FileNotFoundError as exc:
            raise ValueError('Selected originals are not retained locally. Inspect the selected images or run bounded dataset preparation before estimating analysis; estimation does not acquire media.') from exc
    @app.post('/api/v1/runs')
    def create_run(body:RunRequest):
        if not jobs:raise HTTPException(503,'Job coordinator unavailable')
        selection=state.get(body.selection_id)
        config=run_config(body.processor_id,body.config,selection)
        records=local_run_records(selection,body.processor_id,config)
        estimate=jobs.estimate(selection,records,body.processor_id,config)
        if body.estimate_digest!=estimate['estimate_digest']:raise ValueError('Preview the run estimate and approve its unchanged budget before starting')
        return jobs.create(selection,records,body.processor_id,config,estimate=estimate)
    @app.get('/api/v1/runs/{run_id}')
    def run(run_id:str):
        if not jobs:raise HTTPException(503,'Job coordinator unavailable')
        return jobs.get_run(run_id)
    @app.post('/api/v1/runs/{run_id}/cancel')
    def cancel(run_id:str):
        if not jobs:raise HTTPException(503,'Job coordinator unavailable')
        return jobs.cancel(run_id)
    @app.post('/api/v1/runs/{run_id}/retry')
    def retry(run_id:str):
        if not jobs:raise HTTPException(503,'Job coordinator unavailable')
        return jobs.retry(run_id)
    from dataset_atlas.registry.artifacts import RetainedArtifactIndex, merge_artifacts
    retained_artifact_index=RetainedArtifactIndex(registry)
    def artifacts(snapshot_ids=None,artifact_ids=None):
        if jobs and artifact_ids is not None:
            result=[]
            for identity in artifact_ids:
                try:
                    item=jobs.get_artifact(identity)
                    if snapshot_ids is None or snapshot_ids.intersection(item.snapshot_ids):result.append(item)
                except KeyError:pass
        else:result=list(jobs.list_artifacts(snapshot_ids)) if jobs else []
        result.extend(retained_artifact_index.list(snapshot_ids,artifact_ids=artifact_ids))
        return merge_artifacts(result)
    def dataset_snapshot_ids(dataset_id):
        """Every snapshot a dataset's browsing can use: prepared versions and its complete index."""
        snapshots={registry.dataset(dataset_id).snapshot_id}
        snapshots.update(d.snapshot_id for d,_,_ in registry.versions(dataset_id))
        try:snapshots.add(complete_snapshot(dataset_id).snapshot_id)
        except (ValueError,FileNotFoundError):pass
        return {s for s in snapshots if s}
    def without_vectors(value):
        if isinstance(value,dict):return {k:without_vectors(v) for k,v in value.items() if k!='vector'}
        if isinstance(value,list):return [without_vectors(v) for v in value]
        return value
    browse_views={}
    def browse_view(artifact):
        """Omit embedding vectors, which browsing never renders; the full artifact stays at /artifacts/{id}."""
        if not artifact.kind.startswith('embed.') or not isinstance(artifact.data,dict):return artifact
        cached=browse_views.get(artifact.id)
        if cached is None or cached[0] is not artifact:
            data={k:without_vectors(v) if k in {'items','points'} else v for k,v in artifact.data.items()}
            data['omitted_fields']=['vector']
            cached=(artifact,artifact.model_copy(update={'data':data}))
            browse_views[artifact.id]=cached
        return cached[1]
    @app.get('/api/v1/artifacts')
    def list_artifacts(dataset_id:str|None=None,view:str='full'):
        if view not in {'full','browse'}:raise ValueError('Artifact view must be full or browse')
        result=artifacts(dataset_snapshot_ids(dataset_id) if dataset_id else None)
        return [browse_view(a) for a in result] if view=='browse' else result
    @app.get('/api/v1/artifacts/{artifact_id}')
    def artifact(artifact_id:str):
        if jobs:
            try:return jobs.get_artifact(artifact_id)
            except KeyError:pass
        for a in artifacts(artifact_ids={artifact_id}):
            if (a.id if hasattr(a,'id') else a['id'])==artifact_id:return a
        raise KeyError(artifact_id)
    def bulk_array(artifact_id,name):
        from dataset_atlas.queries.embedding_space import bulk_directory
        item=jobs.get_artifact(artifact_id) if jobs else None
        bulk=item.data.get('bulk') if item else None
        if not isinstance(bulk,dict):raise HTTPException(404,'Artifact is not array-backed')
        entry={**bulk.get('arrays',{}),**bulk.get('extras',{})}.get(name)
        if name!='ids' and entry is None:raise HTTPException(404,'No such array')
        return bulk,bulk_directory(item,jobs.artifact_dir),entry
    immutable={'Cache-Control':'public, max-age=31536000, immutable'}  # artifact IDs are content digests
    @app.get('/api/v1/artifacts/{artifact_id}/ids')
    def artifact_ids(artifact_id:str):
        from fastapi.responses import FileResponse
        bulk,directory,_=bulk_array(artifact_id,'ids')
        return FileResponse(directory/bulk['ids']['file'],media_type='application/json',headers=immutable)
    @app.get('/api/v1/artifacts/{artifact_id}/texts/{name}')
    def artifact_texts(artifact_id:str,name:str):
        """A text column (answers, labels, verdicts) as a JSON array aligned with the artifact's ids."""
        from fastapi.responses import FileResponse
        from dataset_atlas.queries.embedding_space import bulk_directory
        item=jobs.get_artifact(artifact_id) if jobs else None
        bulk=item.data.get('bulk') if item else None
        entry=(bulk or {}).get('texts',{}).get(name)
        if entry is None:raise HTTPException(404,'No such text column')
        return FileResponse(bulk_directory(item,jobs.artifact_dir)/entry['file'],media_type='application/json',headers=immutable)
    @app.get('/api/v1/datasets/{dataset_id}/column/{artifact_id}')
    def dataset_column(dataset_id:str,artifact_id:str,field_id:str,snapshot_id:str,result:list[str]=QueryParam(default=[]),top:int=24):
        """A dataset field's value for every row of an array-backed result, in that result's row order.

        A map uses this to colour all of its points by a field of the complete index, not only the records loaded into the page.
        Numbers come back as float32 (NaN where missing), categories as int16 codes; the meta header names the categories."""
        import numpy as np
        from urllib.parse import quote
        from dataset_atlas.queries.embedding_space import bulk_directory
        from dataset_atlas.storage import arrays as store
        item=jobs.get_artifact(artifact_id) if jobs else None
        bulk=item.data.get('bulk') if item else None
        if not isinstance(bulk,dict):raise ValueError('Colouring by a field needs an array-backed result')
        snapshot=complete_snapshot(dataset_id)
        if snapshot_id!=snapshot.snapshot_id or snapshot_id not in item.snapshot_ids:raise ValueError('The result and the complete index are over different snapshots')
        ids=store.read_ids(bulk_directory(item,jobs.artifact_dir),bulk)
        answer=snapshot.column_values(ids,field_id,selected_artifacts(result),top=top)
        array=answer.pop('values' if answer['kind']=='number' else 'codes')
        return Response(array.tobytes(),media_type='application/octet-stream',headers={'X-Atlas-Dtype':str(array.dtype),'X-Atlas-Shape':str(len(array)),
            'X-Atlas-Column':quote(json.dumps(answer,ensure_ascii=False)),'Access-Control-Expose-Headers':'X-Atlas-Dtype, X-Atlas-Shape, X-Atlas-Column'})
    @app.get('/api/v1/artifacts/{artifact_id}/arrays/{name}')
    def artifact_array(artifact_id:str,name:str):
        """One array as raw little-endian C-order bytes; dtype and shape are in the headers."""
        import numpy as np
        from fastapi.responses import StreamingResponse
        _,directory,entry=bulk_array(artifact_id,name)
        path=directory/entry['file']
        with path.open('rb') as stream:
            major,minor=np.lib.format.read_magic(stream)
            (np.lib.format.read_array_header_2_0 if major>=2 else np.lib.format.read_array_header_1_0)(stream)
            offset=stream.tell()
        def body():
            with path.open('rb') as stream:
                stream.seek(offset)
                while chunk:=stream.read(1<<20):yield chunk
        return StreamingResponse(body(),media_type='application/octet-stream',headers={**immutable,'Content-Length':str(path.stat().st_size-offset),
            'X-Atlas-Dtype':entry['dtype'],'X-Atlas-Shape':','.join(map(str,entry['shape'])),'Access-Control-Expose-Headers':'X-Atlas-Dtype, X-Atlas-Shape'})
    try:
        from dataset_atlas.providers import ProviderService, create_provider_router
        from dataset_atlas.api.tools import make_tool_backend
        def external_policy(record,context):
            rights=registry.dataset_version(record.dataset_id,record.release_id,record.snapshot_id).rights
            return (rights.get('external_provider')=='approved' and rights.get('records')=='approved' and (not context.image_asset_ids or rights.get('images')=='approved') and (not (context.include_annotations or context.fields) or rights.get('annotations')=='approved'))
        def context_image(record,asset):
            selected=record.model_copy(update={'assets':[asset],'asset_ids':[asset.id]})
            dataset=registry.dataset_version(record.dataset_id,record.release_id,record.snapshot_id)
            return prepared_record(selected,dataset,allow_source_read=False).assets[0]
        def context_records(context):
            records=[]
            for identity in context.record_ids:
                record=find_record(identity,prepare_media=False,snapshot_ids=context.snapshot_ids)
                if record is None:raise ValueError('Selected context record is unavailable in its inspected snapshot')
                records.append(record)
            if not context.result_snapshot_ids:return records
            from dataset_atlas.models import Pack
            from dataset_atlas.queries.results import attach_results
            chosen=selected_artifacts(context.result_snapshot_ids)
            if any(not any(record.snapshot_id in artifact.snapshot_ids and record.unit==artifact.unit for record in records) for artifact in chosen):
                raise ValueError('Selected context result has an incompatible snapshot or unit')
            joined={}
            groups={ (r.dataset_id,r.release_id,r.snapshot_id,r.unit) for r in records }
            for dataset_id,release,snapshot,unit in groups:
                rows=[r for r in records if (r.dataset_id,r.release_id,r.snapshot_id,r.unit)==(dataset_id,release,snapshot,unit)]
                applicable=[a for a in chosen if snapshot in a.snapshot_ids and a.unit==unit]
                dataset=registry.dataset_version(dataset_id,release,snapshot)
                pack=attach_results(Pack(dataset=dataset,fields=[],records=rows),applicable)
                joined.update({r.id:r for r in pack.records})
            return [joined[r.id] for r in records]
        service=ProviderService(config_path=root/'local-config/providers.json',record_lookup=lambda identity:find_record(identity,prepare_media=False),version_record_lookup=lambda identity,snapshots:find_record(identity,prepare_media=False,snapshot_ids=snapshots),context_records_lookup=context_records,image_roots=roots,image_lookup=context_image,tool_backend=make_tool_backend(registry,lambda identity: find_record(identity,prepare_media=False),jobs,()),external_record_policy=external_policy)
        app.include_router(create_provider_router(service),prefix='/api/v1')
    except ImportError:pass
    web=root/'apps/web/dist'
    if not web.is_dir():web=Path(__file__).resolve().parents[1]/'web'
    if web.is_dir():
        index=web/'index.html'
        @app.get('/',include_in_schema=False)
        def home():
            # The page served by the workbench is the workbench; only a static host lacks this marker.
            html=index.read_text().replace('<head>','<head>\n    <meta name="atlas-mode" content="workbench" />',1)
            return HTMLResponse(html,headers={'Cache-Control':'no-cache'})
        app.mount('/',StaticFiles(directory=web,html=True),name='web')
    else:
        @app.get('/')
        def no_web():return {'message':'Frontend not built. Run npm ci && npm run build in apps/web, then restart atlas serve.','api':'/docs'}
    return app
