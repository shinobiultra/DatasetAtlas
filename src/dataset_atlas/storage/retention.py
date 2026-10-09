"""Verify archive access, pin preview originals, and retire acquired local copies.

This operation is explicit and restricted to Atlas-owned work directories. It
keeps every retained snapshot and installs its original-member routes before
removing any source bytes. Bulk compression is optional: other images can use
the bounded on-demand browsing cache.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile


def _local_config_path(root, value):
    """Normalize possible local dependencies; ordinary metadata is not a path."""
    if not value or '://' in value or '\x00' in value:return None
    path=Path(value)
    try:path=path.expanduser()
    except RuntimeError:
        # An unknown ~username may also be an ordinary literal local filename.
        # Keep that possible dependency relative to the workspace.
        pass
    # Linux cannot address a filename component larger than255 UTF-8 bytes.
    # Descriptive config fields may contain arbitrarily long ordinary text.
    if any(len(part.encode('utf-8'))>255 for part in path.parts):return None
    absolute=path if path.is_absolute() else root/path
    if len(os.fsencode(absolute))>=4096:return None
    return absolute.resolve()


def _require_independent_excluded_asset(asset, native_shas, member_sha, independently_routed=None):
    """A prefix alone cannot prove that an excluded asset survives retirement."""
    metadata=asset.get('metadata') or {}
    refs=[asset.get('uri'),metadata.get('source_ref'),metadata.get('source_path')]
    expected={sha for ref in refs if isinstance(ref,str) and ref and (sha:=member_sha(ref))}
    if len(expected)>1:raise ValueError('Excluded media has conflicting native member checksums')
    native_ref=bool(expected)
    sha=asset.get('sha256')
    if sha and native_ref and sha not in expected:raise ValueError('Excluded media checksum differs from its native member')
    if not native_ref and isinstance(sha,str) and re.fullmatch(r'[0-9a-f]{64}',sha) and sha not in native_shas:return
    measured_sha=sha if isinstance(sha,str) and re.fullmatch(r'[0-9a-f]{64}',sha) else next(iter(expected),None)
    if independently_routed and measured_sha and independently_routed(asset,measured_sha):return
    if native_ref:raise ValueError('Excluded media is a member of the archive being retired')
    raise ValueError('Excluded media lacks a checksum proving independence from this archive')


def _independent_route_checker(root, version, current_native_sha):
    from .indexed_tar import route_path,_file_identity
    from dataset_atlas.adapters.core import _safe_relative
    from contextlib import closing
    route=route_path(root,version.id,version.snapshot_id)
    config=json.loads(route.read_text()) if route.is_file() else {}
    if config and (config.get('dataset_id'),config.get('snapshot_id'))!=(version.id,version.snapshot_id):
        raise ValueError('Independent original route identity changed')
    verified={};base=(root/'work/original-access').resolve()
    def check(asset,expected_sha):
        metadata=asset.get('metadata') or {}
        for ref in [asset.get('uri'),metadata.get('source_ref'),metadata.get('source_path')]:
            if not isinstance(ref,str):continue
            for mapping in config.get('archives',[]):
                prefix=mapping.get('asset_prefix','')
                if not ref.startswith(prefix):continue
                index=(base/mapping['index']).resolve()
                if not index.is_relative_to(base):raise ValueError('Independent original index outside configured root')
                receipt=index/'receipt.json'
                if not receipt.is_file():continue
                proof=json.loads(receipt.read_text())
                source_sha=proof.get('source_sha256')
                if not isinstance(source_sha,str) or not re.fullmatch(r'[0-9a-f]{64}',source_sha):
                    raise ValueError('Independent native archive lacks a pinned source checksum')
                if proof.get('source_sha256')==current_native_sha:continue
                if proof.get('format') not in {'atlas-remote-tar-v1','atlas-remote-gzip-tar-v1','atlas-remote-zip-v1'}:
                    raise ValueError('Unsupported independent archive index')
                derivatives={name:(index/_safe_relative(name)).resolve() for name in proof['checksums']}
                if any(not path.is_relative_to(index) for path in derivatives.values()):
                    raise ValueError('Independent native index derivative outside its root')
                database=index/'members.sqlite'
                if 'members.sqlite' not in derivatives:raise ValueError('Independent native index lacks its member checksum')
                identity=tuple((name,_file_identity(path)) for name,path in sorted(derivatives.items()))
                if verified.get(index)!=identity:
                    for name,path in derivatives.items():
                        with path.open('rb') as stream:
                            if hashlib.file_digest(stream,'sha256').hexdigest()!=proof['checksums'][name]:
                                raise ValueError('Independent native index derivative checksum changed')
                    verified[index]=identity
                name=mapping.get('member_prefix','')+ref[len(prefix):]
                name=mapping.get('member_names',{}).get(name,name)
                with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as db:
                    member=db.execute('SELECT sha256 FROM members WHERE name=?',(name,)).fetchone()
                if member is None:continue
                if expected_sha!=member[0]:raise ValueError('Independent route differs from excluded native asset checksum')
                return True
        return False
    return check


def retire_image_archive(root, dataset_id, index_name, source, *, mappings,
                         max_preview_bytes=500_000_000, max_transfer_bytes=150_000_000,
                         extracted_root=None, linked_datasets=(), modalities=('image',), execute=False):
    import pyarrow.parquet as pq
    from dataset_atlas.registry import Registry
    from dataset_atlas.preparation import atomic
    from .compact import encode_image, store_directory
    from .indexed_tar import route_path, read_tar_member, _file_identity
    from .indexed_zip import read_zip_member
    from .zip_members import LOCAL_ZIP_MEMBERS

    if not modalities or any(modality not in {'image', 'audio'} for modality in modalities):
        raise ValueError('Retirement modalities must be image and/or audio')
    modalities = frozenset(modalities)

    root = Path(root).resolve(); registry = Registry(root); dataset_id = registry.resolve(dataset_id)
    dataset_ids = {dataset_id, *(registry.resolve(identity) for identity in linked_datasets)}
    base = (root/'work/original-access').resolve(); index = (base/index_name).resolve()
    if not index.is_relative_to(base): raise ValueError('Original-access index outside configured root')
    source = Path(source); source = (root/source).resolve() if not source.is_absolute() else source.resolve()
    owned = [root/'work/sources', root/'work/prepared', root/'work/source-objects']
    if not any(source.is_relative_to(p) for p in owned): raise ValueError('Only acquired Atlas source copies can be retired')
    native = json.loads((index/'receipt.json').read_text())
    before = _file_identity(source)
    def strings(obj):
        if isinstance(obj, str): yield obj
        elif isinstance(obj, dict):
            for value in obj.values(): yield from strings(value)
        elif isinstance(obj, list):
            for value in obj: yield from strings(value)
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != native['source_sha256']:
            raise ValueError('Retirement source differs from verified archive')
    if source.stat().st_size != native['source_bytes']: raise ValueError('Retirement source size changed')
    reader = read_zip_member if native['format'] == 'atlas-remote-zip-v1' else read_tar_member
    if native['format'] not in {'atlas-remote-zip-v1', 'atlas-remote-gzip-tar-v1', 'atlas-remote-tar-v1'}:
        raise ValueError('Unsupported original-access index')
    if not mappings: raise ValueError('At least one archive mapping is required')
    routes = []; required = {}; preview_copies = []; preview_bytes = 0; references = 0
    def in_scope(ref):
        return any(ref.startswith(entry.get('asset_prefix', '')) for entry in mappings)
    def member_for(ref):
        for entry in mappings:
            prefix = entry.get('asset_prefix', '')
            if ref.startswith(prefix):
                member = entry.get('member_prefix', '') + ref[len(prefix):]
                row = members.execute('SELECT sha256,bytes FROM members WHERE name=?', (member,)).fetchone()
                if row: return member, row[0], row[1]
        raise ValueError(f'No verified native member for {ref}')
    with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro', uri=True) as members:
        native_shas={row[0] for row in members.execute('SELECT sha256 FROM members')}
        def member_sha(ref):
            row=members.execute('SELECT sha256 FROM members WHERE name=?',(ref,)).fetchone()
            return row[0] if row else None
        for version, pack_path, snapshot in [item for identity in sorted(dataset_ids) for item in registry.versions(identity)]:
            if not snapshot.is_dir(): continue
            if native['source_sha256'] not in set(strings(version.adapter_config)):
                for value in strings(version.adapter_config):
                    candidate = _local_config_path(root,value)
                    if candidate is None:continue
                    if candidate.is_file() and candidate.samefile(source):
                        raise ValueError('A retained snapshot references this source without its pinned archive checksum')
                # A different retained release keeps its own source and routes.
                continue
            pack = json.loads(pack_path.read_text())
            independent_route=_independent_route_checker(root,version,native['source_sha256'])
            preview = {a['id']: a for r in pack['records'] for a in r['assets'] if a.get('uri') and a['modality'] in modalities and in_scope(a['uri'])}
            found = {}; seen = set()
            for batch in pq.ParquetFile(snapshot/'records.parquet').iter_batches(columns=['record_json'], batch_size=512):
                for value in batch.column(0).to_pylist():
                    for asset in json.loads(value)['assets']:
                        ref = asset.get('uri')
                        if not ref or asset['modality'] not in modalities: continue
                        if not in_scope(ref):
                            _require_independent_excluded_asset(asset,native_shas,member_sha,independent_route)
                            continue
                        if ref not in seen:
                            required[ref] = member_for(ref); seen.add(ref)
                        if asset.get('sha256') and asset['sha256'] != required[ref][1]:
                            raise ValueError('Retained asset checksum differs from this archive')
                        references += 1
                        if asset['id'] in preview: found[asset['id']] = ref
            if set(found) != set(preview): raise ValueError('A retained preview is absent from its full snapshot')
            if not seen: raise ValueError('Archive mappings cover no media in a dependent snapshot')
            for asset_id, ref in found.items():
                member, sha, size = required[ref]
                asset = preview[asset_id]
                if asset.get('sha256') and asset['sha256'] != sha:
                    raise ValueError('Preview differs from indexed source member')
                preview_bytes += size
                preview_copies.append((version.id, version.snapshot_id, {ref, asset['uri']}, member, sha, size, asset['modality']))
            path = route_path(root, version.id, version.snapshot_id)
            config = json.loads(path.read_text()) if path.exists() else {'dataset_id': version.id, 'snapshot_id': version.snapshot_id, 'archives': []}
            entries = [{'index': str(index.relative_to(base)), **entry} for entry in mappings]
            config['archives'] = entries + [e for e in config['archives'] if e.get('index') != str(index.relative_to(base))]
            routes.append((path, config))
        if not routes or not required: raise ValueError('Retirement requires a retained complete media snapshot')
        if {config['dataset_id'] for _,config in routes} != dataset_ids:
            raise ValueError('Every linked dataset requires a retained complete snapshot for this exact source')
        if preview_bytes > max_preview_bytes: raise ValueError('Preview originals exceed retention budget')

        # Cold remote reads verify source availability, exact member hashes, and
        # the entire local index before any source is eligible for removal.
        candidates = sorted(set(required.values()))
        probes = [candidates[i] for i in sorted({0, len(candidates)//2, len(candidates)-1})]
        transfer = 0; evidence = []
        for member, sha, size in probes:
            remaining = max_transfer_bytes - transfer
            if remaining < 1: raise ValueError('Original verification transfer budget exhausted')
            data, proof = reader(index, member, max_bytes=50_000_000, transfer_bytes=remaining)
            transfer += proof['transferred_bytes']; evidence.append(proof)
            if hashlib.sha256(data).hexdigest() != sha: raise ValueError('Cold original verification failed')

        extracted = []
        if extracted_root is not None:
            directory = Path(extracted_root); directory = (root/directory).resolve() if not directory.is_absolute() else directory.resolve()
            if not any(directory.is_relative_to(p) for p in owned): raise ValueError('Extracted originals outside Atlas source directories')
            for path in directory.rglob('*'):
                if path.is_symlink(): raise ValueError('Extracted source contains symlinks')
                if not path.is_file(): continue
                _, expected, size = member_for(path.relative_to(directory).as_posix())
                with path.open('rb') as stream:
                    if path.stat().st_size != size or hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                        raise ValueError('Extracted original differs from native archive')
                extracted.append((path, _file_identity(path)))

    inode = (source.stat().st_dev, source.stat().st_ino); paths = []
    for directory, _, files in os.walk(root/'work'):
        for name in files:
            path = Path(directory)/name
            if path.is_symlink(): continue
            try: stat = path.stat()
            except FileNotFoundError: continue  # A disposable cache/journal can disappear during the scan.
            if (stat.st_dev, stat.st_ino) == inode:
                if not any(path.is_relative_to(p) for p in [*owned, root/'work/download-cache']):
                    raise ValueError('An original hard link lies outside acquired-source directories')
                paths.append(path)
    if len(paths) != source.stat().st_nlink: raise ValueError('Original has hard links outside Atlas work directories')
    for other in registry.datasets():
        if other.id in dataset_ids: continue
        for version, _, _ in registry.versions(other.id):
            for value in strings(version.adapter_config):
                path = _local_config_path(root,value)
                if path is None:continue
                if path.is_file() and (path.stat().st_dev, path.stat().st_ino) == inode:
                    raise ValueError(f'Original is required by retained dataset {other.id}')
    # Check extracted-directory dependencies separately from shared archive inodes.
    if extracted_root is not None:
        extracted_base = Path(extracted_root); extracted_base = (root/extracted_base).resolve() if not extracted_base.is_absolute() else extracted_base.resolve()
        for other in registry.datasets():
            if other.id in dataset_ids: continue
            for version, _, _ in registry.versions(other.id):
                for value in strings(version.adapter_config):
                    path = _local_config_path(root,value)
                    if path is None:continue
                    if path.resolve().is_relative_to(extracted_base):
                        raise ValueError(f'Extracted originals are required by {other.id}')
    report = {'dataset_id': dataset_id, 'source_sha256': native['source_sha256'],
              'linked_dataset_ids': sorted(dataset_ids - {dataset_id}),
              'status': 'verified_plan', 'retained_snapshots': len(routes), 'media_references_checked': references,
              'unique_native_media_in_snapshots': len(set(required.values())), 'preview_asset_memberships': len(preview_copies),
              'modalities': sorted(modalities),
              'preview_bytes_upper_bound': preview_bytes, 'cold_original_probes': evidence,
              'paths': [str(p.relative_to(root)) for p in paths], 'extracted_files': len(extracted),
              'source_bytes': native['source_bytes'], 'extracted_bytes': sum(identity[2] for _, identity in extracted),
              'retention': 'Original-quality previews and complete indices; other originals and optimized browsing copies on demand.'}
    if not execute: return report
    # Every preview representation is installed and checked before any deletion.
    for owner_id, snapshot_id, refs, member, sha, size, modality in preview_copies:
        if reader is read_zip_member:
            data = LOCAL_ZIP_MEMBERS.read(source, member, 50_000_000, native['source_sha256'])
        else:
            data, _ = read_tar_member(index, member, local_source=source, max_bytes=50_000_000)
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha: raise ValueError('Preview retention checksum mismatch')
        if modality == 'image':
            _, mime, metadata = encode_image(data, protected=True)
        else:
            from dataset_atlas.adapters.core import _media_type
            mime = _media_type(member)
            metadata = {'original_sha256': sha, 'original_bytes': len(data),
                        'protected_preview': True, 'representation': 'original'}
        store = store_directory(root, owner_id, snapshot_id); (store/'objects').mkdir(parents=True, exist_ok=True)
        with (store/'writer.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            target = store/'objects'/sha
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha: raise ValueError('Existing preview original is corrupt')
            else:
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name); stream.write(data)
                try: os.replace(temporary, target)
                finally: temporary.unlink(missing_ok=True)
            metadata.update(sha256=sha, bytes=len(data), mime=mime)
            with sqlite3.connect(store/'index.sqlite') as db:
                db.execute('CREATE TABLE IF NOT EXISTS media (ref TEXT PRIMARY KEY, metadata TEXT NOT NULL)')
                for ref in refs: db.execute('INSERT OR REPLACE INTO media VALUES (?,?)', (ref, json.dumps(metadata)))
    for path, config in routes: atomic(path, config)
    if _file_identity(source) != before: raise ValueError('Original changed during retirement verification')
    for path, identity in extracted:
        if _file_identity(path) != identity: raise ValueError('Extracted original changed during verification')
    receipt_path = base/'retirements'/f'{dataset_id}-{native["source_sha256"]}.json'
    report['status'] = 'routes_installed'; atomic(receipt_path, report)
    # These files were acquired/derived by Atlas, never corpus originals. Saved
    # snapshots resolve through installed member routes after this point.
    for path in paths: path.unlink()
    freed_extracted = 0
    for path, identity in extracted:
        if path.stat().st_nlink == 1: freed_extracted += path.stat().st_size
        path.unlink()
    report.update(status='executed', freed_unique_file_bytes=native['source_bytes'] + freed_extracted)
    atomic(receipt_path, report)
    return report


def retire_repacked_archive(root, index_name, source, *, source_sha256,
                            max_decoded_bytes, max_transfer_bytes=150_000_000,
                            execute=False):
    """Retire a redundant ZIP only after exact parity and existing route checks.

    Unlike retirement of a native source, this never installs routes. Every
    dependent snapshot must already have verified native access and pinned
    original previews, including datasets that share the repacked archive.
    """
    import zipfile
    import pyarrow.parquet as pq
    from dataset_atlas.registry import Registry
    from dataset_atlas.adapters.core import _safe_relative
    from dataset_atlas.preparation import atomic
    from .indexed_tar import _file_identity, route_path, read_tar_member
    from .indexed_zip import read_zip_member
    from .compact import read_compact

    root = Path(root).resolve(); source = Path(source)
    source = (root/source).resolve() if not source.is_absolute() else source.resolve()
    owned = [root/'work/prepared', root/'work/sources', root/'work/source-objects']
    if not any(source.is_relative_to(p) for p in owned):
        raise ValueError('Only acquired Atlas repacked archives can be retired')
    if any(type(value) is not int or value < 1 for value in (max_decoded_bytes,max_transfer_bytes)):
        raise ValueError('Positive decoded-work and transfer budgets required')
    before = _file_identity(source)
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != source_sha256:
            raise ValueError('Repacked archive checksum changed')
    base = (root/'work/original-access').resolve(); index = (base/index_name).resolve()
    if not index.is_relative_to(base): raise ValueError('Original-access index outside configured root')
    native = json.loads((index/'receipt.json').read_text())
    if native['format'] not in {'atlas-remote-gzip-tar-v1', 'atlas-remote-tar-v1', 'atlas-remote-zip-v1'}:
        raise ValueError('Unsupported native index format')
    with (index/'members.sqlite').open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != native['checksums']['members.sqlite']:
            raise ValueError('Native member index checksum changed')
    with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        expected = {name:(size,sha) for name,size,sha in db.execute('SELECT name,bytes,sha256 FROM members')}
    if not expected: raise ValueError('Native archive contains no members')
    native_shas={sha for _,sha in expected.values()}
    decoded = 0; seen = set()
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            if member.is_dir(): continue
            name = _safe_relative(member.filename)
            if name in seen or name not in expected: raise ValueError('Repacked member absent or duplicated in native inventory')
            seen.add(name); size,sha = expected[name]; decoded += member.file_size
            if decoded > max_decoded_bytes: raise ValueError('Repacked archive exceeds decoded-work budget')
            if member.file_size != size: raise ValueError('Repacked member size differs from native source')
            digest = hashlib.sha256()
            with archive.open(member) as stream:
                for block in iter(lambda:stream.read(1 << 20),b''): digest.update(block)
            if digest.hexdigest() != sha:
                raise ValueError('Repacked member differs from native source')
    if seen != set(expected): raise ValueError('Repacked archive omits native members')

    def strings(obj):
        if isinstance(obj,str): yield obj
        elif isinstance(obj,dict):
            for value in obj.values(): yield from strings(value)
        elif isinstance(obj,list):
            for value in obj: yield from strings(value)
    inode = tuple(before[:2]); dependencies = []; route_identities = []; references = 0; previews = 0
    registry = Registry(root)
    for dataset in registry.datasets():
        for version,pack_path,snapshot in registry.versions(dataset.id):
            values = set(strings(version.adapter_config)); dependent = False
            for value in values:
                candidate = _local_config_path(root,value)
                if candidate is None:continue
                if candidate.is_file() and tuple(_file_identity(candidate)[:2]) == inode: dependent = True
            if not dependent: continue
            if source_sha256 not in values or native['source_sha256'] not in values:
                raise ValueError('Dependent snapshot lacks both pinned archive identities')
            route = route_path(root,version.id,version.snapshot_id)
            if not route.is_file() or not (snapshot/'records.parquet').is_file():
                raise ValueError('Dependent snapshot lacks complete index or native routes')
            config = json.loads(route.read_text()); route_identities.append((route,_file_identity(route)))
            if config.get('dataset_id') != version.id or config.get('snapshot_id') != version.snapshot_id:
                raise ValueError('Native route identity changed')
            mappings = config['archives']
            independent_route=_independent_route_checker(root,version,native['source_sha256'])
            def native_member(asset):
                ref=asset['uri']
                # Multi-archive datasets retain separate routes. Only references
                # assigned to this archive participate in its retirement; a
                # conflicting preceding route still fails closed.
                if not any((base/mapping['index']).resolve() == index and ref.startswith(mapping.get('asset_prefix','')) for mapping in mappings):
                    _require_independent_excluded_asset(asset,native_shas,lambda name:expected[name][1] if name in expected else None,independent_route)
                    return None
                for mapping in mappings:
                    prefix = mapping.get('asset_prefix','')
                    if not ref.startswith(prefix): continue
                    if (base/mapping['index']).resolve() != index:
                        raise ValueError('Dependent media has a different preceding native route')
                    name = mapping.get('member_prefix','') + ref[len(prefix):]
                    name = mapping.get('member_names',{}).get(name,name)
                    if name in expected: return name
                raise ValueError('Dependent media has no verified native route')
            affected = 0
            for batch in pq.ParquetFile(snapshot/'records.parquet').iter_batches(columns=['record_json'],batch_size=512):
                for raw in batch.column(0).to_pylist():
                    for asset in json.loads(raw)['assets']:
                        if not asset.get('uri'): continue
                        name = native_member(asset)
                        if name is None: continue
                        if asset['modality'] != 'image': raise ValueError('Repacked retirement requires image-only media references')
                        references += 1; affected += 1
                        if asset.get('sha256') and asset['sha256'] != expected[name][1]:
                            raise ValueError('Snapshot image differs from native member')
            for record in json.loads(pack_path.read_text())['records']:
                for asset in record['assets']:
                    if not asset.get('uri'): continue
                    name = native_member(asset)
                    if name is None: continue
                    size,sha = expected[name]
                    result = read_compact(root,version.id,version.snapshot_id,asset['uri'],size)
                    if result is None or not result[2].get('protected_preview') or hashlib.sha256(result[0]).hexdigest() != sha:
                        raise ValueError('Dependent preview original is not pinned')
                    previews += 1
            if not affected: raise ValueError('Native routes cover no media in a dependent snapshot')
            dependencies.append({'dataset_id':version.id,'snapshot_id':version.snapshot_id})
    if not dependencies: raise ValueError('No dependent retained image snapshots found')
    reader = read_zip_member if native['format'] == 'atlas-remote-zip-v1' else read_tar_member
    names = sorted(expected); transferred = 0; probes = []
    for name in [names[i] for i in sorted({0,len(names)//2,len(names)-1})]:
        data,proof = reader(index,name,max_bytes=50_000_000,transfer_bytes=max_transfer_bytes-transferred)
        if hashlib.sha256(data).hexdigest() != expected[name][1]: raise ValueError('Cold native member verification failed')
        transferred += proof['transferred_bytes']; probes.append(proof)
    paths = []
    for directory,_,files in os.walk(root/'work'):
        for name in files:
            path = Path(directory)/name
            if path.is_symlink(): continue
            try: identity = _file_identity(path)
            except FileNotFoundError: continue
            if tuple(identity[:2]) == inode:
                if not any(path.is_relative_to(p) for p in [*owned,root/'work/download-cache']):
                    raise ValueError('Repacked hard link lies outside acquired directories')
                paths.append(path)
    if len(paths) != source.stat().st_nlink: raise ValueError('Repacked archive has external hard links')
    report = {'status':'verified_plan','source_sha256':source_sha256,'source_bytes':before[2],
              'native_source_sha256':native['source_sha256'],'native_index':index_name,
              'all_native_members_checked':len(seen),'decoded_bytes':decoded,
              'retained_dependencies':dependencies,'image_references_checked':references,
              'pinned_preview_references_checked':previews,'cold_original_probes':probes,
              'paths':[str(p.relative_to(root)) for p in paths]}
    if not execute: return report
    if _file_identity(source) != before or any(_file_identity(p) != identity for p,identity in route_identities):
        raise ValueError('Repacked archive or native routes changed during verification')
    receipt = base/'retirements'/f'repacked-{source_sha256}.json'; atomic(receipt,report)
    for path in paths: path.unlink()
    report.update(status='executed',freed_unique_file_bytes=before[2]); atomic(receipt,report)
    return report
