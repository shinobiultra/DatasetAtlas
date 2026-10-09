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


# A complete download is preferred for `auto` plans only while it stays this small.
AUTO_COMPLETE_DOWNLOAD_BYTES = 250_000_000


def atomic(path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=None if compact else 2,
                                    separators=(',', ':') if compact else None, ensure_ascii=False))
    temporary.replace(path)


def snapshot_for(dataset_id, plan, identity, root):
    """The snapshot ID of what a plan acquired: derived from the data, never from where it was put.

    A plan hash covers this workspace's absolute paths and budgets, so two colleagues preparing identical
    bytes would get different snapshot IDs and could not exchange saved selections. This hashes the
    acquired files' checksums, revision, recipe, scope and sampling instead. A recipe that declares its own
    reviewed `snapshot_id` wins."""
    if plan.get('recipe_snapshot_id'):
        return plan['recipe_snapshot_id']
    if not plan.get('files'):
        return f'{dataset_id}-{identity[:24]}'
    prefix = str(Path(root).resolve())
    def portable(value):
        if isinstance(value, dict):
            return {key: portable(item) for key, item in value.items() if not key.endswith('_bytes')}
        if isinstance(value, list):
            return [portable(item) for item in value]
        return value.replace(prefix, '') if isinstance(value, str) else value
    config = (plan.get('prepared_dataset') or plan['dataset']).get('adapter_config', {})
    files = sorted([f.get('source_name'), f.get('sha256') or f.get('md5'), f.get('bytes')] for f in plan['files'])
    identity_document = {'dataset': dataset_id, 'kind': plan.get('kind'), 'revision': plan.get('revision'), 'recipe': plan.get('recipe_sha256'),
                         'scope': plan.get('scope'), 'expected_count': plan.get('expected_count'), 'sample': plan.get('sample'),
                         'files': files, 'config': portable(config)}
    digest = hashlib.sha256(json.dumps(identity_document, sort_keys=True, default=str).encode()).hexdigest()
    return f'{dataset_id}-{digest[:24]}'


