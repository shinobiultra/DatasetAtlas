"""One isolated acquisition/index writer. Approved plans are immutable inputs."""
from __future__ import annotations
from contextlib import closing
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sys
import time
import zipfile
from . import PreparationManager, atomic


def run(root, identity):
    manager = PreparationManager(root)
    directory = manager._path(identity)
    plan = json.loads((directory / 'plan.json').read_text())
    status = {'id': identity, 'dataset_id': plan['dataset_id'], 'status': 'running', 'pid': os.getpid()}
    def update(**values):
        status.update(values, updated_at=time.time())
        atomic(directory / 'status.json', status)
    def check():
        if (directory / 'cancel').exists():
            raise InterruptedError('Preparation cancelled; verified source downloads are retained for retry.')
    from .slots import try_writer_slot
    while True:
        lock = try_writer_slot(manager.directory, plan['dataset_id'])
        if lock is not None:
            break
        if (directory/'cancel').exists():
            update(status='cancelled', error='Cancelled while waiting for preparation slot')
            return
        update(status='running', stage='waiting for preparation slot')
        time.sleep(.5)
    try:
        from dataset_atlas.models import Dataset, FieldDescriptor
        from dataset_atlas.adapters import get_adapter, build_preview
        from dataset_atlas.queries.parquet import build_parquet_snapshot
        dataset = Dataset.model_validate(plan['dataset'])
        if dataset.model_dump(mode='json') != manager.registry.dataset(dataset.id).model_dump(mode='json'):
            raise ValueError('Dataset configuration changed after planning; create a new plan.')
        if plan.get('recipe_sha256'):
            recipe_path=Path(root)/'registry/recipes'/f'{dataset.id}.yaml'
            if hashlib.sha256(recipe_path.read_bytes()).hexdigest()!=plan['recipe_sha256']:
                raise ValueError('Acquisition recipe changed; create a new plan')
        dataset=Dataset.model_validate(plan.get('prepared_dataset',plan['dataset']))
        if shutil.disk_usage(directory).free < plan['required_free_bytes']:
            raise ValueError('Insufficient free space for approved plan')
        base = Path(root) / 'work/prepared' / dataset.id
        version = base / identity
        version.mkdir(parents=True, exist_ok=True)
        check()
        update(stage='acquiring', downloaded_bytes=0)
        if plan['kind'] in {'huggingface_columnar','http_archive'}:
            from dataset_atlas.storage import BoundedCache, CacheIdentity, HttpsFetcher
            # Multipart source chunks are consumed into one verified archive as
            # they arrive, so retaining all chunks in the cache would double
            # the final storage footprint.
            cache_limit = (min(plan['max_download_bytes'], 600_000_000)
                           if any(entry.get('parts') for entry in plan['files']) else plan['max_download_bytes'])
            cache = BoundedCache(Path(root) / 'work/download-cache', max_bytes=cache_limit)
            fetcher = HttpsFetcher(['huggingface.co', 'cdn-lfs.huggingface.co', 'cdn-lfs-us-1.huggingface.co',
                'cdn-lfs-eu-1.huggingface.co', 'cas-bridge.xethub.hf.co', 'us.aws.cdn.hf.co', 'eu.aws.cdn.hf.co', 'www.robots.ox.ac.uk', 'thor.robots.ox.ac.uk']+plan.get('allowed_hosts',[]), timeout=60,
                max_bytes=plan['max_download_bytes'],credential_profile=plan.get('credential_profile'))
            files = []
            from .slots import transfer_slot
            with transfer_slot(manager.directory, check):
                for entry in plan['files']:
                    check()
                    from dataset_atlas.storage.sources import source_object
                    source=source_object(root,entry.get('sha256'),entry['bytes'])
                    link_only = entry['source_name'] in plan.get('reuse_registered_sources',[])
                    if link_only and source is None:
                        raise ValueError('Registered source reserved for reuse is missing; create a new plan')
                    if source is None and entry.get('parts'):
                        parts = entry['parts']
                        if not isinstance(parts, list) or not parts or sum(part['bytes'] for part in parts) != entry['bytes']:
                            raise ValueError('Multipart source parts differ from declared archive size')
                        source_dir = version / 'sources'
                        source_dir.mkdir(exist_ok=True)
                        target = source_dir / (entry['sha256'] + '.' + entry['format'])
                        partial = target.with_name(target.name + '.partial')
                        digest = hashlib.sha256()
                        transferred = 0
                        try:
                            with partial.open('wb') as combined:
                                for part in parts:
                                    check()
                                    chunk = fetcher.fetch(part['url'], cache,
                                        CacheIdentity(plan.get('revision', dataset.release), part['sha256'], 'original-part'),
                                        expected_sha256=part['sha256'], byte_budget=part['bytes'], cancel=check,
                                        progress=lambda total: update(downloaded_bytes=sum(f['bytes'] for f in files)+transferred+total,
                                                                      current_file=part['source_name']))
                                    if chunk.stat().st_size != part['bytes']:
                                        raise ValueError('Multipart source part length changed')
                                    with chunk.open('rb') as stream:
                                        for block in iter(lambda: stream.read(1 << 20), b''):
                                            check()
                                            digest.update(block)
                                            combined.write(block)
                                    transferred += part['bytes']
                            if digest.hexdigest() != entry['sha256'] or transferred != entry['bytes']:
                                raise ValueError('Concatenated multipart archive differs from pinned checksum')
                            os.replace(partial, target)
                            source = target
                        finally:
                            partial.unlink(missing_ok=True)
                    elif source is None:
                        source = fetcher.fetch(entry['url'], cache,
                            CacheIdentity(plan.get('revision',dataset.release), entry.get('sha256',entry.get('md5')), 'original'),
                            expected_sha256=entry.get('sha256'), byte_budget=entry['bytes'], cancel=check,
                            progress=lambda total:update(downloaded_bytes=sum(f['bytes'] for f in files)+total,current_file=entry['source_name']))
                    else:update(stage='reusing registered source',current_file=entry['source_name'])
                    digest=hashlib.sha256();md5=hashlib.md5(usedforsecurity=False)
                    with source.open('rb') as stream:
                        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk);md5.update(chunk)
                    if entry.get('sha256') and digest.hexdigest()!=entry['sha256']:
                        raise ValueError('Acquired source SHA-256 differs from the approved plan')
                    if entry.get('md5') and md5.hexdigest()!=entry['md5']:raise ValueError('Official source MD5 mismatch')
                    source_dir = version / 'sources'
                    source_dir.mkdir(exist_ok=True)
                    target = source_dir / (digest.hexdigest() + '.' + entry['format'])
                    if not target.exists():
                        try:
                            os.link(source, target)
                        except OSError as error:
                            if link_only:
                                raise ValueError('Registered source hard-link reuse failed; create a new plan') from error
                            # Cache and prepared roots may sit on different filesystems.
                            shutil.copy2(source, target)
                    files.append({**entry, 'sha256':digest.hexdigest(), 'path': str(target)})
                    if entry.get('config_key'):dataset.adapter_config[entry['config_key']]=str(target)
                    if entry.get('config_key')=='path':dataset.adapter_config['sha256']=digest.hexdigest()
                    update(downloaded_bytes=sum(f['bytes'] for f in files), current_file=entry['source_name'])
            dataset.adapter_config['source_files'] = files
            if plan['kind']=='huggingface_columnar':
                dataset.release = plan['revision']
            dataset.snapshot_id = f'{dataset.id}-{identity[:24]}'
            if plan['kind']=='huggingface_columnar':
                dataset.adapter = 'columnar'
                dataset.adapter_config = {**dataset.adapter_config, 'files': files, 'population': plan['scope'],
                    'mapping': {'text': 'text', 'question': 'question', 'choices': 'choices', **dataset.adapter_config.get('mapping', {})}}
        if plan['kind']=='huggingface_remote_columnar':
            from .remote import pin_remote_files
            hosts=['huggingface.co','cdn-lfs.huggingface.co','cdn-lfs-us-1.huggingface.co','cdn-lfs-eu-1.huggingface.co',
                   'cas-bridge.xethub.hf.co','us.aws.cdn.hf.co','eu.aws.cdn.hf.co']
            fingerprint_path=directory/'remote-shards.json'
            if fingerprint_path.is_file():
                remote_files=json.loads(fingerprint_path.read_text())
                if [{k:v for k,v in entry.items() if k!='etag'} for entry in remote_files]!=plan['files']:
                    raise ValueError('Saved remote shard fingerprints differ from the approved plan')
                update(stage='reusing pinned remote shards',pinned_shards=len(remote_files),total_shards=len(remote_files))
            else:
                remote_files=pin_remote_files(plan['files'],hosts,check,update)
                atomic(fingerprint_path,remote_files)
            dataset.release=plan['revision']
            dataset.snapshot_id=f'{dataset.id}-{identity[:24]}'
            dataset.adapter='remote_columnar'
            source_options={key:dataset.adapter_config[key] for key in ('record_filter','expected_source_count','fields','max_record_bytes','remote_cache_root','remote_cache_bytes') if key in dataset.adapter_config}
            dataset.adapter_config={'remote_files':remote_files,'allowed_hosts':hosts,
                'remote_cache_root':str(Path(root)/'work/media-cache/remote-parquet'),'remote_cache_bytes':1_000_000_000,
                'metadata_transfer_bytes':plan['max_download_bytes'],'population':plan['scope'],
                'mapping':dataset.adapter_config.get('mapping',{}),**source_options}
        derived_sources = []
        if dataset.adapter_config.get('archive_preparation') == 'indexed-gzip':
            from dataset_atlas.storage.indexed_tar import build_tar_index
            from dataset_atlas.storage.ranges import range_fingerprint
            original = Path(dataset.adapter_config['path'])
            entry = next(f for f in dataset.adapter_config['source_files'] if f.get('config_key') == 'path')
            hosts = ['huggingface.co','cdn-lfs.huggingface.co','cdn-lfs-us-1.huggingface.co',
                     'cas-bridge.xethub.hf.co','us.aws.cdn.hf.co',*plan.get('allowed_hosts', [])]
            index = Path(root) / 'work/original-access' / entry['sha256']
            update(stage='indexing original archive for selective retrieval')
            if entry.get('parts'):
                remote = {'bytes': entry['bytes'], 'parts': [
                    {'url': part['url'], 'bytes': part['bytes'], 'sha256': part['sha256'],
                     'allowed_hosts': hosts,
                     'etag': range_fingerprint(part['url'], expected_size=part['bytes'], allowed_hosts=hosts)}
                    for part in entry['parts']]}
            else:
                remote = {'url': entry['url'], 'bytes': entry['bytes'], 'allowed_hosts': hosts,
                          'etag': range_fingerprint(entry['url'], expected_size=entry['bytes'], allowed_hosts=hosts)}
            if (index / 'receipt.json').is_file():
                proof = json.loads((index / 'receipt.json').read_text())
                def remote_identity(value):
                    if 'parts' in value:
                        return (value['bytes'], [(part['url'], part['bytes'], part.get('sha256'), part['etag'])
                                                for part in value['parts']])
                    return (value['url'], value['bytes'], value['etag'])
                if proof['source_sha256'] != entry['sha256'] or remote_identity(proof['remote']) != remote_identity(remote):
                    raise ValueError('Existing original-access index differs from pinned source')
            else:
                proof = build_tar_index(original, index, source_sha256=entry['sha256'], remote=remote,
                    max_uncompressed_bytes=dataset.adapter_config.get('max_uncompressed_bytes', entry['bytes'] * 4),
                    max_index_bytes=plan['max_output_bytes'], cancel=check, progress=lambda values: update(**values))
            derived_sources.append({'format': proof['format'], 'path': str(index), 'bytes': proof['index_bytes'],
                                    'source_sha256': proof['source_sha256'], 'members': proof['members']})
            dataset.adapter_config.update(original_access_index=str(index), original_archive_path=str(original),
                path=str(index / 'members.sqlite'), sha256=proof['checksums']['members.sqlite'])
        repack_paths = dataset.adapter_config.get('repack_paths', [])
        if dataset.adapter_config.get('archive_preparation') == 'zip-store':
            repack_paths = ['path', *repack_paths]
        for path_key in dict.fromkeys(repack_paths):
            from dataset_atlas.storage.archive import repack_tar
            if not isinstance(path_key, str) or not re.fullmatch(r'[a-z_]+', path_key):
                raise ValueError('Invalid archive path configuration key')
            original=Path(dataset.adapter_config[path_key])
            if original.suffix != '.zip':
                update(stage='preparing random-access archive')
                target=version/'sources'/('original-members.zip' if path_key=='path' else path_key+'-members.zip')
                target.parent.mkdir(exist_ok=True)
                derived=repack_tar(original,target,plan['max_output_bytes']-sum(item['bytes'] for item in derived_sources),check,
                    compression=dataset.adapter_config.get('repack_compression','stored'),
                    max_uncompressed_bytes=dataset.adapter_config.get('repack_max_uncompressed_bytes'))
                derived_sources.append({**derived, 'path_key': path_key})
                dataset.adapter_config[path_key]=str(target)
                dataset.adapter_config.setdefault('derived_archive_checksums', {})[path_key]=derived['sha256']
                if path_key=='path':dataset.adapter_config['sha256']=derived['sha256']
        for step in dataset.adapter_config.get('repack_members', []):
            from dataset_atlas.storage.archive import repack_tar
            from dataset_atlas.adapters.core import _safe_relative
            path_key=step['target_key']
            if not isinstance(path_key, str) or not re.fullmatch(r'[a-z_]+', path_key):
                raise ValueError('Invalid archive target configuration key')
            update(stage='preparing nested random-access archive')
            target=version/'sources'/(path_key+'-members.zip')
            target.parent.mkdir(exist_ok=True)
            with zipfile.ZipFile(dataset.adapter_config[step['source_key']]) as outer:
                info=outer.getinfo(_safe_relative(step['member']))
                if info.is_dir() or info.file_size > plan['max_output_bytes']:
                    raise ValueError('Nested source archive exceeds approved output budget')
                with outer.open(info) as member:
                    derived=repack_tar(member,target,plan['max_output_bytes']-sum(item['bytes'] for item in derived_sources),check)
            derived_sources.append({**derived, 'path_key':path_key, 'source_member':step['member']})
            dataset.adapter_config[path_key]=str(target)
            dataset.adapter_config.setdefault('derived_archive_checksums', {})[path_key]=derived['sha256']
            if path_key=='path':dataset.adapter_config['sha256']=derived['sha256']
        derived_source=derived_sources[0] if len(derived_sources)==1 else None
        derived_bytes=sum(item['bytes'] for item in derived_sources)
        if not dataset.snapshot_id:
            dataset.snapshot_id=f'{dataset.id}-{identity[:24]}'
        # Freeze small derived source inventories alongside this immutable version.
        if dataset.adapter_config.get('media_inventory_path'):
            inventory=Path(dataset.adapter_config['media_inventory_path'])
            payload=inventory.read_bytes()
            digest=hashlib.sha256(payload).hexdigest()
            if digest!=dataset.adapter_config['media_inventory_sha256']:raise ValueError('Media inventory checksum changed')
            target=version/'sources'/(digest+'.inventory.json')
            target.parent.mkdir(exist_ok=True)
            if not target.exists():target.write_bytes(payload)
            dataset.adapter_config['media_inventory_path']=str(target)
        if dataset.adapter == 'pathways_shapes':
            from dataset_atlas.adapters.pathways_shapes import materialize
            update(stage='rendering pinned author generation recipe')
            generated = materialize(dataset,version/'sources/shapes',plan['max_output_bytes']-derived_bytes,check)
            derived_sources.append(generated)
            derived_bytes += generated['bytes']
        if dataset.adapter == 'visual_genome':
            dataset.adapter_config['join_index_path'] = str(version / 'sources' / 'visual-genome-join.sqlite')
        adapter = get_adapter(dataset)
        adapter.cancel=check
        if dataset.adapter == 'remote_columnar':
            update(stage='reading remote schemas')
            adapter.warm_layouts(progress=lambda **values: update(**values))
        from .filtering import population_counts, accepts_record
        record_filter=dataset.adapter_config.get('record_filter')
        native_count=adapter.count if dataset.adapter in {'columnar','remote_columnar'} else plan['expected_count']
        expected_count=population_counts(native_count,plan.get('expected_count'),record_filter,dataset.adapter_config.get('expected_source_count'))
        if expected_count is None or expected_count < 1:
            raise ValueError('Source population must have a verified positive count')
        # Source reads can include large embedded media, while persisted output has its own cap.
        read_budget = min(10_000_000_000_000, max(plan['max_output_bytes'], sum(f['bytes'] for f in plan['files']) * 4))
        check()
        media_validation = None
        if hasattr(adapter, 'validate_media'):
            update(stage='validating media references')
            media_validation=adapter.validate_media(plan.get('remote_metadata_bytes',20_000_000),check)
        check()
        update(stage='preview', expected_count=expected_count)
        adapter_derivatives = getattr(adapter, 'derived_sources', [])
        if adapter_derivatives:
            derived_sources.extend(adapter_derivatives)
            derived_bytes = sum(item['bytes'] for item in derived_sources)
        pack = build_preview(dataset, version / 'pack', adapter=adapter, limit=min(expected_count, 100), max_bytes=read_budget,max_output_bytes=plan['max_output_bytes']-derived_bytes)
        # Columnar metadata covers all shards, including fields beyond the preview.
        declared_types = adapter.source_field_types() if hasattr(adapter, 'source_field_types') else {}
        for name in sorted({k for r in pack.records for k in r.source} | set(declared_types)):
            if any(f.id == 'source.' + name for f in pack.fields):
                continue
            values = [r.source[name] for r in pack.records if r.source.get(name) is not None]
            types = {type(v) for v in values}
            dtype = ('boolean' if types == {bool} else 'number' if types and types <= {int, float}
                else 'array' if types == {list} else 'string' if types == {str} else 'object')
            dtype = declared_types.get(name, dtype)
            pack.fields.append(FieldDescriptor(id='source.' + name, name=name, dtype=dtype,
                provenance={'source_url': dataset.source_url},
                query_ops=['eq','ne','in','contains','is_null']+(['gt','gte','lt','lte'] if dtype=='number' else [])))
        for field in pack.fields:
            if field.dtype=='number' and field.query_ops==['eq','ne','in','contains','is_null']:
                field.query_ops+=['gt','gte','lt','lte']
        preview_bytes=len(json.dumps(pack.model_dump(mode='json'),indent=2,ensure_ascii=False).encode())
        if preview_bytes+derived_bytes>=plan['max_output_bytes']:raise ValueError('Preview alone exceeds approved output budget')
        source = adapter.prepare(adapter.plan(1000, read_budget))
        from .sampling import PreviewSampler
        sampler = PreviewSampler(min(expected_count, 100))
        def records():
            cursor = None
            count = 0
            if dataset.adapter == 'remote_columnar':
                with closing(adapter.iter_all_records(source)) as remote_records:
                    for record in remote_records:
                        check()
                        if not accepts_record(record,record_filter):continue
                        sampler.add(record)
                        yield record
                        count += 1
                        if count % 1000 == 0:
                            update(stage='indexing', indexed_count=count, downloaded_bytes=adapter.bytes_fetched)
                return
            while True:
                check()
                batch = adapter.iter_records(source, cursor, 1000)
                if not batch.records and batch.next_cursor:
                    raise ValueError('Adapter made no progress')
                for record in batch.records:
                    if not accepts_record(record,record_filter):continue
                    sampler.add(record)
                    yield record
                    count += 1
                update(stage='indexing', indexed_count=count, **({'downloaded_bytes':adapter.bytes_fetched} if dataset.adapter=='remote_columnar' else {}))
                if not batch.next_cursor:
                    break
                if cursor == batch.next_cursor:
                    raise ValueError('Adapter repeated its cursor')
                cursor = batch.next_cursor
        snapshot = version / 'snapshot'
        if not snapshot.exists():
            with closing(records()) as record_stream:
                build_parquet_snapshot(record_stream, pack.fields, snapshot, root=version,
                    dataset_id=dataset.id, release_id=dataset.release, snapshot_id=dataset.snapshot_id,
                    expected_count=expected_count, unit=dataset.coverage.unit, population_scope='complete',
                    max_bytes=plan['max_output_bytes']-preview_bytes-derived_bytes,
                    max_record_bytes=dataset.adapter_config.get('max_record_bytes',2_000_000))
        if sampler.population_count == 0:
            # A completed staged index can survive cancellation before activation.
            # Recover the same sample without reading source media a second time.
            import pyarrow.parquet as pq
            from dataset_atlas.models import Record
            for batch in pq.ParquetFile(snapshot / 'records.parquet').iter_batches(columns=['record_json'], batch_size=256):
                check()
                for value in batch.column(0).to_pylist():
                    sampler.add(Record.model_validate_json(value))
        if sampler.population_count != expected_count:
            raise ValueError('Preview sampling population differs from the complete index')
        pack.records = sampler.records()
        pack.sampling = sampler.description(dataset.release, dataset.coverage.unit)
        actual_preview_bytes = len(pack.model_dump_json(indent=2).encode())
        snapshot_bytes = sum(path.stat().st_size for path in snapshot.rglob('*') if path.is_file())
        if actual_preview_bytes + snapshot_bytes + derived_bytes > plan['max_output_bytes']:
            raise ValueError('Random preview and snapshot exceed approved output budget')
        check()
        dataset.coverage.preview_count = len(pack.records)
        dataset.coverage.total_count = expected_count
        dataset.coverage.preview = 'complete_target'
        dataset.coverage.adapter = 'tested'
        dataset.coverage.complete_data = 'supported' if dataset.adapter_config.get('media_scope') != 'selected_preview' and not (media_validation or {}).get('absent_media_references') else 'indexed_metadata_partial_media'
        # Access/identity/rights evidence is deliberately not upgraded by downloading.
        from . import prepared_metadata
        dataset=prepared_metadata(dataset,plan['scope'])
        pack.dataset = dataset.model_copy(update={'adapter_config': {}})
        atomic(version / 'pack/pack.json', pack.model_dump(mode='json'))
        atomic(version / 'dataset.json', dataset.model_dump(mode='json'))
        atomic(version / 'receipt.json', {'plan_id': identity, 'source_files': plan['files'],
            'record_count': expected_count, 'snapshot_id': dataset.snapshot_id, 'scope': plan['scope'], 'media_validation':media_validation,'derived_source':derived_source,'derived_sources':derived_sources,'remote_metadata_bytes':getattr(adapter,'bytes_fetched',None)})
        atomic(base / 'active.json', {'version': identity})
        update(status='completed', stage='ready', snapshot_id=dataset.snapshot_id, indexed_count=expected_count)
    except InterruptedError as exc:
        update(status='cancelled', error=str(exc))
    except Exception as exc:
        update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        lock.close()


if __name__ == '__main__':
    from dataset_atlas.jobs.limits import install
    stage=Path(sys.argv[1])/'work/preparation'/sys.argv[2]
    limits=json.loads((stage/'plan.json').read_text()).get('resource_limits',{})
    install(limits, stage)
    run(Path(sys.argv[1]), sys.argv[2])
