"""One isolated acquisition/index writer. Approved plans are immutable inputs."""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
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
                max_bytes=plan['max_download_bytes'])
            files = []
            for entry in plan['files']:
                check()
                source = fetcher.fetch(entry['url'], cache,
                    CacheIdentity(plan.get('revision',dataset.release), entry.get('sha256',entry.get('md5')), 'original'),
                    expected_sha256=entry.get('sha256'), byte_budget=entry['bytes'], cancel=check,
                    progress=lambda total:update(downloaded_bytes=sum(f['bytes'] for f in files)+total,current_file=entry['source_name']))
                digest=hashlib.sha256();md5=hashlib.md5(usedforsecurity=False)
                with source.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk);md5.update(chunk)
                if entry.get('md5') and md5.hexdigest()!=entry['md5']:raise ValueError('Official source MD5 mismatch')
                source_dir = version / 'sources'
                source_dir.mkdir(exist_ok=True)
                target = source_dir / (digest.hexdigest() + '.' + entry['format'])
                if not target.exists():
                    os.link(source, target)
                files.append({**entry, 'sha256':digest.hexdigest(), 'path': str(target)})
                if entry.get('config_key'):dataset.adapter_config[entry['config_key']]=str(target)
                if entry.get('config_key')=='path':dataset.adapter_config['sha256']=digest.hexdigest()
                update(downloaded_bytes=sum(f['bytes'] for f in files), current_file=entry['source_name'])
            if plan['kind']=='huggingface_columnar':
                dataset.release = plan['revision']
            dataset.snapshot_id = f'{dataset.id}-{identity[:24]}'
            if plan['kind']=='huggingface_columnar':
                dataset.adapter = 'columnar'
                dataset.adapter_config = {**dataset.adapter_config, 'files': files, 'population': plan['scope'],
                    'mapping': {'text': 'text', 'question': 'question', 'choices': 'choices', **dataset.adapter_config.get('mapping', {})}}
        adapter = get_adapter(dataset)
        expected_count = adapter.count if dataset.adapter == 'columnar' else plan['expected_count']
        if dataset.adapter == 'columnar' and plan.get('expected_count') is not None and expected_count != plan['expected_count']:
            raise ValueError('Columnar count differs from declared release population')
        if expected_count is None or expected_count < 1:
            raise ValueError('Source population must have a verified positive count')
        # Source reads can include large embedded media, while persisted output has its own cap.
        read_budget = min(100_000_000_000, max(plan['max_output_bytes'], sum(f['bytes'] for f in plan['files']) * 4))
        check()
        update(stage='preview', expected_count=expected_count)
        pack = build_preview(dataset, version / 'pack', limit=min(expected_count, 100), max_bytes=read_budget,max_output_bytes=plan['max_output_bytes'])
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
                provenance={'source_url': dataset.source_url}))
        preview_bytes=len(json.dumps(pack.model_dump(mode='json'),indent=2,ensure_ascii=False).encode())
        if preview_bytes>=plan['max_output_bytes']:raise ValueError('Preview alone exceeds approved output budget')
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
                update(stage='indexing', indexed_count=count)
                if not batch.next_cursor:
                    break
                if cursor == batch.next_cursor:
                    raise ValueError('Adapter repeated its cursor')
                cursor = batch.next_cursor
        snapshot = version / 'snapshot'
        if not snapshot.exists():
            build_parquet_snapshot(records(), pack.fields, snapshot, root=version,
                dataset_id=dataset.id, release_id=dataset.release, snapshot_id=dataset.snapshot_id,
                expected_count=expected_count, population_scope='complete', max_bytes=plan['max_output_bytes']-preview_bytes)
        check()
        dataset.coverage.preview_count = len(pack.records)
        dataset.coverage.total_count = expected_count
        dataset.coverage.preview = 'complete_target'
        dataset.coverage.adapter = 'tested'
        dataset.coverage.complete_data = 'supported' if dataset.adapter_config.get('media_scope') != 'selected_preview' else 'indexed_metadata_partial_media'
        # Access/identity/rights evidence is deliberately not upgraded by downloading.
        from . import prepared_metadata
        dataset=prepared_metadata(dataset,plan['scope'])
        pack.dataset = dataset.model_copy(update={'adapter_config': {}})
        atomic(version / 'pack/pack.json', pack.model_dump(mode='json'))
        atomic(version / 'dataset.json', dataset.model_dump(mode='json'))
        atomic(version / 'receipt.json', {'plan_id': identity, 'source_files': plan['files'],
            'record_count': expected_count, 'snapshot_id': dataset.snapshot_id, 'scope': plan['scope']})
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
