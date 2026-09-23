"""One isolated acquisition/index writer. Approved plans are immutable inputs."""
from __future__ import annotations
import fcntl
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
    lock = (manager.directory / 'writer.lock').open('a')
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if (directory/'cancel').exists():
                update(status='cancelled', error='Cancelled while waiting for preparation slot')
                lock.close()
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
            cache = BoundedCache(Path(root) / 'work/download-cache', max_bytes=plan['max_download_bytes'])
            fetcher = HttpsFetcher(['huggingface.co', 'cdn-lfs.huggingface.co', 'cdn-lfs-us-1.huggingface.co',
                'cdn-lfs-eu-1.huggingface.co', 'cas-bridge.xethub.hf.co', 'us.aws.cdn.hf.co', 'eu.aws.cdn.hf.co', 'www.robots.ox.ac.uk', 'thor.robots.ox.ac.uk']+plan.get('allowed_hosts',[]), timeout=60,
                max_bytes=plan['max_download_bytes'],credential_profile=plan.get('credential_profile'))
            files = []
            for entry in plan['files']:
                check()
                from dataset_atlas.storage.sources import source_object
                source=source_object(root,entry.get('sha256'),entry['bytes'])
                if source is None:
                    source = fetcher.fetch(entry['url'], cache,
                        CacheIdentity(plan.get('revision',dataset.release), entry.get('sha256',entry.get('md5')), 'original'),
                        expected_sha256=entry.get('sha256'), byte_budget=entry['bytes'], cancel=check,
                        progress=lambda total:update(downloaded_bytes=sum(f['bytes'] for f in files)+total,current_file=entry['source_name']))
                else:update(stage='reusing registered source',current_file=entry['source_name'])
                digest=hashlib.sha256();md5=hashlib.md5(usedforsecurity=False)
                with source.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk);md5.update(chunk)
                if entry.get('md5') and md5.hexdigest()!=entry['md5']:raise ValueError('Official source MD5 mismatch')
                source_dir = version / 'sources'
                source_dir.mkdir(exist_ok=True)
                target = source_dir / (digest.hexdigest() + '.' + entry['format'])
                if not target.exists():
                    try:
                        os.link(source, target)
                    except OSError:
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
            from dataset_atlas.storage.ranges import range_fingerprint
            hosts=['huggingface.co','cdn-lfs.huggingface.co','cdn-lfs-us-1.huggingface.co','cdn-lfs-eu-1.huggingface.co',
                   'cas-bridge.xethub.hf.co','us.aws.cdn.hf.co','eu.aws.cdn.hf.co']
            remote_files=[]
            for entry in plan['files']:
                check()
                update(stage='pinning remote shards',current_file=entry['source_name'])
                remote_files.append({**entry,'etag':range_fingerprint(entry['url'],expected_size=entry['bytes'],allowed_hosts=hosts)})
            dataset.release=plan['revision']
            dataset.snapshot_id=f'{dataset.id}-{identity[:24]}'
            dataset.adapter='remote_columnar'
            dataset.adapter_config={'remote_files':remote_files,'allowed_hosts':hosts,
                'remote_cache_root':str(Path(root)/'work/media-cache/remote-parquet'),'remote_cache_bytes':1_000_000_000,
                'metadata_transfer_bytes':plan['max_download_bytes'],'population':plan['scope'],
                'mapping':dataset.adapter_config.get('mapping',{})}
        derived_sources = []
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
                derived=repack_tar(original,target,plan['max_output_bytes']-sum(item['bytes'] for item in derived_sources),check)
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
        if dataset.adapter == 'visual_genome':
            dataset.adapter_config['join_index_path'] = str(version / 'sources' / 'visual-genome-join.sqlite')
        adapter = get_adapter(dataset)
        adapter.cancel=check
        expected_count = adapter.count if dataset.adapter in {'columnar','remote_columnar'} else plan['expected_count']
        if dataset.adapter in {'columnar','remote_columnar'} and plan.get('expected_count') is not None and expected_count != plan['expected_count']:
            raise ValueError('Columnar count differs from declared release population')
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
        def records():
            cursor = None
            count = 0
            while True:
                check()
                batch = adapter.iter_records(source, cursor, 1000)
                if not batch.records and batch.next_cursor:
                    raise ValueError('Adapter made no progress')
                yield from batch.records
                count += len(batch.records)
                update(stage='indexing', indexed_count=count, **({'downloaded_bytes':adapter.bytes_fetched} if dataset.adapter=='remote_columnar' else {}))
                if not batch.next_cursor:
                    break
                if cursor == batch.next_cursor:
                    raise ValueError('Adapter repeated its cursor')
                cursor = batch.next_cursor
        snapshot = version / 'snapshot'
        if not snapshot.exists():
            build_parquet_snapshot(records(), pack.fields, snapshot, root=version,
                dataset_id=dataset.id, release_id=dataset.release, snapshot_id=dataset.snapshot_id,
                expected_count=expected_count, population_scope='complete', max_bytes=plan['max_output_bytes']-preview_bytes-derived_bytes)
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
    install({}, Path(sys.argv[1])/'work/preparation'/sys.argv[2])
    run(Path(sys.argv[1]), sys.argv[2])
