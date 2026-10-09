import hashlib
import os
import json
import sqlite3
import pytest

from dataset_atlas.storage.cache import BoundedCache, CacheIdentity
from dataset_atlas.storage.maintenance import clean_workspace, evict_idle_media_caches


def test_cleanup_keeps_pinned_media_and_sources_and_deduplicates_exact_bytes(tmp_path):
    payload = b'original' * 150_000
    sha = hashlib.sha256(payload).hexdigest()
    original = tmp_path / 'work/source-objects' / sha
    original.parent.mkdir(parents=True)
    original.write_bytes(payload)
    duplicate = tmp_path / 'work/prepared/data/version/sources/native.bin'
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(payload)
    distinct = duplicate.with_name('different.bin')
    distinct.write_bytes(b'x' * len(payload))
    cache = BoundedCache(tmp_path / 'work/media-cache/decoded', 3_000_000)
    for key, pin in [('preview', True), ('disposable', False)]:
        identity = CacheIdentity('release', key, 'original')
        cache.partial_path(identity).write_bytes(payload)
        cache.commit(identity, cache.partial_path(identity))
        cache.pin(identity, pin)
    temporary = tmp_path / 'work/verify-install/test-venv'
    temporary.mkdir(parents=True)
    (temporary / 'pyvenv.cfg').write_text('home = /python')
    receipt = temporary.parent / 'verification.json'
    receipt.write_text('{"passed": true}')
    model_env = tmp_path / 'work/model-server/.venv'
    model_env.mkdir(parents=True)
    (model_env / 'pyvenv.cfg').write_text('home = /python')
    outside = tmp_path.parent / (tmp_path.name + '-external')
    outside.mkdir()
    (outside / 'original.bin').write_bytes(payload)
    os.symlink(outside, tmp_path / 'work/sources')
    plan = clean_workspace(tmp_path)
    assert not plan['executed'] and temporary.exists()
    assert duplicate.stat().st_ino != original.stat().st_ino and cache.usage()['entries'] == 2
    result = clean_workspace(tmp_path, execute=True)
    assert result['freed_allocated_bytes'] > 0
    assert duplicate.read_bytes() == payload and duplicate.stat().st_ino == original.stat().st_ino
    assert distinct.read_bytes() == b'x' * len(payload)
    assert cache.get(CacheIdentity('release', 'preview', 'original')) is not None
    assert cache.get(CacheIdentity('release', 'disposable', 'original')) is None
    assert model_env.exists() and receipt.exists() and not temporary.exists()
    assert (outside / 'original.bin').stat().st_ino != original.stat().st_ino


def test_compressed_copies_can_be_removed_without_touching_preview_originals(tmp_path):
    store=tmp_path/'work/compact-media/snapshot'
    (store/'objects').mkdir(parents=True)
    pinned='a'*64; compressed='b'*64
    for digest in (pinned,compressed):(store/'objects'/digest).write_bytes(b'media')
    with sqlite3.connect(store/'index.sqlite') as db:
        db.execute('CREATE TABLE media (ref TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
        for ref,sha,protected,representation in [('preview',pinned,True,'original'),('alias',pinned,False,'compressed_avif'),('derived',compressed,False,'compressed_avif')]:
            db.execute('INSERT INTO media VALUES (?,?)',(ref,json.dumps(dict(sha256=sha,protected_preview=protected,representation=representation))))
    env=tmp_path/'work/model-server/.venv';env.mkdir(parents=True)
    (env/'pyvenv.cfg').write_text('home = /python')
    clean_workspace(tmp_path,execute=True)
    assert env.exists() and (store/'objects'/pinned).exists() and not (store/'objects'/compressed).exists()
    with sqlite3.connect(store/'index.sqlite') as db:assert db.execute('SELECT ref FROM media').fetchall()==[('preview',)]
    clean_workspace(tmp_path,execute=True,include_model_test_env=True)
    assert not env.exists()


def test_cleanup_refuses_an_active_preparation_and_a_locked_store(tmp_path):
    import fcntl
    status=tmp_path/'work/preparation/pending/status.json'
    status.parent.mkdir(parents=True)
    status.write_text('{"status":"running"}')
    with pytest.raises(ValueError,match='active preparations'):
        clean_workspace(tmp_path,execute=True)
    status.write_text('{"status":"completed"}')
    cache=BoundedCache(tmp_path/'work/media-cache/ranges',1000)
    with (cache.root/'range-cache.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with pytest.raises(ValueError,match='being read or written'):
            clean_workspace(tmp_path,execute=True)


def test_cleanup_shares_identical_immutable_preview_bytes_and_indices(tmp_path):
    payload=b'original preview'*10000
    paths=[tmp_path/'work/packs/example/media/original.png',
           tmp_path/'work/prepared/example/version/pack/media/original.png',
           tmp_path/'work/snapshots/example/records.parquet',
           tmp_path/'work/prepared/example/version/snapshot/records.parquet']
    for path in paths:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
    mutable=paths[1].parents[1]/'dataset.json';mutable.write_bytes(payload)
    plan=clean_workspace(tmp_path)
    assert len(plan['derivative_links'])==3 and len({p.stat().st_ino for p in paths})==4
    clean_workspace(tmp_path,execute=True)
    assert len({p.stat().st_ino for p in paths})==1 and all(p.read_bytes()==payload for p in paths)
    assert mutable.stat().st_ino!=paths[0].stat().st_ino


def test_idle_cleanup_preserves_active_namespaces_and_pinned_originals(tmp_path):
    identities = {}
    for name in ('active', 'idle'):
        cache = BoundedCache(tmp_path / 'work/media-cache' / name, 100_000)
        identities[name] = cache
        for key, pinned in [('preview', True), ('temporary', False)]:
            identity = CacheIdentity('fixture', key, 'original')
            cache.partial_path(identity).write_bytes(b'fixture original')
            cache.commit(identity, cache.partial_path(identity)); cache.pin(identity, pinned)
    directory = tmp_path / 'work/preparation/fixture'; directory.mkdir(parents=True)
    (directory / 'status.json').write_text('{"status":"running"}')
    (directory / 'plan.json').write_text(json.dumps({'dataset': {'adapter_config': {
        'remote_cache_root': 'work/media-cache/active'}}}))
    plan = evict_idle_media_caches(tmp_path)
    assert len(plan['cache_entries']) == 1 and identities['idle'].usage()['entries'] == 2
    proof = evict_idle_media_caches(tmp_path, execute=True)
    assert proof['active_cache_namespaces_preserved'] == ['work/media-cache/active']
    assert identities['active'].usage()['entries'] == 2
    assert identities['idle'].get(CacheIdentity('fixture', 'preview', 'original')) is not None
    assert identities['idle'].get(CacheIdentity('fixture', 'temporary', 'original')) is None


def test_idle_cleanup_cannot_follow_a_work_directory_symlink(tmp_path):
    external = tmp_path / 'external'; external.mkdir()
    (tmp_path / 'work').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='Atlas-owned'):
        evict_idle_media_caches(tmp_path, execute=True)
