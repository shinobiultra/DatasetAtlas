"""Conservative workspace cleanup: evict caches and hard-link verified source copies.

Never remove a dataset version, a preview, a model, or an original source. Byte
identical source copies retain all their paths; only redundant inodes disappear.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import stat

from .usage import workspace_usage


def _file_signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _replace_verified_link(root, original, target, original_info, target_info):
    """Replace through anchored directories only after checking the new link.

    Linking changes ctime itself. All other verified source metadata must stay
    identical, and the source and temporary link must share the updated inode.
    Keep a rollback link to the old target until postchecks succeed. Directory
    descriptors prevent an ancestor swap from redirecting writes or recovery.
    """
    with ExitStack() as descriptors:
        try:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            root_fd = os.open(root, flags)
            descriptors.callback(os.close, root_fd)
            ancestors = []

            def parent_fd(path):
                directory = root_fd
                relative = path.relative_to(root)
                if '..' in relative.parts:
                    raise ValueError('Path changed during cleanup')
                for name in relative.parts[:-1]:
                    child = os.open(name, flags, dir_fd=directory)
                    descriptors.callback(os.close, child)
                    ancestors.append((directory, name, child))
                    directory = child
                return directory

            source_fd = parent_fd(original)
            target_fd = parent_fd(target)

            def validate_ancestors():
                pairs = [(root.lstat(), os.fstat(root_fd))]
                pairs.extend((os.stat(name, dir_fd=parent, follow_symlinks=False), os.fstat(child))
                             for parent, name, child in ancestors)
                for current, anchored in pairs:
                    if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (anchored.st_dev, anchored.st_ino):
                        raise ValueError('Directory changed during cleanup')

            def source_stat():
                return os.stat(original.name, dir_fd=source_fd, follow_symlinks=False)

            def target_stat():
                return os.stat(target.name, dir_fd=target_fd, follow_symlinks=False)

            validate_ancestors()
            if (_file_signature(source_stat()) != _file_signature(original_info)
                    or _file_signature(target_stat()) != _file_signature(target_info)):
                raise ValueError('Immutable file changed during cleanup')
            temporary = '.atlas-link-' + secrets.token_hex(12)
            rollback = '.atlas-link-backup-' + secrets.token_hex(12)
            linked = False
            backed_up = False
            replace_attempted = False
            retain_backup = False
            try:
                os.link(target.name, rollback, src_dir_fd=target_fd,
                        dst_dir_fd=target_fd, follow_symlinks=False)
                backed_up = True
                backup_info = os.stat(rollback, dir_fd=target_fd, follow_symlinks=False)
                validate_ancestors()
                if (not stat.S_ISREG(backup_info.st_mode)
                        or _file_signature(backup_info)[:-1] != _file_signature(target_info)[:-1]
                        or _file_signature(target_stat()) != _file_signature(backup_info)):
                    raise ValueError('Immutable file changed during cleanup')
                os.link(original.name, temporary, src_dir_fd=source_fd,
                        dst_dir_fd=target_fd, follow_symlinks=False)
                linked = True
                temporary_info = os.stat(temporary, dir_fd=target_fd, follow_symlinks=False)
                current_source = source_stat()
                validate_ancestors()
                if (not stat.S_ISREG(temporary_info.st_mode)
                        or _file_signature(temporary_info)[:-1] != _file_signature(original_info)[:-1]
                        or _file_signature(current_source) != _file_signature(temporary_info)
                        or _file_signature(target_stat()) != _file_signature(backup_info)):
                    raise ValueError('Immutable file changed during cleanup')
                replace_attempted = True
                os.replace(temporary, target.name, src_dir_fd=target_fd, dst_dir_fd=target_fd)
                validate_ancestors()
                updated_source = source_stat()
                if (not stat.S_ISREG(updated_source.st_mode)
                        or _file_signature(updated_source)[:-1] != _file_signature(original_info)[:-1]
                        or _file_signature(target_stat()) != _file_signature(updated_source)):
                    raise ValueError('Immutable file changed during cleanup')
                return updated_source
            except BaseException:
                if replace_attempted:
                    try:
                        recovery_info = os.stat(rollback, dir_fd=target_fd, follow_symlinks=False)
                        if (not stat.S_ISREG(recovery_info.st_mode)
                                or _file_signature(recovery_info)[:-1] != _file_signature(target_info)[:-1]):
                            raise ValueError('Recovery copy changed during cleanup')
                        os.replace(rollback, target.name, src_dir_fd=target_fd, dst_dir_fd=target_fd)
                        backed_up = False
                    except (OSError, ValueError) as exc:
                        retain_backup = True
                        recovery = str(target.parent / rollback)
                        raise ValueError(f'Cleanup could not restore the original; retained recovery link at {recovery}') from exc
                raise
            finally:
                if linked:
                    try:
                        os.unlink(temporary, dir_fd=target_fd)
                    except FileNotFoundError:
                        pass
                if backed_up and not retain_backup:
                    os.unlink(rollback, dir_fd=target_fd)
        except OSError as exc:
            raise ValueError('Immutable file or directory changed during cleanup') from exc


@contextmanager
def _locked_file(path):
    if path.is_symlink():
        raise ValueError('Symlink in storage lock; cleanup refused')
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Storage is being read or written; retry cleanup when idle') from None
        yield


@contextmanager
def _deduplication_locks(root):
    """Exclude coordinators and both preparation writers throughout replacement.

    Acquire admission before writer slots, matching preparation dispatch. Every
    acquisition is nonblocking, so a busy writer releases this entire attempt.
    Retain cache/store leases until every verified replacement has finished.
    """
    from dataset_atlas.jobs.coordinator_lock import acquire_coordinator_lock
    work = root / 'work'
    if work.is_symlink():
        raise ValueError('Cleanup requires an Atlas-owned work directory')
    work.mkdir(parents=True, exist_ok=True)
    if (work / '.coordinator.lock').is_symlink():
        raise ValueError('Symlink in storage lock; cleanup refused')
    with ExitStack() as leases:
        coordinator = acquire_coordinator_lock(work)
        leases.callback(coordinator.close)
        preparation = work / 'preparation'
        if preparation.is_symlink():
            raise ValueError('Symlink in preparation directory; cleanup refused')
        preparation.mkdir(exist_ok=True)
        for name in ('storage-admission.lock', 'writer-0.lock', 'writer-1.lock', 'source-transfer.lock'):
            leases.enter_context(_locked_file(preparation / name))
        for base in (work / 'media-cache', work / 'download-cache', work / 'sources'):
            if not base.is_dir() or base.is_symlink():
                continue
            for directory, children, files in os.walk(base, followlinks=False):
                children[:] = [name for name in children if not (Path(directory) / name).is_symlink()]
                if 'cache.sqlite3' in files and not (Path(directory) / 'cache.sqlite3').is_symlink():
                    leases.enter_context(_locked_file(Path(directory) / 'range-cache.lock'))
        compact = work / 'compact-media'
        if compact.is_dir() and not compact.is_symlink():
            for store in compact.iterdir():
                if (store.is_dir() and not store.is_symlink()
                        and (store / 'index.sqlite').is_file()
                        and not (store / 'index.sqlite').is_symlink()
                        and not (store / 'objects').is_symlink()):
                    leases.enter_context(_locked_file(store / 'writer.lock'))
        yield


@contextmanager
def _locked_database(path, lock_name):
    with (path.parent/lock_name).open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Storage is being read or written; retry cleanup when idle') from None
        with sqlite3.connect(path) as db:
            yield db


def evict_idle_media_caches(root,*,execute=False):
    """Evict unpinned media caches outside all active preparation namespaces."""
    root=Path(root).resolve();base=root/'work/media-cache';protected=set()
    if (root/'work').is_symlink():raise ValueError('Cleanup requires an Atlas-owned work directory')
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for item in value.values():yield from strings(item)
        elif isinstance(value,list):
            for item in value:yield from strings(item)
    for status in (root/'work/preparation').glob('*/status.json'):
        if json.loads(status.read_text()).get('status') not in {'running','queued'}:continue
        plan=json.loads((status.parent/'plan.json').read_text())
        config=(plan.get('prepared_dataset') or plan['dataset']).get('adapter_config',{})
        for value in strings(config):
            path=Path(value)
            if not path.is_absolute():path=root/path
            path=path.resolve()
            if path.is_relative_to(base):protected.add(path)
        if plan.get('kind') in {'huggingface_remote_columnar','huggingface_remote_sample'}:protected.add(base/'remote-parquet')
    before=workspace_usage(root);removed=[];skipped=[]
    if base.is_dir() and not base.is_symlink():
        for path in base.glob('*/cache.sqlite3'):
            directory=path.parent
            if directory.is_symlink() or path.is_symlink():continue
            if any(directory.is_relative_to(p) or p.is_relative_to(directory) for p in protected):
                skipped.append(str(directory.relative_to(root)));continue
            with _locked_database(path,'range-cache.lock') as db:
                db.execute('BEGIN IMMEDIATE')
                for key,relative in db.execute('SELECT key,path FROM entries WHERE pinned=0').fetchall():
                    if not re.fullmatch('[a-f0-9]{64}',key) or relative!=f'objects/{key}':raise ValueError('Unsafe media cache entry')
                    target=directory/relative
                    if target.is_symlink() or target.parent.is_symlink():raise ValueError('Symlink in media cache')
                    removed.append(str(target.relative_to(root)))
                    if execute:
                        target.unlink(missing_ok=True);db.execute('DELETE FROM entries WHERE key=?',(key,))
    after=workspace_usage(root)
    return {'executed':execute,'cache_entries':removed,'active_cache_namespaces_preserved':skipped,
            'freed_allocated_bytes':max(0,before['allocated_bytes']-after['allocated_bytes']) if execute else 0,
            'scope':'Only unpinned media cache entries. Sources, preview packs, snapshots, models and all active preparation caches are retained.'}


def clean_workspace(root, *, execute=False, include_model_test_env=False, deduplicate_only=False):
    """Share verified immutable bytes, optionally leaving every cache and copy intact."""
    root = Path(root).resolve()
    if deduplicate_only and execute:
        with _deduplication_locks(root):
            return _clean_workspace(root, execute=execute, include_model_test_env=include_model_test_env,
                                    deduplicate_only=deduplicate_only)
    return _clean_workspace(root, execute=execute, include_model_test_env=include_model_test_env,
                            deduplicate_only=deduplicate_only)


def _clean_workspace(root, *, execute, include_model_test_env, deduplicate_only):
    root = Path(root).resolve()
    work = root / 'work'
    if work.is_symlink():
        raise ValueError('Cleanup requires an Atlas-owned work directory')
    if execute:
        for path in (work/'preparation').glob('*/status.json'):
            if json.loads(path.read_text()).get('status') in {'queued','running'}:
                raise ValueError('Wait for active preparations before cleaning this workspace')
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'executed': execute,
              'deduplicate_only': deduplicate_only,
              'temporary_directories': [], 'cache_entries': [], 'source_links': [], 'compressed_copies': [],'derivative_links':[]}
    before = workspace_usage(root)
    # These are isolated installation-test environments, not the application or
    # local model server environments. Keep all verification logs and receipts.
    temporary = [] if deduplicate_only else [work / 'clean-ci-check']
    if include_model_test_env and not deduplicate_only:
        temporary.append(work / 'model-server/.venv')
    verify = work / 'verify-install'
    if not deduplicate_only and verify.is_dir() and not verify.is_symlink():
        temporary += [p for p in verify.iterdir() if p.name.endswith(('-venv', '-env')) and (p / 'pyvenv.cfg').is_file()]
    for path in temporary:
        if path.is_dir() and not path.is_symlink():
            report['temporary_directories'].append(str(path.relative_to(root)))
            if execute:
                shutil.rmtree(path)
    # Native sources and prepared versions may share cache inodes. Unlinking an
    # unpinned cache entry preserves those links, and accounting measures this.
    for base in (work / 'media-cache', work / 'download-cache', work / 'sources'):
        if not base.is_dir() or base.is_symlink():
            continue
        for directory, children, files in os.walk(base, followlinks=False):
            children[:] = [name for name in children if not (Path(directory) / name).is_symlink()]
            if 'cache.sqlite3' not in files:
                continue
            db_path = Path(directory) / 'cache.sqlite3'
            if db_path.is_symlink():
                continue
            if deduplicate_only and execute:
                continue  # The outer guard holds this cache lease for the whole operation.
            with _locked_database(db_path,'range-cache.lock') as db:
                if deduplicate_only:
                    continue
                columns = {row[1] for row in db.execute('PRAGMA table_info(entries)')}
                if not {'key', 'path', 'pinned', 'representation', 'fingerprint_type'} <= columns:
                    continue
                db.execute('BEGIN IMMEDIATE')
                for key, relative in db.execute('SELECT key,path FROM entries WHERE pinned=0').fetchall():
                    if not re.fullmatch('[a-f0-9]{64}', key) or relative != f'objects/{key}':
                        raise ValueError('Unsafe cache entry; cleanup refused')
                    path = db_path.parent / relative
                    if path.is_symlink() or path.parent.is_symlink():
                        raise ValueError('Symlink in cache; cleanup refused')
                    report['cache_entries'].append(str(path.relative_to(root)))
                    if execute:
                        path.unlink(missing_ok=True)
                        db.execute('DELETE FROM entries WHERE key=?', (key,))
    compact=work/'compact-media'
    if compact.is_dir() and not compact.is_symlink():
        for store in compact.iterdir():
            if store.is_symlink() or not store.is_dir() or not (store/'index.sqlite').is_file():continue
            if (store/'index.sqlite').is_symlink() or (store/'objects').is_symlink():continue
            if deduplicate_only and execute:continue
            with _locked_database(store/'index.sqlite','writer.lock') as db:
                if deduplicate_only:continue
                rows=[(ref,json.loads(raw)) for ref,raw in db.execute('SELECT ref,metadata FROM media')]
                retained={item['sha256'] for _,item in rows if item.get('protected_preview') or item.get('representation')!='compressed_avif'}
                for ref,item in rows:
                    if item.get('protected_preview') or item.get('representation')!='compressed_avif':continue
                    digest=item['sha256']
                    if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Unsafe compact media identity')
                    path=store/'objects'/digest
                    if path.is_symlink():raise ValueError('Symlink in compact store; cleanup refused')
                    report['compressed_copies'].append({'store':store.name,'ref':ref,'sha256':digest})
                    if execute:
                        db.execute('DELETE FROM media WHERE ref=?',(ref,))
                        if digest not in retained:path.unlink(missing_ok=True)
    objects = work / 'source-objects'
    candidates = {}
    if objects.is_dir() and not objects.is_symlink():
        for path in sorted(objects.iterdir()):
            if re.fullmatch('[a-f0-9]{64}', path.name) and path.is_file() and not path.is_symlink():
                candidates.setdefault(path.stat().st_size, []).append(path)
    verified = {}
    # Only immutable acquired source files are eligible. SQLite, artifacts,
    # original corpus files, user data, and preview media are outside this scan.
    for base in (work / 'sources', work / 'prepared'):
        if not base.is_dir() or base.is_symlink():
            continue
        for directory, children, files in os.walk(base, followlinks=False):
            children[:] = [name for name in children if not (Path(directory) / name).is_symlink()]
            if base.name == 'prepared' and Path(directory).name != 'sources':
                continue
            for name in files:
                path = Path(directory) / name
                if path.is_symlink() or path.suffix in {'.sqlite', '.sqlite3', '.db'}:
                    continue
                info = path.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_size < 1_000_000 or info.st_size not in candidates:
                    continue
                for original in candidates[info.st_size]:
                    pinned = original.stat()
                    if (info.st_dev != pinned.st_dev or info.st_ino == pinned.st_ino
                            or (info.st_mode,info.st_uid,info.st_gid)!=(pinned.st_mode,pinned.st_uid,pinned.st_gid)):
                        continue
                    if original not in verified:
                        with original.open('rb') as stream:
                            if hashlib.file_digest(stream, 'sha256').hexdigest() != original.name:
                                raise ValueError('Registered original source checksum changed')
                        verified[original] = _file_signature(pinned)
                    elif verified[original] != _file_signature(pinned):
                        raise ValueError('Source changed during cleanup')
                    with path.open('rb') as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if (_file_signature(path.lstat()) != _file_signature(info)
                            or _file_signature(original.lstat()) != _file_signature(pinned)):
                        raise ValueError('Source changed during cleanup')
                    if digest != original.name:
                        continue
                    report['source_links'].append({'path': str(path.relative_to(root)), 'sha256': original.name})
                    if execute:
                        updated = _replace_verified_link(root, original, path, pinned, info)
                        verified[original] = _file_signature(updated)
                    break
    # Immutable preview bytes and canonical Parquet indices can also be shared
    # across versions. Keep every path and every byte; mutable metadata and
    # operational databases are deliberately excluded.
    sizes={}
    for base in (work/'packs',work/'prepared',work/'snapshots',work/'compact-media'):
        if not base.is_dir() or base.is_symlink():continue
        for directory,children,files in os.walk(base,followlinks=False):
            children[:]=[name for name in children if not (Path(directory)/name).is_symlink()]
            for name in files:
                path=Path(directory)/name;relative=path.relative_to(base)
                parts=relative.parts
                eligible=(base.name=='compact-media' and 'objects' in parts and bool(re.fullmatch('[a-f0-9]{64}',name))
                    or base.name in {'packs','prepared'} and 'media' in parts
                    or base.name in {'prepared','snapshots'} and name=='records.parquet')
                if not eligible or path.is_symlink():continue
                info=path.stat()
                if stat.S_ISREG(info.st_mode) and info.st_size>=64_000:
                    sizes.setdefault(info.st_size,{}).setdefault((info.st_dev,info.st_ino),(path,info))
    for copies in sizes.values():
        if len(copies)<2:continue
        hashes={}
        for path,info in copies.values():
            with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
            if _file_signature(path.lstat()) != _file_signature(info):
                raise ValueError('Immutable derivative changed during cleanup')
            identity=(info.st_dev,sha,info.st_mode,info.st_uid,info.st_gid)
            previous=hashes.setdefault(identity,(path,info))
            if previous[0]==path:continue
            original,pinned=previous
            report['derivative_links'].append({'path':str(path.relative_to(root)),'retained_path':str(original.relative_to(root)),'sha256':sha})
            if execute:
                current=original.lstat()
                if _file_signature(current) != _file_signature(pinned):
                    raise ValueError('Immutable derivative changed during cleanup')
                updated=_replace_verified_link(root,original,path,pinned,info)
                hashes[identity]=(original,updated)
    after = workspace_usage(root)
    report.update(allocated_before_bytes=before['allocated_bytes'], allocated_after_bytes=after['allocated_bytes'],
                  freed_allocated_bytes=before['allocated_bytes'] - after['allocated_bytes'] if execute else 0,
                  accounting_note=before['measurement_note'])
    return report
