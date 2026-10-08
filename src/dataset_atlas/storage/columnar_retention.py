"""Retire acquired Parquet bodies after pinning native images and cold checks.

Canonical records and frozen identities stay intact. Routes map their original
embedded references to a revision/ETag-pinned shard and its measured image SHA.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

from dataset_atlas.adapters.core import PreparedSource
from dataset_atlas.adapters.remote_columnar import RemoteColumnarAdapter
from dataset_atlas.models import Dataset
from .indexed_tar import route_path
from .retention import _local_config_path


def read_columnar_member(index,member,*,max_bytes,transfer_bytes=1_000_000_000,cache=None):
    index=Path(index);receipt=json.loads((index/'receipt.json').read_text())
    if receipt['format']!='atlas-remote-parquet-images-v1':raise ValueError('Native Parquet route format changed')
    with (index/'members.sqlite').open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=receipt['members_sha256']:raise ValueError('Native Parquet image index checksum changed')
    with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT remote_ref,sha256,bytes FROM members WHERE name=?',(member,)).fetchone()
    if row is None:raise FileNotFoundError('Original embedded image has no native route')
    if row[2]>max_bytes:raise ValueError('Original embedded image exceeds byte budget')
    dataset=Dataset.model_validate(receipt['reader_dataset'])
    dataset.adapter_config.update(remote_cache_root=str(cache.root) if cache else str(index/'range-cache'),
        remote_cache_bytes=1_000_000_000,metadata_transfer_bytes=transfer_bytes,media_transfer_bytes=transfer_bytes,
        aggregate_transfer_bytes=transfer_bytes)
    adapter=RemoteColumnarAdapter(dataset)
    source=PreparedSource(dataset.id,dataset.release,max_bytes,1,'native remote Parquet')
    # This is original-byte retrieval. Safe-view and processors enforce their
    # own decoded-pixel limits; no raster is expanded by the retention route.
    handle=adapter.resolve_original_asset(source,row[0])
    if handle.sha256!=row[1] or len(handle.data)!=row[2]:raise ValueError('Cold Parquet image differs from the measured native original')
    return handle.data,{'sha256':handle.sha256,'transferred_bytes':adapter.bytes_fetched+adapter.media_bytes_fetched,
        'source_ref':row[0],'media_type':handle.media_type,'integrity':'Native original image SHA-256 verified; remote consistency is ETag-bound.'}


def retire_columnar_sources(root,dataset_id,*,max_source_bytes,max_preview_bytes,max_transfer_bytes,max_index_bytes=250_000_000,execute=False):
    """Use a preparation writer lease so this dataset cannot change underneath us."""
    from dataset_atlas.preparation import PreparationManager
    from dataset_atlas.preparation.slots import try_writer_slot
    from .optimized import preparation_headroom
    root=Path(root).resolve()
    if (root/'work').is_symlink():raise ValueError('Retirement requires an Atlas-owned work directory')
    if min(max_source_bytes,max_preview_bytes,max_transfer_bytes,max_index_bytes)<1:raise ValueError('Positive retirement budgets required')
    manager=PreparationManager(root)
    lease=try_writer_slot(manager.directory,manager.registry.resolve(dataset_id))
    if lease is None:raise ValueError('Dataset or preparation writers are busy; retry retirement when idle')
    with lease:
        admission=preparation_headroom(root,1_000_000_000+max_preview_bytes+max_index_bytes,manager._storage_reservations())
        if admission and not admission['admitted']:raise ValueError('Insufficient shared storage headroom for bounded retirement verification')
        return _retire_columnar_sources(root,dataset_id,max_source_bytes=max_source_bytes,max_preview_bytes=max_preview_bytes,
            max_transfer_bytes=max_transfer_bytes,max_index_bytes=max_index_bytes,execute=execute)


def _retire_columnar_sources(root,dataset_id,*,max_source_bytes,max_preview_bytes,max_transfer_bytes,max_index_bytes,execute):
    import pyarrow.parquet as pq
    from dataset_atlas.preparation import atomic
    from dataset_atlas.registry import Registry
    from dataset_atlas.storage import BoundedCache
    from .ranges import range_fingerprint
    from .compact import compact_entry,pin_preview_originals,read_compact
    root=Path(root).resolve();registry=Registry(root);dataset=registry.dataset(dataset_id)
    if dataset.adapter!='columnar':raise ValueError('Retirement requires an acquired native ColumnarAdapter population')
    files=dataset.adapter_config['files']
    if not files or any(f.get('format')!='parquet' or not re.match(r'https://huggingface\.co/datasets/[^/]+/[^/]+/resolve/[a-f0-9]{40}/',f.get('url','')) for f in files):
        raise ValueError('Retirement requires pinned native Hugging Face Parquet sources')
    if sum(f['bytes'] for f in files)>max_source_bytes:raise ValueError('Native source bodies exceed approved verification budget')
    hosts=['huggingface.co','cdn-lfs-us-1.huggingface.co','cdn-lfs-eu-1.huggingface.co','cdn-lfs.huggingface.co','us.aws.cdn.hf.co','eu.aws.cdn.hf.co','cas-bridge.xethub.hf.co']
    owned=[root/'work/sources',root/'work/prepared',root/'work/source-objects',root/'work/download-cache']
    bodies={};native_files=[];total_transfer=0;media_columns=set()
    for f in files:
        configured=Path(f['path']);configured=configured if configured.is_absolute() else root/configured
        if configured.is_symlink():raise ValueError('Native source retirement cannot follow symlinks')
        path=configured.resolve()
        if not any(path.is_relative_to(p) for p in owned) or not path.is_file():raise ValueError('Only acquired Atlas-owned native source bodies can be retired')
        with path.open('rb') as stream:
            if path.stat().st_size!=f['bytes'] or hashlib.file_digest(stream,'sha256').hexdigest()!=f['sha256']:
                raise ValueError('Native Parquet source differs from its complete checksum')
        info=path.stat();bodies[(info.st_dev,info.st_ino)]=(path,f['sha256'],info.st_nlink)
        if total_transfer>=max_transfer_bytes:raise ValueError('Native source probes exceed aggregate transfer budget')
        native_files.append({k:f[k] for k in ('source_name','url','bytes','sha256')}|{
            'etag':range_fingerprint(f['url'],expected_size=f['bytes'],allowed_hosts=hosts,probe_method='GET',
                credential_profile=dataset.adapter_config.get('credential_profile')),
            'rows':pq.read_metadata(path).num_rows})
        total_transfer+=1
        import pyarrow as pa
        for field in pq.read_schema(path):
            dtype=field.type
            if pa.types.is_list(dtype) or pa.types.is_large_list(dtype):dtype=dtype.value_type
            if pa.types.is_binary(dtype) or pa.types.is_large_binary(dtype) or (pa.types.is_struct(dtype) and 'bytes' in [v.name for v in dtype]):
                media_columns.add(field.name)
            elif (pa.types.is_string(dtype) or pa.types.is_large_string(dtype)) and dataset.adapter_config.get('media_encoding')=='base64' and field.name in dataset.adapter_config.get('media_columns',[]):
                media_columns.add(field.name)
    versions=[];routes=[];preview_upper_bound=0;index_bytes=0
    checksum_files={f['sha256']:i for i,f in enumerate(native_files)}
    if len(checksum_files)!=len(native_files):raise ValueError('Duplicate native shard checksums require an explicit source mapping')
    for version,pack_path,snapshot in registry.versions(dataset.id):
        affected={f.get('sha256') for f in version.adapter_config.get('files',[])} & set(checksum_files)
        if not affected:continue
        if version.adapter!='columnar' or not snapshot.is_dir():raise ValueError('A dependent version has no immutable complete Columnar snapshot')
        manifest=json.loads((snapshot/'manifest.json').read_text())
        with (snapshot/'records.parquet').open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=manifest['checksums']['records.parquet']:raise ValueError('Dependent canonical snapshot checksum changed')
        identity='parquet-'+hashlib.sha256(json.dumps([version.id,version.snapshot_id,native_files],sort_keys=True).encode()).hexdigest()[:32]+'-'+uuid.uuid4().hex
        index=root/'work/original-access'/identity;index.mkdir(parents=True,exist_ok=True)
        table=index/'members.sqlite'
        per_file={};references=0
        with sqlite3.connect(table) as db:
            db.execute('CREATE TABLE members (name TEXT PRIMARY KEY,remote_ref TEXT NOT NULL,sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,file_index INTEGER NOT NULL)')
            for batch in pq.ParquetFile(snapshot/'records.parquet').iter_batches(columns=['record_json'],batch_size=256):
                for value in batch.column(0).to_pylist():
                    record=json.loads(value);origin=record['source'].get('_atlas_origin',{})
                    if origin.get('sha256') not in checksum_files:continue
                    file_index=checksum_files[origin['sha256']];native_row=origin['row']
                    if type(native_row) is not int or not 0<=native_row<native_files[file_index]['rows']:raise ValueError('Native row origin differs from pinned shard')
                    for asset in record['assets']:
                        if not asset.get('uri'):continue
                        if asset['modality']!='image' or not re.fullmatch(r'embedded/[0-9]+/[0-9]+\.(png|jpg|webp|gif|avif)',asset['uri']):
                            raise ValueError('Unsupported dependent native media reference')
                        meta=asset['metadata'];column=meta['source_field'];slot=meta['source_slot'];sha=asset.get('sha256')
                        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',column) or type(slot) is not int or not 0<=slot<32 or not re.fullmatch('[a-f0-9]{64}',sha or ''):
                            raise ValueError('Native image provenance or measured SHA-256 missing')
                        if meta['sha256']!=sha or type(meta['bytes']) is not int or not 1<=meta['bytes']<=10_000_000:raise ValueError('Native image integrity fields disagree')
                        remote=f'remote/{file_index}/{native_row}/{column}/{slot}.png'
                        db.execute('INSERT INTO members VALUES (?,?,?,?,?)',(asset['uri'],remote,sha,meta['bytes'],file_index))
                        per_file.setdefault(file_index,[]).append(asset['uri']);references+=1
                if table.stat().st_size+index_bytes>max_index_bytes:raise ValueError('Native image index exceeds output budget')
            db.commit()
            if set(per_file)!={checksum_files[sha] for sha in affected}:raise ValueError('A native source shard has no measured dependent images')
        index_bytes+=table.stat().st_size
        if index_bytes>max_index_bytes:raise ValueError('Native image index exceeds output budget')
        with table.open('rb') as stream:table_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        reader=Dataset(id=version.id,name=version.name,release=version.release,snapshot_id=version.snapshot_id,adapter='remote_columnar',
            adapter_config={'remote_files':native_files,'allowed_hosts':hosts,'media_columns':sorted(media_columns),
                            'credential_profile':version.adapter_config.get('credential_profile'),
                            **({'media_encoding':version.adapter_config['media_encoding']} if version.adapter_config.get('media_encoding') else {})})
        atomic(index/'receipt.json',{'format':'atlas-remote-parquet-images-v1','members_sha256':table_sha,
            'reader_dataset':reader.model_dump(mode='json'),'source_full_sha256_verified':True,'image_references':references})
        # One cold original per source shard, then first/middle/last within the
        # population. The full index retains every native image's measured hash.
        probes=[refs[len(refs)//2] for refs in per_file.values()]
        all_refs=[ref for refs in per_file.values() for ref in refs]
        probes=list(dict.fromkeys(probes+[all_refs[i] for i in sorted({0,len(all_refs)//2,len(all_refs)-1})]))
        evidence=[];range_cache=BoundedCache(root/'work/media-cache/columnar-retirement',1_000_000_000)
        for ref in probes:
            remaining=max_transfer_bytes-total_transfer
            if remaining<1:raise ValueError('Cold native Parquet verification exceeds aggregate transfer budget')
            _,proof=read_columnar_member(index,ref,max_bytes=10_000_000,transfer_bytes=min(1_000_000_000,remaining),cache=range_cache)
            total_transfer+=proof['transferred_bytes'];evidence.append({'ref':ref,**proof})
        pack=json.loads(pack_path.read_text())
        preview_upper_bound+=sum(a['metadata']['bytes'] for r in pack['records'] for a in r['assets'] if a.get('uri'))
        if preview_upper_bound>max_preview_bytes:raise ValueError('Native preview originals exceed retention budget')
        if version.snapshot_id!=dataset.snapshot_id:
            # Frozen versions need their own protected originals; do not evict a
            # source when a prior preview cannot be proved byte-exact locally.
            for record in pack['records']:
                for asset in record['assets']:
                    if not asset.get('uri'):continue
                    compact=compact_entry(root,version.id,version.snapshot_id,asset['uri'])
                    if not compact or not compact.get('protected_preview') or compact.get('representation')!='original':
                        raise ValueError('Pin every prior frozen preview original before source retirement')
        elif execute:
            pin_preview_originals(root,dataset.id,max_input_bytes=max_preview_bytes,max_output_bytes=max_preview_bytes)
        if execute:
            for record in pack['records']:
                for asset in record['assets']:
                    if not asset.get('uri'):continue
                    result=read_compact(root,version.id,version.snapshot_id,asset['uri'],10_000_000)
                    if not result or not result[2].get('protected_preview') or hashlib.sha256(result[0]).hexdigest()!=asset['sha256']:
                        raise ValueError('Native preview original is not protected byte-exactly')
        target=route_path(root,version.id,version.snapshot_id)
        config=json.loads(target.read_text()) if target.is_file() else {'dataset_id':version.id,'snapshot_id':version.snapshot_id,'archives':[]}
        config['archives']=[{'index':identity,'asset_prefix':'embedded/','member_prefix':'embedded/'}]+[
            entry for entry in config['archives'] if entry.get('asset_prefix')!='embedded/']
        routes.append((target,config))
        versions.append({'snapshot_id':version.snapshot_id,'native_image_references':references,'index':identity,'cold_checks':evidence})
    if not versions:raise ValueError('No retained native image population depends on these Parquet files')
    paths={key:[] for key in bodies}
    for directory,children,names in os.walk(root/'work',followlinks=False):
        children[:]=[name for name in children if not (Path(directory)/name).is_symlink()]
        for name in names:
            path=Path(directory)/name
            if path.is_symlink():continue
            try:info=path.stat()
            except FileNotFoundError:continue
            key=(info.st_dev,info.st_ino)
            if key in paths:
                if not any(path.is_relative_to(p) for p in owned):raise ValueError('Native source hard link lies outside acquired-source directories')
                paths[key].append(path)
    for key,(body,_,links) in bodies.items():
        if len(paths[key])!=links or body.stat().st_nlink!=links:raise ValueError('Native source has unaccounted hard links')
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for item in value.values():yield from strings(item)
        elif isinstance(value,list):
            for item in value:yield from strings(item)
    for other in registry.datasets():
        if other.id==dataset.id:continue
        for version,_,_ in registry.versions(other.id):
            for value in strings(version.adapter_config):
                path=_local_config_path(root,value)
                if path is None:continue
                if path.is_file() and (path.stat().st_dev,path.stat().st_ino) in bodies:
                    raise ValueError('Native source is required by another retained dataset: '+other.id)
    freed=sum(body.stat().st_blocks*512 for body,_,_ in bodies.values())
    proof={'dataset_id':dataset.id,'executed':False,'status':'verified_plan','sources':native_files,'versions':versions,
        'total_verification_transfer_bytes':total_transfer,'native_index_bytes':index_bytes,'preview_bytes_upper_bound':preview_upper_bound,
        'source_paths_eligible':[str(p) for values in paths.values() for p in values],
        'source_paths_retired':[],'freed_source_allocated_bytes':0,
        'integrity':'Complete native Parquet SHA-256 and every canonical image SHA-256 retained. Preview originals pinned locally. Retrieved originals equal their measured native SHA-256.',
        'transfer_measurement':'One-byte source probes plus actual range payloads; validated ETag-bound cache hits transfer zero bytes. Verification can reuse those cached ranges.'}
    if execute:
        for target,config in routes:atomic(target,config)
        proof['status']='routes_installed'
        atomic(root/'work/original-access'/('columnar-retirement-'+dataset.id+'.json'),proof)
        for key,values in paths.items():
            body,expected,links=bodies[key]
            with body.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Native source changed during retirement verification')
            if body.stat().st_nlink!=links:raise ValueError('Native source hard links changed during retirement')
            for path in values:
                info=path.stat()
                if (info.st_dev,info.st_ino)!=key:raise ValueError('Native source path changed during retirement')
            for path in values:path.unlink()
        proof.update(status='executed',executed=True,freed_source_allocated_bytes=freed,
            source_paths_retired=proof['source_paths_eligible'])
        atomic(root/'work/original-access'/('columnar-retirement-'+dataset.id+'.json'),proof)
    return proof


def verify_retired_preview(root,dataset_id,*,max_transfer_bytes,max_preview_bytes,execute=False):
    """Re-derive a decoded preview from an immutable, retired native snapshot."""
    import io
    import time
    import tempfile
    import pyarrow.parquet as pq
    from PIL import Image
    from dataset_atlas.registry import Registry
    from dataset_atlas.models import Record,Pack
    from dataset_atlas.adapters.core import MediaHandle
    from dataset_atlas.adapters.remote_columnar import MediaLimitError
    from dataset_atlas.preparation import PreparationManager,atomic
    from dataset_atlas.preparation.slots import try_writer_slot
    from dataset_atlas.preparation.sampling import PreviewSampler,select_verified_remote_preview
    from .compact import read_compact,store_directory,encode_image
    from .indexed_tar import read_original_route
    from .optimized import preparation_headroom
    root=Path(root).resolve()
    if (root/'work').is_symlink() or min(max_transfer_bytes,max_preview_bytes)<1:raise ValueError('Owned workspace and positive preview budgets required')
    manager=PreparationManager(root);registry=Registry(root);dataset=registry.dataset(dataset_id)
    lease=try_writer_slot(manager.directory,dataset.id)
    if lease is None:raise ValueError('Dataset or preparation writers are busy; retry preview verification when idle')
    with lease:
        admission=preparation_headroom(root,1_000_000_000+max_preview_bytes,manager._storage_reservations())
        if admission and not admission['admitted']:raise ValueError('Insufficient shared preview verification headroom')
        directory=registry.active_directory(dataset.id)
        if directory is None or dataset.adapter!='columnar' or not route_path(root,dataset.id,dataset.snapshot_id).is_file():
            raise ValueError('A prepared native columnar snapshot with retained original routes is required')
        snapshot=directory/'snapshot';manifest=json.loads((snapshot/'manifest.json').read_text());path=snapshot/'records.parquet'
        with path.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=manifest['checksums']['records.parquet']:raise ValueError('Prepared canonical snapshot checksum changed')
        count=manifest['record_count'];sampler=PreviewSampler(min(count,250))
        for batch in pq.ParquetFile(path).iter_batches(columns=['record_json'],batch_size=256):
            for value in batch.column(0).to_pylist():sampler.add(Record.model_validate_json(value))
        if sampler.population_count!=count:raise ValueError('Prepared snapshot population count changed')
        payloads={};consumed=0;transferred=0
        def original(ref):
            nonlocal consumed,transferred
            if ref in payloads:data,mime=payloads[ref]
            else:
                local=read_compact(root,dataset.id,dataset.snapshot_id,ref,10_000_000)
                if local:data,mime,_=local
                else:
                    remaining=max_transfer_bytes-transferred
                    if remaining<1:raise ValueError('Native preview aggregate transfer budget exhausted')
                    found=read_original_route(root,dataset.id,dataset.snapshot_id,ref,10_000_000,transfer_bytes=remaining)
                    if found is None:raise FileNotFoundError('Native original preview reference has no retained route')
                    data,proof=found;mime=proof['media_type'];transferred+=proof['transferred_bytes']
                consumed+=len(data)
                if consumed>max_preview_bytes:raise ValueError('Native preview original-byte budget exhausted')
                with Image.open(io.BytesIO(data)) as image:
                    if image.width*image.height>50_000_000:raise MediaLimitError('Original image exceeds the 50-million-pixel preview decode limit')
                payloads[ref]=(data,mime)
            return MediaHandle(data,mime,hashlib.sha256(data).hexdigest(),ref)
        pack_path=directory/'pack/pack.json';before=pack_path.read_bytes();pack=Pack.model_validate_json(before)
        records,validation=select_verified_remote_preview(sampler.records(),original,min(count,100))
        result={'dataset_id':dataset.id,'snapshot_id':dataset.snapshot_id,'executed':execute,'preview_records':len(records),
            'index_rows':count,'index_sha256':digest,'preview_media_validation':validation,
            'original_bytes_read':consumed,'network_bytes_transferred':transferred,
            'max_transfer_bytes':max_transfer_bytes,'max_preview_bytes':max_preview_bytes,
            'previous_pack_sha256':hashlib.sha256(before).hexdigest(),'native_snapshot_changed':False,
            'note':'Every selected original image was decoded within the pixel cap. Oversized native examples remain in the complete index with original-byte access.'}
        if not execute:return result
        store=store_directory(root,dataset.id,dataset.snapshot_id);(store/'objects').mkdir(parents=True,exist_ok=True)
        import fcntl
        with (store/'writer.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with sqlite3.connect(store/'index.sqlite') as db:
                db.execute('CREATE TABLE IF NOT EXISTS media (ref TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
                written=0
                for record in records:
                    for asset in record.assets:
                        if asset.modality!='image' or not asset.uri:continue
                        data,mime=payloads[asset.uri];sha=hashlib.sha256(data).hexdigest()
                        if sha!=asset.sha256:raise ValueError('Verified preview original checksum changed')
                        _,_,meta=encode_image(data,protected=True);target=store/'objects'/sha
                        if target.exists():
                            if hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError('Protected preview object checksum changed')
                        else:
                            written+=len(data)
                            if written>max_preview_bytes:raise ValueError('Protected preview output exceeds byte budget')
                            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as stream:
                                temporary=Path(stream.name);stream.write(data)
                            try:os.replace(temporary,target)
                            finally:temporary.unlink(missing_ok=True)
                        meta.update(sha256=sha,bytes=len(data),mime=mime)
                        db.execute('INSERT OR REPLACE INTO media VALUES (?,?)',(asset.uri,json.dumps(meta,separators=(',',':'))))
                db.commit()
        pack.records=records;pack.sampling=sampler.description(dataset.release,dataset.coverage.unit)
        dataset.coverage.preview_count=len(records)
        dataset.coverage.preview='complete_target'
        pack.dataset=dataset.model_copy(update={'adapter_config':{}})
        pack.sampling.update(method='sha256_bottom_k_primary_asset_verified_media',requested_count=min(count,100),
            returned_count=len(records),candidate_pool_count=len(sampler.records()),
            selection_note='Lowest hash-ranked native candidates with every linked original image decoded within the pixel cap; excluded oversized examples remain available in the complete index.')
        receipt_path=directory/'receipt.json';receipt=json.loads(receipt_path.read_text());audit=directory/'preview-audits'/str(time.time_ns());audit.mkdir(parents=True)
        (audit/'previous-pack.json').write_bytes(before);(audit/'previous-receipt.json').write_bytes(receipt_path.read_bytes())
        receipt['preview_media_validation']=validation;receipt['preview_verified_at']=time.time();receipt['preview_verification']=result
        atomic(pack_path,pack.model_dump(mode='json'));atomic(directory/'dataset.json',dataset.model_dump(mode='json'));atomic(receipt_path,receipt)
        result['protected_original_bytes_added']=written
        result['prior_preview_audit']=str(audit.relative_to(root))
        return result