def read_metadata(url, credential_profile=None):
    """Bounded primary-source metadata; credentials are resolved locally for the Hub host."""
    from dataset_atlas.storage.https import HttpsFetcher, _PinnedHTTPSConnection
    fetcher = HttpsFetcher(['huggingface.co'],credential_profile=credential_profile)
    from urllib.parse import urljoin
    for hop in range(5):
        host, port, address, target = fetcher._destination(url)
        connection = _PinnedHTTPSConnection(host, address, port, 30)
        try:
            from dataset_atlas.storage.auth import source_headers
            connection.request('GET', target, headers={'Accept-Encoding': 'identity',**source_headers(credential_profile,host)})
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

    def plan(self, dataset_id, max_download_bytes, max_output_bytes, source_mode="download"):
        if source_mode == 'auto':
            return self._plan_auto(dataset_id, max_download_bytes, max_output_bytes)
        return self._plan(dataset_id, max_download_bytes, max_output_bytes, source_mode)

    def _plan_auto(self, dataset_id, max_download_bytes, max_output_bytes):
        """The cheapest route to inspectable records, chosen from real plans.

        A complete download is preferred only while it is small, because it also yields a complete
        index. Otherwise a sampled remote read fetches ~100 rows. If neither fits, the full-download
        plan is returned so its stated requirements (size, recipe, access) explain why."""
        download = self._plan(dataset_id, max_download_bytes, max_output_bytes, 'download')
        if self._recipe_auto_source_mode(dataset_id) == 'selective':
            selective = self._plan(dataset_id, max_download_bytes, max_output_bytes, 'selective')
            if selective['ready']:
                return selective
        if download['ready'] and download['expected_download_bytes'] <= AUTO_COMPLETE_DOWNLOAD_BYTES:
            return download
        try:
            sample = self._plan(dataset_id, max_download_bytes, max_output_bytes, 'sample')
        except (ValueError, KeyError, OSError):
            sample = None
        if sample is not None and sample['ready']:
            return sample
        return download

    def _recipe_auto_source_mode(self, dataset_id):
        """A recipe can name the route `auto` must take when a small complete download would fail, for example because
        embedded images exceed the full-download limits; selective range reads have no such limit."""
        path = self.root/'registry/recipes'/f'{dataset_id}.yaml'
        if not path.is_file():
            return None
        import yaml
        mode = (yaml.safe_load(path.read_text()) or {}).get('auto_source_mode')
        if mode not in {None, 'selective'}:
            raise ValueError('auto_source_mode must be selective')
        return mode

    @staticmethod
    def _no_path_message(dataset):
        """Say whose gap this is: Atlas's, the source's, or unknown. Never present a missing adapter as a restriction."""
        access = dataset.coverage.access
        if access == 'public':
            return ('Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a '
                    'restriction by the source (see docs/adding-datasets.md).')
        if access == 'unreleased':
            return 'The authors have not released this data, so there is nothing to fetch; the entry records where it is described.'
        if access in {'gated', 'request_required', 'author_request_required'}:
            return 'This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it.'
        return ('Atlas has no acquisition path for this release, and its public availability has not been verified. '
                'Identity or source research is needed before a recipe can be written (see docs/adding-datasets.md).')

    def _plan(self, dataset_id, max_download_bytes, max_output_bytes, source_mode="download"):
        if any(type(n) is not int or not 1 <= n <= 10_000_000_000_000 for n in (max_download_bytes, max_output_bytes)):
            raise ValueError('Positive download and output limits of at most 10 TB are required')
        if source_mode not in {'download','selective','sample'}:raise ValueError('Source mode must be download, selective or sample')
        dataset = self.registry.dataset(dataset_id)
        plan = {'dataset_id': dataset.id, 'dataset': dataset.model_dump(mode='json'),
            'max_download_bytes': max_download_bytes, 'max_output_bytes': max_output_bytes,
            'source_mode':source_mode,'files': [], 'expected_download_bytes': 0, 'expected_count': None,
            'source_url': dataset.source_url, 'requirements': [], 'ready': False,
            'scope': dataset.adapter_config.get('population', 'configured source population'),
            'source_identity': 'Pinned available release; not a claim of the paper-used revision.'}
        recipe = {}
        active = self.registry.active_directory(dataset.id)
        recipe_changed = False
        recipe_path = self.root/'registry/recipes'/f'{dataset.id}.yaml'
        if recipe_path.is_file():
            import yaml
            recipe=yaml.safe_load(recipe_path.read_text())
            recipe_hash=hashlib.sha256(recipe_path.read_bytes()).hexdigest()
            if active:
                previous_plan=self._path(json.loads((active/'receipt.json').read_text())['plan_id'])/'plan.json'
                previous_hash=json.loads(previous_plan.read_text()).get('recipe_sha256') if previous_plan.is_file() else None
                recipe_changed=previous_hash!=recipe_hash
            prepared=self.registry.baseline_dataset(dataset.id) if recipe_changed else dataset.model_copy(deep=True)
            if recipe_changed or (recipe.get('files') and not active):prepared.snapshot_id=''
            if recipe.get('source_url'):prepared.source_url=recipe['source_url']
            if recipe.get('description'):prepared.description=recipe['description']
            if recipe.get('release'):prepared.release=recipe['release']
            if recipe.get('snapshot_id'):
                prepared.snapshot_id=recipe['snapshot_id']
                # A reviewed, content-derived ID is workspace-independent; a plan hash is not (it covers local paths).
                plan['recipe_snapshot_id']=recipe['snapshot_id']
            if recipe.get('adapter'):prepared.adapter=recipe['adapter']
            prepared.adapter_config.update(recipe.get('adapter_config',{}))
            prepared=self.registry._resolved(prepared)
            plan['prepared_dataset']=prepared.model_dump(mode='json')
            plan['recipe_sha256']=recipe_hash
            if recipe.get('credential_profile'):
                from dataset_atlas.storage.auth import source_headers
                try:source_headers(recipe['credential_profile'],'huggingface.co')
                except ValueError as exc:plan['requirements'].append(str(exc))
                plan['credential_profile']=recipe['credential_profile']
                prepared.adapter_config['credential_profile']=recipe['credential_profile']
                plan['prepared_dataset']=prepared.model_dump(mode='json')
            dataset=prepared
            plan['scope']=recipe.get('scope',prepared.adapter_config.get('population',plan['scope']))
        parsed = urlsplit(dataset.source_url or '')
        match = re.match(r'^/datasets/([^/]+/[^/]+)', parsed.path)
        # A tested local adapter remains authoritative for joined/native releases.
        adapter_error = None
        try:
            from dataset_atlas.adapters import get_adapter
            adapter = get_adapter(dataset)
            description = adapter.probe()
        except (ValueError, KeyError, FileNotFoundError) as exc:
            description = None
            if str(exc).startswith('unknown adapter:'):adapter_error=str(exc)
        if recipe.get('files') and (recipe_changed or not active or not (description and description.exists)):
            plan.update(kind='http_archive', files=recipe['files'], expected_count=recipe.get('expected_count'),
                expected_download_bytes=sum(f['bytes'] for f in recipe['files']), ready=True,
                scope=recipe['scope'], allowed_hosts=recipe.get('allowed_hosts',[]))
            if recipe.get('sequential_tar_sources'):
                if dataset.adapter not in {'imagenet_c','inaturalist'}:raise ValueError('Sequential TAR acquisition requires a supported native archive adapter')
                plan['kind']='http_sequential_tar'
            if recipe.get('zip_tar_sources'):
                from .zip_tar import validate_sources
                if dataset.adapter!='spoken_wikipedia':raise ValueError('Native ZIP/TAR preparation requires the Spoken Wikipedia adapter')
                validate_sources(recipe['zip_tar_sources'])
                maximum=recipe.get('native_zip_tar_index_bytes',1_000_000_000)
                if type(maximum) is not int or not 1<=maximum<=1_000_000_000:
                    raise ValueError('Native ZIP/TAR indices require an aggregate output cap within1byte..1GB')
                plan['zip_tar_sources']=recipe['zip_tar_sources'];plan['native_zip_tar_index_bytes']=maximum
                plan['expected_annotation_transfer_bytes']=sum(entry.get('remote_zip_member',{}).get('transfer_bytes',entry['bytes']) for entry in recipe['files'])
                plan['expected_download_bytes']=plan['expected_annotation_transfer_bytes']+sum(spec['compressed_bytes']+1_000_000 for spec in recipe['zip_tar_sources'].values())
                plan['download_is_upper_bound']=True
            if recipe.get('convert'):
                conversion = recipe['convert']
                if (not isinstance(conversion, dict) or not isinstance(conversion.get('name'), str) or type(conversion.get('count')) is not int
                        or not re.fullmatch(r'[a-f0-9]{64}', str(conversion.get('rows_sha256', '')))
                    or (conversion.get('media_sha256') is not None and not re.fullmatch(r'[a-f0-9]{64}', str(conversion['media_sha256'])))):
                    raise ValueError('A conversion recipe requires a converter name, an integer row count and a SHA-256 row digest')
                plan['convert'] = conversion
            for entry in recipe['files']:
                if entry.get('config_dir') is not None or entry.get('dest_name') is not None:
                    if (not isinstance(entry.get('config_dir'), str) or not re.fullmatch(r'[a-z_]+', entry['config_dir'])
                            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', str(entry.get('dest_name', entry['source_name'])))):
                        raise ValueError('config_dir must be a lowercase configuration key and dest_name a plain file name')
                if entry.get('extract') is not None:
                    members = entry['extract']
                    if (entry.get('format') != 'zip' or not isinstance(entry.get('config_dir'), str) or not isinstance(members, list)
                            or not members or len(members) > 64
                            or any(not isinstance(m, dict) or not isinstance(m.get('member'), str) or not m['member'] or m['member'].startswith('/')
                                   or '..' in m['member'].split('/') or not re.fullmatch(r'[a-f0-9]{64}', str(m.get('sha256', '')))
                                   or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', m['member'].rsplit('/', 1)[-1]) for m in members)
                            or len({m['member'].rsplit('/', 1)[-1] for m in members}) != len(members)):
                        raise ValueError('extract needs a zip file with a config_dir and plain, checksum-pinned members with distinct names')
                if not entry.get('parts'):
                    continue
                parts = entry['parts']
                if (not isinstance(parts, list) or not parts or len(parts) > 256 or
                    any(not isinstance(part, dict) for part in parts) or
                    any(not isinstance(part.get('source_name'), str) or
                        not part['source_name'] or type(part.get('bytes')) is not int or part['bytes'] < 1 or
                        not isinstance(part.get('sha256'), str) or
                        not re.fullmatch(r'[a-f0-9]{64}', part['sha256']) or
                        not isinstance(part.get('url'), str) or
                        urlsplit(part['url']).scheme != 'https' for part in parts) or
                    len({part['source_name'] for part in parts}) != len(parts) or
                    sum(part['bytes'] for part in parts) != entry['bytes']):
                    raise ValueError('Multipart recipe requires ordered, checksum-pinned HTTPS parts matching the archive size')
            # A recipe may be authored before its archive has been fetched once; until a
            # checksum is pinned the worker would have nothing to verify against.
            unpinned=[f['source_name'] for f in recipe['files'] if not (f.get('sha256') or f.get('md5'))]
            if unpinned:
                plan['ready']=False
                plan['requirements'].append(f"Checksum not pinned for {', '.join(unpinned)}; fetch once, record its SHA-256, then plan again.")
            if plan['expected_count'] is None:
                plan['ready']=False
                plan['requirements'].append('Exact source population count must be declared in the recipe before full indexing.')
        elif description and description.exists and not (source_mode in {'selective','sample'} and parsed.hostname=='huggingface.co' and match):
            plan['kind'] = 'local'
            plan['expected_count'] = recipe.get('expected_count', dataset.coverage.total_count)
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
            info = read_metadata(f'https://huggingface.co/api/datasets/{repo}{revision_path}?blobs=true',**({'credential_profile':plan['credential_profile']} if plan.get('credential_profile') else {}))
            accessible=True
            if info.get('gated'):
                from dataset_atlas.storage.auth import source_headers
                try:
                    source_headers('huggingface','huggingface.co')
                    plan['credential_profile']='huggingface'
                    dataset.adapter_config['credential_profile']='huggingface'
                    plan['prepared_dataset']=dataset.model_dump(mode='json')
                except ValueError:
                    accessible=False
                    plan['requirements'].append('This release is gated. Request access on its Hugging Face page and sign in locally, or register authorized source files.')
            if accessible:
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
            plan['requirements'].append(self._no_path_message(dataset))
        if source_mode=='selective':
            if plan.get('kind')=='huggingface_columnar' and plan['files'] and all(f['format']=='parquet' for f in plan['files']):
                plan['kind']='huggingface_remote_columnar'
                plan['source_total_bytes']=plan['expected_download_bytes']
                plan['expected_download_bytes']=max_download_bytes
                plan['download_is_upper_bound']=True
                plan['media_access']='Index all annotation columns through bounded HTTPS ranges; fetch embedded images on inspection. Strong ETags enforce consistency; full shard SHA-256 is not checked locally. Unsupported layouts fail explicitly.'
            elif plan.get('kind')!='local' or dataset.adapter!='remote_columnar':
                plan['ready']=False
                plan['requirements'].append('Selective column access requires a native Parquet source. Use the source recipe or full download for this format.')
        if source_mode=='sample':
            if plan.get('kind')=='huggingface_columnar' and plan['files'] and all(f['format']=='parquet' for f in plan['files']):
                policy=recipe.get('sample_footers','all')
                if policy not in {'all','shard_rank'}:raise ValueError('sample_footers must be all or shard_rank')
                shards=recipe.get('sample_shards',min(100,len(plan['files'])))
                if policy=='shard_rank' and (type(shards) is not int or not 1<=shards<=len(plan['files'])):raise ValueError('sample_shards must be within the pinned shard count')
                plan.update(kind='huggingface_remote_sample',source_total_bytes=plan['expected_download_bytes'],
                    expected_download_bytes=max_download_bytes,download_is_upper_bound=True,
                    sample={'size':100,'seed':recipe.get('sample_seed',0),'footers':policy,'shards':shards if policy=='shard_rank' else len(plan['files'])},
                    media_access='Sample 100 rows by a seeded SHA-256 counter over row counts from Parquet footers; read only the selected row groups within the transfer budget. No complete local index is built; embedded images are fetched on inspection.')
            else:
                plan['ready']=False
                plan['requirements'].append('Sampled remote previews require a native Parquet source on Hugging Face.')
        if plan.get('kind')=='local' and dataset.adapter=='remote_columnar':
            dataset.adapter_config['metadata_transfer_bytes']=max_download_bytes
            plan['prepared_dataset']=dataset.model_dump(mode='json')
            plan['expected_download_bytes']=max_download_bytes
            plan['download_is_upper_bound']=True
            plan['media_access']='Re-index complete remote annotations within the approved transfer budget; embedded images remain remote.'
        if plan.get('kind')=='local' and dataset.adapter=='objectnet':
            dataset.adapter_config['remote_transfer_budget_bytes']=min(max_download_bytes,recipe['remote_transfer_budget_bytes'])
            plan['prepared_dataset']=dataset.model_dump(mode='json')
            plan['expected_download_bytes']=recipe['remote_transfer_budget_bytes']
            plan['download_is_upper_bound']=True
            plan['media_access']='Index the complete ETag-bound remote ZIP directory; verify and pin 100 original encrypted PNGs. Other originals remain range-addressable on demand.'
        if (plan.get('convert') or {}).get('name')=='tid2013_native':
            try:
                import rarfile
                if not hasattr(rarfile,'RarFile') or not (shutil.which('7zz') or shutil.which('7z')):raise ImportError
            except (ImportError,OSError):
                plan['ready']=False
                plan['requirements'].append('Native RAR access requires dataset-atlas[datasets] (rarfile) and the system 7-Zip command.')
        if adapter_error and plan.get('kind') not in {'huggingface_columnar','huggingface_remote_columnar','huggingface_remote_sample'}:
            plan['ready'] = False
            plan['requirements'].append('Adapter implementation missing: ' + dataset.adapter)
        if dataset.adapter_config.get('archive_preparation') == 'indexed-gzip':
            import importlib.util
            if importlib.util.find_spec('indexed_gzip') is None:
                plan['requirements'].append('Indexed gzip access requires the remote-storage extra (indexed-gzip).')
            plan['media_access'] = 'Native gzip TAR checkpoints support bounded original-image retrieval; no uncompressed media archive is created.'
        if plan.get('zip_tar_sources') or (dataset.adapter=='spoken_wikipedia' and dataset.adapter_config.get('native_audio_sources')):
            import importlib.util
            if importlib.util.find_spec('indexed_gzip') is None:
                plan['requirements'].append('Native ZIP/TAR seek indices require dataset-atlas[remote-storage] (indexed-gzip).')
            if dataset.adapter_config.get('verify_remote_preview_media'):
                if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
                    plan['requirements'].append('Native audio preview verification requires FFmpeg and ffprobe before source acquisition.')
        if dataset.adapter=='svhn_cropped_mat':
            import importlib.util
            if importlib.util.find_spec('scipy') is None:
                plan['requirements'].append('SVHN MAT preparation requires scipy; install dataset-atlas[datasets] before downloading.')
        if dataset.adapter=='ucf101' and (not shutil.which('ffmpeg') or not shutil.which('ffprobe')):
            plan['requirements'].append('Native UCF101 verification and browser playback require FFmpeg and ffprobe before acquisition.')
        if (plan.get('convert') or {}).get('name')=='ffhq_metadata':
            import importlib.util
            if importlib.util.find_spec('ijson') is None:
                plan['requirements'].append('FFHQ metadata conversion requires ijson; install dataset-atlas[datasets] before acquisition.')
        remote = dataset.adapter_config.get('remote_archives', {})
        remote_zips = [key for key in ('remote_questions', 'remote_images', 'remote_archive', 'remote_media_archive') if dataset.adapter_config.get(key)]
        selective_media = remote or remote_zips or dataset.adapter_config.get('media_inventory_path') or plan.get('kind') in {'huggingface_remote_columnar','huggingface_remote_sample'} or dataset.adapter in {'remote_columnar','objectnet','objaverse','miap','fivek','ffhq','emoset','imagenet_c','inaturalist','spoken_wikipedia'}
        if selective_media:
            cache_bytes = dataset.adapter_config.get('remote_cache_bytes',1_000_000_000)
            if type(cache_bytes) is not int or not 1 <= cache_bytes <= 1_000_000_000_000:
                raise ValueError('Remote cache budget must be a positive integer of at most 1 TB')
        if remote:
            metadata_limit = recipe.get('remote_metadata_bytes', 20_000_000)
            if type(metadata_limit) is not int or not 1 <= metadata_limit <= 100_000_000:
                raise ValueError('Remote metadata budget must be within 1..100 MB')
            plan['remote_archives'] = remote
            plan['remote_metadata_bytes'] = metadata_limit
            plan['source_file_bytes'] = plan['expected_download_bytes']
            plan['expected_download_bytes'] += metadata_limit
            plan['media_access'] = 'Original images fetched on inspection through bounded HTTPS ranges; strong ETags are consistency fingerprints, not archive hashes.'
        elif dataset.adapter_config.get('local_archives'):
            metadata_limit = recipe.get('remote_metadata_bytes', 20_000_000)
            if type(metadata_limit) is not int or not 1 <= metadata_limit <= 100_000_000:
                raise ValueError('Archive metadata budget must be within 1..100 MB')
            plan['remote_metadata_bytes'] = metadata_limit
        elif selective_media and not plan.get('media_access'):
            plan['media_access'] = 'Original image files fetched on inspection and checked against the pinned source inventory; a bounded cache limits disk use.'
        if remote_zips:
            # Directories are read by ranges; each inspected original adds its own bytes. Nothing is downloaded whole.
            plan['expected_download_bytes'] += dataset.adapter_config.get('remote_metadata_bytes', 150_000_000) * len(remote_zips)
            plan['download_is_upper_bound'] = True
            plan['media_access'] = ("Archive directories and the few originals you inspect are read by HTTPS ranges bound to each archive's "
                                    'strong ETag (a consistency fingerprint, not a content hash); the archives themselves are not downloaded.')
        preview_media = recipe.get('preview_media_transfer_bytes') if recipe else None
        if preview_media is not None:
            # Verifying the preview opens original files the source list does not count (100 original 16-bit TIFFs are about 5 GB), so a recipe
            # declares the transfer measured on a real preparation and the plan must show it before the researcher approves a budget.
            if type(preview_media) is not int or not 0 <= preview_media <= 1_000_000_000_000:
                raise ValueError('preview_media_transfer_bytes must be an integer number of bytes of at most 1 TB')
            plan['preview_media_transfer_bytes'] = preview_media
            plan['expected_download_bytes'] += preview_media
            plan['download_is_upper_bound'] = True
        if plan['expected_download_bytes'] > max_download_bytes:
            plan['ready'] = False
            plan['requirements'].append('Source download exceeds the selected download budget.')
        # Cache and retained source may coexist; reserve both conservatively.
        plan['required_free_bytes'] = plan['expected_download_bytes'] * 2 + max_output_bytes + (dataset.adapter_config.get('remote_cache_bytes',1_000_000_000) if selective_media else 0)
        if plan.get('kind')=='http_sequential_tar':
            # One cache object is indexed and cold-verified before retirement;
            # the next source never coexists with that completed original.
            plan['required_free_bytes']=max(entry['bytes'] for entry in plan['files'])+max_output_bytes+dataset.adapter_config.get('remote_cache_bytes',200_000_000)+20_000_000
        if plan.get('zip_tar_sources'):
            plan['required_free_bytes']=plan['expected_annotation_transfer_bytes']*2+max_output_bytes+dataset.adapter_config.get('remote_cache_bytes',200_000_000)+64_000_000
            plan['media_access']='Every pinned native TAR and member is hash-checked through its parent ZIP; only bounded seek indices and verified original audio previews are retained. No full audio TAR body is stored.'
        if plan.get('kind') in {'huggingface_remote_columnar','huggingface_remote_sample'} or (plan.get('kind')=='local' and dataset.adapter in {'remote_columnar','objectnet'}):
            # Transfer is streamed through a bounded cache, not retained as a full source copy.
            plan['required_free_bytes']=max_output_bytes+dataset.adapter_config.get('remote_cache_bytes',1_000_000_000)+20_000_000
        if plan.get('kind') in {'http_archive','huggingface_columnar'}:
            # Verified, registered originals on the destination filesystem need
            # only another hard link. The worker must fail if reuse is no longer
            # possible; it cannot silently download/copy under this reservation.
            from dataset_atlas.storage.sources import source_object
            destination = self.root/'work/prepared'/dataset.id
            while not destination.exists():
                destination = destination.parent
            reuse = []
            for entry in plan['files']:
                source = source_object(self.root,entry.get('sha256'),entry['bytes'])
                if source is not None and source.stat().st_dev == destination.stat().st_dev:
                    reuse.append(entry['source_name'])
                    plan['required_free_bytes'] -= 2 * entry['bytes']
            if reuse:
                plan['reuse_registered_sources'] = reuse
        plan['required_free_bytes'] += dataset.adapter_config.get('max_join_bytes', 0)
        plan['available_bytes'] = shutil.disk_usage(self.directory).free
        if plan['required_free_bytes'] > plan['available_bytes']:
            plan['ready'] = False
            plan['requirements'].append('Insufficient free space for source, cache, and the approved output budget.')
        from dataset_atlas.storage.optimized import preparation_headroom
        storage = preparation_headroom(self.root, plan['required_free_bytes'], self._storage_reservations())
        if storage:
            plan['shared_storage'] = storage
            if not storage['admitted']:
                plan['ready'] = False
                if storage['measurement_errors']:
                    # Usage that cannot be measured completely is never assumed to fit under the ceiling.
                    first = storage['measurement_errors'][0]
                    plan['requirements'].append(
                        f"Storage use could not be measured completely, so the workspace ceiling cannot be checked ({first['path']}: {first['error']}). "
                        'Remove or fix that path in local-config/storage.json (or run `atlas storage configure`), then plan again.')
                else:
                    plan['requirements'].append('Shared Atlas storage ceiling leaves insufficient space for this preparation; free retained data or reduce the requested limits.')
        if plan['requirements']:
            plan['ready'] = False
        from dataset_atlas.jobs.limits import limits, enforcement
        plan['resource_limits']=limits(recipe.get('resource_limits',{}))
        plan['memory_enforcement']=enforcement()
        plan['id'] = hashlib.sha256(json.dumps({k:v for k,v in plan.items() if k not in {'available_bytes', 'shared_storage'}}, sort_keys=True).encode()).hexdigest()
        atomic(self._path(plan['id']) / 'plan.json', plan)
        return plan

    def start(self, identity):
        import fcntl
        directory=self._path(identity)
        if not directory.is_dir():raise FileNotFoundError('Preparation plan not found')
        with (self.directory/'storage-admission.lock').open('a') as storage_lock:
            fcntl.flock(storage_lock,fcntl.LOCK_EX)
            with (directory/'dispatch.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                return self._start(identity)

    def _storage_reservations(self):
        reserved = 0
        # The UI listing is capped at 100; admission must include older jobs too.
        for status_path in self.directory.glob('*/status.json'):
            status = self.status(status_path.parent.name)
            if status['status'] not in {'queued', 'running'}: continue
            path = self._path(status['id'])/'plan.json'
            plan=json.loads(path.read_text())
            reserved += max(0,plan['required_free_bytes']-self._allocated_preparation_bytes(plan))
        return reserved

    def _allocated_preparation_bytes(self,plan):
        """Subtract Atlas-owned job bytes already counted in shared usage.

        Shared hard links are deliberately not subtracted: another source or
        frozen version may own those bytes. A failed measurement reserves the
        whole declared peak instead of assuming that unknown bytes are free.
        """
        if not plan.get('id') or not plan.get('dataset_id'):return 0
        version=self.root/'work/prepared'/plan['dataset_id']/plan['id']
        if version.is_symlink() or not version.is_dir():return 0
        total=0
        try:
            for directory,children,files in os.walk(version,followlinks=False):
                children[:]=[name for name in children if not (Path(directory)/name).is_symlink()]
                for name in files:
                    path=Path(directory)/name
                    if path.is_symlink():continue
                    info=path.stat()
                    if info.st_nlink==1:total+=getattr(info,'st_blocks',0)*512
        except OSError:return 0
        return total

    def _start(self, identity):
        directory = self._path(identity)
        plan = json.loads((directory / 'plan.json').read_text())
        if not plan['ready']:
            raise ValueError('Preparation requirements have not been satisfied')
        prior = self.status(identity)
        if prior['status'] in {'running', 'queued', 'completed'}:
            return prior
        from dataset_atlas.storage.optimized import preparation_headroom
        remaining=max(0,plan['required_free_bytes']-self._allocated_preparation_bytes(plan))
        storage = preparation_headroom(self.root, remaining, self._storage_reservations())
        if storage and not storage['admitted']:
            raise ValueError('Shared Atlas storage headroom changed; free retained data or create a smaller plan')
        if shutil.disk_usage(self.directory).free < remaining:
            raise ValueError('Free space changed; create a new plan')
        if prior['status'] in {'failed','cancelled','interrupted'}:
            history=directory/'attempts'; history.mkdir(exist_ok=True)
            resource=directory/'resource-error.receipt'
            atomic(history/f'{time.time_ns()}.json',{
                'status':prior,
                'plan_sha256':hashlib.sha256((directory/'plan.json').read_bytes()).hexdigest(),
                'worker_log_bytes_before_retry':(directory/'worker.log').stat().st_size if (directory/'worker.log').exists() else 0,
                'resource_error':json.loads(resource.read_text()) if resource.is_file() else None})
        (directory / 'cancel').unlink(missing_ok=True)
        (directory / 'resource-error.receipt').unlink(missing_ok=True)
        atomic(directory / 'status.json', {'id': identity, 'dataset_id': plan['dataset_id'], 'status': 'queued', 'updated_at': time.time()})
        with (directory / 'worker.log').open('ab') as log:
            from dataset_atlas.jobs.limits import worker_command
            process = subprocess.Popen(worker_command([sys.executable, '-m', 'dataset_atlas.preparation.worker', str(self.root), identity],plan.get('resource_limits',{})),
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
        # A PID can be invisible from a restricted process namespace while its
        # filesystem writer lease remains held. Do not rewrite a live worker's
        # status as interrupted merely because this reader cannot see procfs.
        if value['status'] == 'running' and not alive:
            from .slots import dataset_writer_active
            dataset_id = value.get('dataset_id')
            if dataset_id and dataset_writer_active(self.directory, dataset_id,plan_id=identity,expected_pid=pid):
                alive = True
            if time.time() - value.get('updated_at', 0) < 10:
                alive = True
        if value['status'] == 'running' and not alive:
            receipt=directory/'resource-error.receipt'
            reason=json.loads(receipt.read_text()).get('message') if receipt.is_file() else 'Worker is no longer running; retry reuses verified downloads.'
            value.update(status='interrupted', error=reason)
            atomic(path, value)
        elif value['status'] == 'queued' and time.time() - value.get('updated_at', 0) > 30:
            value.update(status='interrupted', error='Worker did not start; retry preparation.')
            atomic(path, value)
        process = self.processes.get(identity)
        if process is not None and process.poll() is not None and not alive and value.get('pid') == process.pid and value['status'] in {'running', 'queued'}:
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
        from dataset_atlas.registry import Registry
        catalogue = Registry(self.root).baseline_dataset(dataset_id)
        if not dataset.tasks:
            dataset.tasks = list(catalogue.tasks)
        if not dataset.modalities:
            dataset.modalities = list(catalogue.modalities)
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

    def verify_remote_preview(self, dataset_id, identity):
        """Re-derive a remote preview from a finished index without re-indexing it.

        Path-only image structs in some released Parquet rows do not contain
        retrievable originals. A bounded, hash-ranked candidate pool is checked
        against the pinned remote release before any preview metadata changes.
        """
        import hashlib
        import pyarrow.parquet as pq
        from dataset_atlas.adapters import get_adapter
        from dataset_atlas.models import Dataset, Pack, Record
        from .sampling import PreviewSampler, select_verified_remote_preview

        directory = self.version_directory(dataset_id, identity)
        receipt_path = directory / 'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        dataset = Dataset.model_validate_json((directory / 'dataset.json').read_text())
        if dataset.adapter != 'remote_columnar' or dataset.snapshot_id != receipt['snapshot_id']:
            raise ValueError('A completed remote-columnar version is required')
        manifest = json.loads((directory / 'snapshot/manifest.json').read_text())
        path = directory / 'snapshot/records.parquet'
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(16_000_000), b''):
                digest.update(chunk)
        if digest.hexdigest() != manifest['checksums']['records.parquet']:
            raise ValueError('Prepared index checksum differs from its manifest')
        expected = manifest['record_count']
        sampler = PreviewSampler(min(expected, 250))
        for batch in pq.ParquetFile(path).iter_batches(columns=['record_json'], batch_size=256):
            for value in batch.column(0).to_pylist():
                sampler.add(Record.model_validate_json(value))
        if sampler.population_count != expected or expected != receipt['record_count']:
            raise ValueError('Prepared index row count differs from its receipt')
        adapter = get_adapter(dataset)
        source = adapter.prepare(adapter.plan(100, 10_000_000_000_000))
        pack_path = directory / 'pack/pack.json'
        pack = Pack.model_validate_json(pack_path.read_text())
        pack.records, validation = select_verified_remote_preview(sampler.records(),
            lambda ref: adapter.resolve_asset(source, ref), min(expected, 100))
        pack.sampling = sampler.description(dataset.release, dataset.coverage.unit)
        pack.sampling.update(method='sha256_bottom_k_primary_asset_verified_media',
            requested_count=min(expected, 100), returned_count=len(pack.records),
            candidate_pool_count=len(sampler.records()),
            selection_note='Lowest hash-ranked candidate records with all linked original images verified; excludes unavailable remote image slots.')
        dataset.adapter_config['media_scope'] = 'on_demand_unverified'
        dataset.coverage.preview_count = len(pack.records)
        dataset.coverage.complete_data = 'indexed_metadata_partial_media'
        dataset.evidence = [item for item in dataset.evidence
                            if not (item.get('kind') == 'local_preparation' and item.get('snapshot_id') == dataset.snapshot_id)]
        dataset = prepared_metadata(dataset, receipt['scope'])
        pack.dataset = dataset.model_copy(update={'adapter_config': {}})
        receipt['preview_media_validation'] = validation
        receipt['metadata_version'] = 3
        receipt['metadata_refreshed_at'] = time.time()
        atomic(pack_path, pack.model_dump(mode='json'))
        atomic(directory / 'dataset.json', dataset.model_dump(mode='json'))
        atomic(receipt_path, receipt)
        return {'dataset_id': dataset_id, 'snapshot_id': dataset.snapshot_id,
                'preview_records': len(pack.records), 'preview_media_validation': validation,
                'index_sha256': digest.hexdigest(), 'index_rows': expected}

    def verify_full_media(self, dataset_id, identity):
        """Prove every indexed image has a protected, checksum-valid local original."""
        import hashlib
        import pyarrow.parquet as pq
        from dataset_atlas.models import Dataset, Pack
        from dataset_atlas.storage.compact import read_compact

        directory = self.version_directory(dataset_id, identity)
        receipt_path = directory / 'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        dataset = Dataset.model_validate_json((directory / 'dataset.json').read_text())
        manifest = json.loads((directory / 'snapshot/manifest.json').read_text())
        if (dataset.id != dataset_id or dataset.snapshot_id != receipt['snapshot_id']
                or manifest['record_count'] != receipt['record_count']):
            raise ValueError('Full-media audit requires a matching completed index')
        snapshot_path = directory / 'snapshot/records.parquet'
        with snapshot_path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != manifest['checksums']['records.parquet']:
                raise ValueError('Full-media audit index checksum differs from manifest')
        refs = {}
        rows = 0
        for batch in pq.ParquetFile(snapshot_path).iter_batches(columns=['record_json'], batch_size=256):
            for value in batch.column(0).to_pylist():
                record = json.loads(value)
                rows += 1
                if set(record['asset_ids']) != {asset['id'] for asset in record['assets']}:
                    raise ValueError('Full-media audit asset references disagree with indexed assets')
                for asset in record['assets']:
                    if asset['modality'] != 'image' or not asset.get('uri'):
                        raise ValueError('Full-media audit only supports indexed image assets')
                    ref = asset['uri']
                    if ref in refs and refs[ref] != asset['id']:
                        raise ValueError('Image reference has conflicting asset identities')
                    refs[ref] = asset['id']
        if rows != manifest['record_count'] or not refs:
            raise ValueError('Full-media audit row count or asset population differs')
        verified_bytes = 0
        for ref in refs:
            result = read_compact(self.root, dataset.id, dataset.snapshot_id, ref, 50_000_000)
            if not result or result[2].get('representation') != 'original' or not result[2].get('protected_preview'):
                raise ValueError('Indexed image lacks a protected original')
            verified_bytes += len(result[0])
        dataset.adapter_config['media_scope'] = 'full'
        dataset.coverage.complete_data = 'supported'
        dataset.evidence = [item for item in dataset.evidence
                            if not (item.get('kind') == 'local_preparation' and item.get('snapshot_id') == dataset.snapshot_id)]
        dataset = prepared_metadata(dataset, receipt['scope'])
        pack_path = directory / 'pack/pack.json'
        pack = Pack.model_validate_json(pack_path.read_text())
        pack.dataset = dataset.model_copy(update={'adapter_config': {}})
        validation = {'indexed_records': rows, 'unique_image_assets': len(refs),
            'protected_original_bytes': verified_bytes,
            'scope': 'Every image reference in the complete indexed release has a checksum-valid protected local original.'}
        receipt['full_media_validation'] = validation
        receipt['metadata_version'] = 4
        receipt['metadata_refreshed_at'] = time.time()
        atomic(directory / 'dataset.json', dataset.model_dump(mode='json'))
        atomic(pack_path, pack.model_dump(mode='json'))
        atomic(receipt_path, receipt)
        return {'dataset_id': dataset.id, 'snapshot_id': dataset.snapshot_id, **validation}

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
        decisions = {}
        for dataset_dir in sorted(base.iterdir()):
            if not dataset_dir.is_dir():
                continue
            pointer = dataset_dir / 'active.json'
            active = json.loads(pointer.read_text())['version'] if pointer.is_file() else None
            versions = []
            for directory in sorted(dataset_dir.iterdir()):
                if not directory.is_dir():
                    continue
                document = directory / 'dataset.json'
                body = json.loads(document.read_text()) if document.is_file() else {}
                status_path = self.directory / directory.name / 'status.json'
                status = json.loads(status_path.read_text()).get('status') if status_path.is_file() else None
                versions.append((directory, body, status))
            active_snapshot = next((body.get('snapshot_id') for directory, body, _ in versions if directory.name == active), None)
            for directory, body, status in versions:
                snapshot = body.get('snapshot_id')
                if directory.name == active:
                    reason, removable = 'active', False
                elif status in {'running', 'queued'}:
                    reason, removable = 'preparation in progress', False
                elif status in {'failed', 'cancelled', 'interrupted'} or snapshot is None:
                    reason, removable = status or 'incomplete', True
                elif snapshot == active_snapshot:
                    reason, removable = 'duplicate of active snapshot', True
                elif snapshot in referenced:
                    reason, removable = 'referenced by a saved selection', False
                else:
                    reason, removable = 'superseded and unreferenced', True
                decisions[directory.resolve()] = [snapshot, reason, removable, body]
        # Local re-indexing can reference source files in an older prepared version.
        # Trace every retained configuration transitively, including across datasets.
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for child in value.values():
                    yield from strings(child)
            elif isinstance(value, list):
                for child in value:
                    yield from strings(child)
        pending = [directory for directory, entry in decisions.items() if not entry[2]]
        visited = set()
        while pending:
            directory = pending.pop()
            if directory in visited:
                continue
            visited.add(directory)
            config = decisions[directory][3].get('adapter_config', {})
            # A running worker may not have written dataset.json yet.
            plan_path = self.directory / directory.name / 'plan.json'
            if not config and plan_path.is_file():
                plan = json.loads(plan_path.read_text())
                config = plan.get('prepared_dataset', plan.get('dataset', {})).get('adapter_config', {})
            for value in strings(config):
                if not value or '://' in value:
                    continue
                try:
                    path = Path(value)
                    path = (path if path.is_absolute() else self.root / path).resolve()
                    relative = path.relative_to(base)
                except (ValueError, OSError):
                    continue
                if len(relative.parts) < 2:
                    continue
                target = base.joinpath(*relative.parts[:2]).resolve()
                if target in decisions and target != directory:
                    entry = decisions[target]
                    if entry[2]:
                        entry[1:3] = ['source dependency of a retained version', False]
                    pending.append(target)
        retained_inodes = set()
        for directory, (_, _, removable, _) in decisions.items():
            if not removable:
                for path in directory.rglob('*'):
                    if path.is_file():
                        stat = path.stat()
                        retained_inodes.add((stat.st_dev, stat.st_ino))
        # A source object or cache may hold another hard link *outside* prepared/.
        # Count bytes as reclaimable only when all links to that inode are removed.
        from collections import Counter
        removable_links = Counter()
        for directory, (_, _, removable, _) in decisions.items():
            if removable:
                for path in directory.rglob('*'):
                    if path.is_file() and not path.is_symlink():
                        info = path.stat()
                        removable_links[(info.st_dev, info.st_ino)] += 1
        counted = set()
        for directory, (snapshot, reason, removable, _) in decisions.items():
            entry = {'dataset_id': directory.parent.name, 'version': directory.name, 'snapshot_id': snapshot, 'reason': reason}
            if not removable:
                report['retained'].append(entry)
                continue
            freed = 0
            for path in directory.rglob('*'):
                if path.is_file() and not path.is_symlink():
                    stat = path.stat()
                    inode = (stat.st_dev, stat.st_ino)
                    if inode not in retained_inodes and inode not in counted and removable_links[inode] == stat.st_nlink:
                        freed += stat.st_size
                        counted.add(inode)
            entry['freed_bytes'] = freed
            report['removable'].append(entry)
            report['freed_bytes'] += freed
            if execute:
                shutil.rmtree(directory)
        return report


def prepared_metadata(dataset, scope):
    """Remove only acquisition claims that this successful preparation disproves."""
    if dataset.adapter_config.get('media_scope')=='partial':
        dataset.coverage.complete_data='indexed_metadata_partial_media'
    obsolete = {'Adapter and preview are not implemented.', 'Adapter and preview are not implemented'}
    if dataset.adapter_config.get('credential_profile') == 'huggingface':
        obsolete.add('Repository files require accepting the Hugging Face contact-sharing access gate.')
        obsolete.update({
            'Original-source credentials or agreement are required.',
            'Official authors require access approval before downloading the 202503 base question.jsonl; no approved local source is present.',
            'Original author Hugging Face dataset requires account login and acceptance of access conditions; unauthenticated pinned Parquet HEAD returns HTTP 401.',
        })
    dataset.coverage.blockers = [message for message in dataset.coverage.blockers
        if message not in obsolete
        and not (dataset.adapter=='columnar' and message.startswith('Pinned HF Parquet source totals') and 'no local preview' in message)
        and not (dataset.adapter_config.get('media_scope')=='full' and message.startswith('Only 100 selected original JPEGs'))]
    if dataset.adapter_config.get('credential_profile') == 'huggingface':
        dataset.coverage.blockers = [
            'Source-image redistribution rights remain unreviewed; local acquisition does not approve publication.'
            if message == 'Dataset content and inherited source-image rights have not been inspected.' else message
            for message in dataset.coverage.blockers]
    dataset.evidence.append({'kind':'local_preparation','snapshot_id':dataset.snapshot_id,'population':scope,
        'record_count':dataset.coverage.total_count,'note':'Prepared source population; publication rights and paper identity are separate.'})
    return dataset
