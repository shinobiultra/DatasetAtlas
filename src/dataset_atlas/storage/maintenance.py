"""Conservative workspace cleanup: evict caches and hard-link verified source copies.

Never remove a dataset version, a preview, a model, or an original source. Byte
identical source copies retain all their paths; only redundant inodes disappear.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile

from .usage import workspace_usage


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


def clean_workspace(root, *, execute=False, include_model_test_env=False):
    root = Path(root).resolve()
    work = root / 'work'
    if work.is_symlink():
        raise ValueError('Cleanup requires an Atlas-owned work directory')
    if execute:
        for path in (work/'preparation').glob('*/status.json'):
            if json.loads(path.read_text()).get('status') in {'queued','running'}:
                raise ValueError('Wait for active preparations before cleaning this workspace')
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'executed': execute,
              'temporary_directories': [], 'cache_entries': [], 'source_links': [], 'compressed_copies': [],'derivative_links':[]}
    before = workspace_usage(root)
    # These are isolated installation-test environments, not the application or
    # local model server environments. Keep all verification logs and receipts.
    temporary = [work / 'clean-ci-check']
    if include_model_test_env:
        temporary.append(work / 'model-server/.venv')
    verify = work / 'verify-install'
    if verify.is_dir() and not verify.is_symlink():
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
            with _locked_database(db_path,'range-cache.lock') as db:
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
            with _locked_database(store/'index.sqlite','writer.lock') as db:
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
    verified = set()
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
                    if info.st_dev != pinned.st_dev or info.st_ino == pinned.st_ino:
                        continue
                    if original not in verified:
                        with original.open('rb') as stream:
                            if hashlib.file_digest(stream, 'sha256').hexdigest() != original.name:
                                raise ValueError('Registered original source checksum changed')
                        verified.add(original)
                    with path.open('rb') as stream:
                        if hashlib.file_digest(stream, 'sha256').hexdigest() != original.name:
                            continue
                    def signature(value):
                        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns
                    if signature(path.stat()) != signature(info) or signature(original.stat()) != signature(pinned):
                        raise ValueError('Source changed during cleanup')
                    report['source_links'].append({'path': str(path.relative_to(root)), 'sha256': original.name})
                    if execute:
                        fd, temporary_name = tempfile.mkstemp(prefix='.atlas-link-', dir=path.parent)
                        os.close(fd)
                        temporary_path = Path(temporary_name)
                        try:
                            temporary_path.unlink()
                            os.link(original, temporary_path)
                            os.replace(temporary_path, path)
                        finally:
                            temporary_path.unlink(missing_ok=True)
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
            if (path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns)!=(info.st_ino,info.st_size,info.st_mtime_ns):
                raise ValueError('Immutable derivative changed during cleanup')
            previous=hashes.setdefault((info.st_dev,sha),(path,info))
            if previous[0]==path:continue
            original,pinned=previous
            report['derivative_links'].append({'path':str(path.relative_to(root)),'retained_path':str(original.relative_to(root)),'sha256':sha})
            if execute:
                current=original.stat()
                if (current.st_ino,current.st_size,current.st_mtime_ns)!=(pinned.st_ino,pinned.st_size,pinned.st_mtime_ns):
                    raise ValueError('Immutable derivative changed during cleanup')
                fd,name=tempfile.mkstemp(prefix='.atlas-link-',dir=path.parent);os.close(fd);temporary=Path(name)
                try:
                    temporary.unlink();os.link(original,temporary);os.replace(temporary,path)
                finally:temporary.unlink(missing_ok=True)
    after = workspace_usage(root)
    report.update(allocated_before_bytes=before['allocated_bytes'], allocated_after_bytes=after['allocated_bytes'],
                  freed_allocated_bytes=before['allocated_bytes'] - after['allocated_bytes'] if execute else 0,
                  accounting_note=before['measurement_note'])
    return report
