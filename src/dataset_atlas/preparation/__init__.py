"""Explicit, disk-bounded acquisition plans and isolated preparation workers."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit
from dataset_atlas.models import content_id
from dataset_atlas.registry import Registry


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    temporary.replace(path)


def read_metadata(url):
    """Bounded primary-source metadata, without credentials or repository execution."""
    from dataset_atlas.storage.https import HttpsFetcher, _PinnedHTTPSConnection
    fetcher = HttpsFetcher(['huggingface.co'])
    from urllib.parse import urljoin
    for hop in range(5):
        host, port, address, target = fetcher._destination(url)
        connection = _PinnedHTTPSConnection(host, address, port, 30)
        try:
            connection.request('GET', target, headers={'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in {301,302,303,307,308}:
                location=response.getheader('Location')
                if not location:raise ValueError('Source metadata redirect has no location')
                url=urljoin(url,location)
                continue
            if response.status != 200:
                raise ValueError(f'Source metadata HTTP {response.status}; authentication/terms are not bypassed')
            payload = response.read(20_000_001)
            if len(payload) > 20_000_000:
                raise ValueError('Source metadata exceeds 20 MB planning limit')
            return json.loads(payload)
        finally:
            connection.close()
    raise ValueError('Too many source metadata redirects')



class PreparationManager:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / 'work/preparation'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.registry = Registry(self.root)
        self.processes = {}

    def _path(self, identity):
        if not re.fullmatch(r'[a-f0-9]{64}', identity):
            raise ValueError('Invalid preparation ID')
        return self.directory / identity

    def plan(self, dataset_id, max_download_bytes, max_output_bytes):
        if any(type(n) is not int or not 1 <= n <= 10_000_000_000_000 for n in (max_download_bytes, max_output_bytes)):
            raise ValueError('Positive download and output limits of at most 10 TB are required')
        dataset = self.registry.dataset(dataset_id)
        plan = {'dataset_id': dataset.id, 'dataset': dataset.model_dump(mode='json'),
            'max_download_bytes': max_download_bytes, 'max_output_bytes': max_output_bytes,
            'files': [], 'expected_download_bytes': 0, 'expected_count': None,
            'source_url': dataset.source_url, 'requirements': [], 'ready': False,
            'scope': dataset.adapter_config.get('population', 'configured source population'),
            'source_identity': 'Pinned available release; not a claim of the paper-used revision.'}
        recipe = {}
        recipe_path = self.root/'registry/recipes'/f'{dataset.id}.yaml'
        if recipe_path.is_file():
            import yaml
            recipe=yaml.safe_load(recipe_path.read_text())
            prepared=dataset.model_copy(deep=True)
            if recipe.get('source_url'):prepared.source_url=recipe['source_url']
            if recipe.get('description'):prepared.description=recipe['description']
            if recipe.get('release'):prepared.release=recipe['release']
            if recipe.get('snapshot_id'):prepared.snapshot_id=recipe['snapshot_id']
            if recipe.get('adapter'):prepared.adapter=recipe['adapter']
            prepared.adapter_config.update(recipe.get('adapter_config',{}))
            prepared=self.registry._resolved(prepared)
            plan['prepared_dataset']=prepared.model_dump(mode='json')
            plan['recipe_sha256']=hashlib.sha256(recipe_path.read_bytes()).hexdigest()
            dataset=prepared
            plan['scope']=recipe.get('scope',prepared.adapter_config.get('population',plan['scope']))
        parsed = urlsplit(dataset.source_url or '')
        match = re.match(r'^/datasets/([^/]+/[^/]+)', parsed.path)
        # A tested local adapter remains authoritative for joined/native releases.
        try:
            from dataset_atlas.adapters import get_adapter
            adapter = get_adapter(dataset)
            description = adapter.probe()
        except (ValueError, KeyError, FileNotFoundError):
            description = None
        if recipe.get('files') and not (description and description.exists):
            plan.update(kind='http_archive', files=recipe['files'], expected_count=recipe.get('expected_count'),
                expected_download_bytes=sum(f['bytes'] for f in recipe['files']), ready=True,
                scope=recipe['scope'], allowed_hosts=recipe.get('allowed_hosts',[]))
            # A recipe may be authored before its archive has been fetched once; until a
            # checksum is pinned the worker would have nothing to verify against.
            unpinned=[f['source_name'] for f in recipe['files'] if not (f.get('sha256') or f.get('md5'))]
            if unpinned:
                plan['ready']=False
                plan['requirements'].append(f"Checksum not pinned for {', '.join(unpinned)}; fetch once, record its SHA-256, then plan again.")
            if plan['expected_count'] is None:
                plan['ready']=False
                plan['requirements'].append('Exact source population count must be declared in the recipe before full indexing.')
        elif description and description.exists:
            plan['kind'] = 'local'
            plan['expected_count'] = dataset.coverage.total_count
            snapshot = self.registry.snapshot_path(dataset.id)
            if (snapshot / 'manifest.json').is_file():
                plan['expected_count'] = json.loads((snapshot / 'manifest.json').read_text())['record_count']
            if plan['expected_count'] is None:
                plan['requirements'].append('Exact source population count must be registered before full indexing.')
            else:
                plan['ready'] = True
        elif parsed.hostname == 'huggingface.co' and match:
            repo = match[1]
            parts = parsed.path.split('/')
            requested_revision = parts[5] if len(parts)>5 and parts[4]=='tree' else None
            prefix = '/'.join(parts[6:]).rstrip('/') if requested_revision else ''
            revision_path = '/revision/'+quote(requested_revision,safe='') if requested_revision else ''
            info = read_metadata(f'https://huggingface.co/api/datasets/{repo}{revision_path}?blobs=true')
            if info.get('gated'):
                plan['requirements'].append('This release is gated. Obtain authorized local files and configure its adapter.')
            else:
                revision = info.get('sha', '')
                if not re.fullmatch('[a-f0-9]{40}', revision):
                    raise ValueError('Source API did not return an immutable revision')
                files = []
                for entry in info.get('siblings', []):
                    name = entry['rfilename']
                    if prefix and not name.startswith(prefix+'/'):continue
                    if recipe.get('source_patterns'):
                        import fnmatch
                        if not any(fnmatch.fnmatchcase(name, pattern) for pattern in recipe['source_patterns']):continue
                    if not name.endswith(('.parquet', '.arrow')):
                        continue
                    size = entry.get('size')
                    checksum = entry.get('lfs', {}).get('sha256')
                    if type(size) is not int or size < 0 or not checksum:
                        raise ValueError('Columnar source lacks a declared size and SHA-256')
                    files.append({'source_name': name, 'bytes': size, 'sha256': checksum,
                        'format': name.rsplit('.', 1)[1],
                        'url': f'https://huggingface.co/datasets/{repo}/resolve/{revision}/{quote(name, safe="/")}'})
                files.sort(key=lambda entry:entry['source_name'])
                plan.update(kind='huggingface_columnar', revision=revision, files=files,
                    expected_download_bytes=sum(f['bytes'] for f in files),
                    scope=recipe.get('scope','All Arrow/Parquet shards in the pinned repository; configuration and split retained by source filename.'),
                    expected_count=recipe.get('expected_count'))
                if files:
                    plan['ready'] = True
                else:
                    plan['requirements'].append('No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required.')
        else:
            plan['kind'] = 'unconfigured'
            plan['requirements'].append('A pinned acquisition recipe or authorized local source is required for this release.')
        if plan['expected_download_bytes'] > max_download_bytes:
            plan['ready'] = False
            plan['requirements'].append('Source download exceeds the selected download budget.')
        # Cache and retained source may coexist; reserve both conservatively.
        plan['required_free_bytes'] = plan['expected_download_bytes'] * 2 + max_output_bytes
        plan['available_bytes'] = shutil.disk_usage(self.directory).free
        if plan['required_free_bytes'] > plan['available_bytes']:
            plan['ready'] = False
            plan['requirements'].append('Insufficient free space for source, cache, and the approved output budget.')
        from dataset_atlas.jobs.limits import limits, enforcement
        plan['resource_limits']=limits({})
        plan['memory_enforcement']=enforcement()
        plan['id'] = hashlib.sha256(json.dumps({k:v for k,v in plan.items() if k!='available_bytes'}, sort_keys=True).encode()).hexdigest()
        atomic(self._path(plan['id']) / 'plan.json', plan)
        return plan

    def start(self, identity):
        import fcntl
        directory=self._path(identity)
        if not directory.is_dir():raise FileNotFoundError('Preparation plan not found')
        with (directory/'dispatch.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return self._start(identity)

    def _start(self, identity):
        directory = self._path(identity)
        plan = json.loads((directory / 'plan.json').read_text())
        if not plan['ready']:
            raise ValueError('Preparation requirements have not been satisfied')
        prior = self.status(identity)
        if prior['status'] in {'running', 'queued', 'completed'}:
            return prior
        if shutil.disk_usage(self.directory).free < plan['required_free_bytes']:
            raise ValueError('Free space changed; create a new plan')
        (directory / 'cancel').unlink(missing_ok=True)
        (directory / 'resource-error.receipt').unlink(missing_ok=True)
        atomic(directory / 'status.json', {'id': identity, 'dataset_id': plan['dataset_id'], 'status': 'queued', 'updated_at': time.time()})
        with (directory / 'worker.log').open('ab') as log:
            from dataset_atlas.jobs.limits import worker_command
            process = subprocess.Popen(worker_command([sys.executable, '-m', 'dataset_atlas.preparation.worker', str(self.root), identity],{}),
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        self.processes[identity] = process
        return self.status(identity)

    def status(self, identity):
        directory = self._path(identity)
        if not (directory / 'plan.json').is_file():
            raise FileNotFoundError('Preparation plan not found')
        path = directory / 'status.json'
        value = json.loads(path.read_text()) if path.exists() else {'id': identity, 'status': 'planned'}
        pid = value.get('pid')
        alive = False
        if pid:
            proc = Path(f'/proc/{pid}/cmdline')
            if proc.exists():
                try:
                    command = proc.read_bytes()
                    alive = identity.encode() in command and b'dataset_atlas.preparation.worker' in command
                except OSError:
                    pass
            else:
                # No procfs (macOS): a live PID is the best available signal.
                try:
                    os.kill(pid, 0)
                    alive = True
                except OSError:
                    alive = False
        if value['status'] == 'running' and not alive:
            receipt=directory/'resource-error.receipt'
            reason=json.loads(receipt.read_text()).get('message') if receipt.is_file() else 'Worker is no longer running; retry reuses verified downloads.'
            value.update(status='interrupted', error=reason)
            atomic(path, value)
        elif value['status'] == 'queued' and time.time() - value.get('updated_at', 0) > 30:
            value.update(status='interrupted', error='Worker did not start; retry preparation.')
            atomic(path, value)
        process = self.processes.get(identity)
        if process is not None and process.poll() is not None and value['status'] in {'running', 'queued'}:
            value.update(status='interrupted', error='Worker exited before completion; retry reuses verified downloads.')
            atomic(path, value)
        return value

    def list(self, dataset_id=None):
        rows=[]
        for path in self.directory.glob('*/status.json'):
            value=self.status(path.parent.name)
            if dataset_id is None or value.get('dataset_id')==dataset_id:rows.append(value)
        return sorted(rows,key=lambda value:value.get('updated_at',0),reverse=True)[:100]

    def cancel(self, identity):
        directory = self._path(identity)
        (directory / 'cancel').touch()
        # Worker sees this during transfers and between record batches.
        return self.status(identity)


    def version_directory(self, dataset_id, identity):
        if '/' in dataset_id or '\\' in dataset_id or dataset_id in {'.', '..'}:
            raise ValueError('Invalid dataset ID')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', identity):
            raise ValueError('Invalid prepared version')
        directory = (self.root / 'work/prepared' / dataset_id / identity).resolve()
        if directory.parent != (self.root / 'work/prepared' / dataset_id).resolve() or not (directory / 'dataset.json').is_file():
            raise FileNotFoundError('Prepared version not found')
        return directory

    def refresh_metadata(self, dataset_id, identity, *, activate=False):
        """Re-derive a completed version's catalogue metadata from its own receipt.

        The worker's index and sources are immutable; only the derived coverage
        and evidence in dataset.json/pack.json can change when the derivation
        code improves. Doing that here, idempotently, keeps every active version
        reproducible from the repository instead of from an ad-hoc edit.
        """
        from dataset_atlas.models import Dataset, Pack
        directory = self.version_directory(dataset_id, identity)
        receipt = json.loads((directory / 'receipt.json').read_text())
        dataset = Dataset.model_validate_json((directory / 'dataset.json').read_text())
        if dataset.id != dataset_id or dataset.snapshot_id != receipt['snapshot_id']:
            raise ValueError('Prepared version identity does not match its receipt')
        dataset.evidence = [item for item in dataset.evidence
                            if not (item.get('kind') == 'local_preparation' and item.get('snapshot_id') == dataset.snapshot_id)]
        dataset = prepared_metadata(dataset, receipt['scope'])
        pack_path = directory / 'pack/pack.json'
        pack = Pack.model_validate_json(pack_path.read_text())
        pack.dataset = dataset.model_copy(update={'adapter_config': {}})
        atomic(directory / 'dataset.json', dataset.model_dump(mode='json'))
        atomic(pack_path, pack.model_dump(mode='json'))
        receipt['metadata_version'] = 2
        receipt['metadata_refreshed_at'] = time.time()
        atomic(directory / 'receipt.json', receipt)
        if activate:
            atomic(directory.parent / 'active.json', {'version': identity})
        return {'dataset_id': dataset_id, 'version': identity, 'snapshot_id': dataset.snapshot_id,
                'active': json.loads((directory.parent / 'active.json').read_text())['version'] == identity if (directory.parent / 'active.json').is_file() else False}

    def _referenced_snapshots(self):
        """Snapshot IDs that saved selections still point at; those versions are pinned."""
        import sqlite3
        path = self.root / 'work/atlas.sqlite'
        if not path.is_file():
            return set()
        referenced = set()
        db = sqlite3.connect(path)
        try:
            for (body,) in db.execute('SELECT body FROM selections'):
                referenced.update(json.loads(body).get('snapshot_ids', []))
        finally:
            db.close()
        return referenced

    def prune(self, *, execute=False):
        """Explicit eviction for prepared versions nothing can reach any more.

        Removable: failed/cancelled/interrupted runs; non-active versions whose
        snapshot is also served by the active version (exact duplicates); and
        superseded versions no saved selection references. Byte counts ignore
        inodes shared with a retained version, so they are what deletion frees.
        """
        referenced = self._referenced_snapshots()
        report = {'removable': [], 'retained': [], 'freed_bytes': 0, 'executed': execute}
        base = self.root / 'work/prepared'
        if not base.is_dir():
            return report
        for dataset_dir in sorted(base.iterdir()):
            if not dataset_dir.is_dir():
                continue
            pointer = dataset_dir / 'active.json'
            active = json.loads(pointer.read_text())['version'] if pointer.is_file() else None
            versions = []
            for version_dir in sorted(dataset_dir.iterdir()):
                if not version_dir.is_dir():
                    continue
                document = version_dir / 'dataset.json'
                snapshot = json.loads(document.read_text()).get('snapshot_id') if document.is_file() else None
                status_path = self.directory / version_dir.name / 'status.json'
                status = json.loads(status_path.read_text()).get('status') if status_path.is_file() else None
                versions.append((version_dir, snapshot, status))
            active_snapshot = next((snapshot for directory, snapshot, _ in versions if directory.name == active), None)
            retained_inodes = set()
            decisions = []
            for directory, snapshot, status in versions:
                if directory.name == active:
                    decisions.append((directory, snapshot, 'active', False))
                elif status in {'failed', 'cancelled', 'interrupted'} or snapshot is None:
                    decisions.append((directory, snapshot, status or 'incomplete', True))
                elif snapshot == active_snapshot:
                    decisions.append((directory, snapshot, 'duplicate of active snapshot', True))
                elif snapshot in referenced:
                    decisions.append((directory, snapshot, 'referenced by a saved selection', False))
                else:
                    decisions.append((directory, snapshot, 'superseded and unreferenced', True))
            for directory, _, _, removable in decisions:
                if not removable:
                    for path in directory.rglob('*'):
                        if path.is_file():
                            stat = path.stat()
                            retained_inodes.add((stat.st_dev, stat.st_ino))
            for directory, snapshot, reason, removable in decisions:
                entry = {'dataset_id': dataset_dir.name, 'version': directory.name, 'snapshot_id': snapshot, 'reason': reason}
                if not removable:
                    report['retained'].append(entry)
                    continue
                freed = 0
                for path in directory.rglob('*'):
                    if path.is_file() and not path.is_symlink():
                        stat = path.stat()
                        if (stat.st_dev, stat.st_ino) not in retained_inodes:
                            freed += stat.st_size
                entry['freed_bytes'] = freed
                report['removable'].append(entry)
                report['freed_bytes'] += freed
                if execute:
                    shutil.rmtree(directory)
        return report


def prepared_metadata(dataset, scope):
    """Remove only acquisition claims that this successful preparation disproves."""
    obsolete = {'Adapter and preview are not implemented.', 'Adapter and preview are not implemented'}
    dataset.coverage.blockers = [message for message in dataset.coverage.blockers
        if message not in obsolete
        and not (dataset.adapter=='columnar' and message.startswith('Pinned HF Parquet source totals') and 'no local preview' in message)
        and not (dataset.adapter_config.get('media_scope')=='full' and message.startswith('Only 100 selected original JPEGs'))]
    dataset.evidence.append({'kind':'local_preparation','snapshot_id':dataset.snapshot_id,'population':scope,
        'record_count':dataset.coverage.total_count,'note':'Prepared source population; publication rights and paper identity are separate.'})
    return dataset
