import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat

import pytest

from dataset_atlas.storage.cache import BoundedCache, CacheIdentity
from dataset_atlas.storage.maintenance import clean_workspace
from dataset_atlas.jobs.coordinator_lock import acquire_coordinator_lock


def test_deduplication_only_preserves_caches_environments_and_derivatives(tmp_path):
    payload = b"original bytes" * 100_000
    digest = hashlib.sha256(payload).hexdigest()
    source = tmp_path / "work/source-objects" / digest
    duplicate = tmp_path / "work/prepared/example/version/sources/native.bin"
    preview = tmp_path / "work/packs/example/media/original.png"
    preview_copy = tmp_path / "work/prepared/example/version/pack/media/original.png"
    for path in (source, duplicate, preview, preview_copy):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    cache = BoundedCache(tmp_path / "work/media-cache/phantom", 3_000_000)
    identity = CacheIdentity("gated-snapshot", "original", "original")
    cache.partial_path(identity).write_bytes(payload)
    cache.commit(identity, cache.partial_path(identity))
    cached = cache.get(identity)
    assert cached is not None

    environments = [tmp_path / "work/clean-ci-check",
                    tmp_path / "work/verify-install/test-venv",
                    tmp_path / "work/model-server/.venv"]
    for directory in environments:
        directory.mkdir(parents=True)
        (directory / "pyvenv.cfg").write_text("home = /python")
    store = tmp_path / "work/compact-media/snapshot"
    (store / "objects").mkdir(parents=True)
    derivative = store / "objects" / ("a" * 64)
    derivative.write_bytes(b"derived bytes")
    with sqlite3.connect(store / "index.sqlite") as db:
        db.execute("CREATE TABLE media (ref TEXT PRIMARY KEY, metadata TEXT NOT NULL)")
        db.execute("INSERT INTO media VALUES (?, ?)", ("derivative", json.dumps({
            "sha256": "a" * 64, "protected_preview": False,
            "representation": "compressed_avif"})))

    plan = clean_workspace(tmp_path, deduplicate_only=True)
    assert plan["deduplicate_only"] is True and not plan["executed"]
    assert duplicate.stat().st_ino != source.stat().st_ino
    assert plan["temporary_directories"] == plan["cache_entries"] == plan["compressed_copies"] == []
    result = clean_workspace(tmp_path, execute=True, deduplicate_only=True,
                             include_model_test_env=True)
    assert result["freed_allocated_bytes"] > 0
    assert duplicate.stat().st_ino == source.stat().st_ino
    assert preview.stat().st_ino == preview_copy.stat().st_ino
    assert all(path.read_bytes() == payload for path in (source, duplicate, preview, preview_copy, cached))
    assert cache.get(identity) == cached and derivative.read_bytes() == b"derived bytes"
    assert all((directory / "pyvenv.cfg").exists() for directory in environments)
    with sqlite3.connect(store / "index.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 1
    second = clean_workspace(tmp_path, execute=True, deduplicate_only=True)
    assert second["source_links"] == second["derivative_links"] == []
    assert second["freed_allocated_bytes"] == 0


def test_deduplication_only_preserves_different_file_modes(tmp_path):
    payload = b"original" * 150_000
    source = tmp_path / "work/source-objects" / hashlib.sha256(payload).hexdigest()
    duplicate = tmp_path / "work/prepared/example/version/sources/native.bin"
    preview = tmp_path / "work/packs/example/media/original.png"
    preview_copy = tmp_path / "work/prepared/example/version/pack/media/original.png"
    for path in (source, duplicate, preview, preview_copy):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    source.chmod(0o444)
    preview.chmod(0o444)
    duplicate.chmod(0o644)
    preview_copy.chmod(0o644)

    clean_workspace(tmp_path, execute=True, deduplicate_only=True)
    assert source.stat().st_ino != duplicate.stat().st_ino
    assert preview.stat().st_ino != preview_copy.stat().st_ino
    assert [stat.S_IMODE(path.stat().st_mode) for path in (source, duplicate, preview, preview_copy)] == [0o444, 0o644, 0o444, 0o644]


@pytest.mark.parametrize("status", ["running", "queued"])
def test_deduplication_only_refuses_active_preparations(tmp_path, status):
    path = tmp_path / "work/preparation/pending/status.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"status": status}))
    with pytest.raises(ValueError, match="active preparations"):
        clean_workspace(tmp_path, execute=True, deduplicate_only=True)


@pytest.mark.parametrize("kind", ["cache", "compact"])
def test_deduplication_only_refuses_locked_stores(tmp_path, kind):
    if kind == "cache":
        cache = BoundedCache(tmp_path / "work/media-cache/phantom", 1_000)
        lock_path = cache.root / "range-cache.lock"
    else:
        store = tmp_path / "work/compact-media/snapshot"
        store.mkdir(parents=True)
        with sqlite3.connect(store / "index.sqlite") as db:
            db.execute("CREATE TABLE media (ref TEXT PRIMARY KEY, metadata TEXT NOT NULL)")
        lock_path = store / "writer.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with pytest.raises(ValueError, match="being read or written"):
            clean_workspace(tmp_path, execute=True, deduplicate_only=True)


def test_deduplication_only_never_follows_external_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    payload = b"external original" * 10_000
    external = outside / "original.png"
    external.write_bytes(payload)
    media = tmp_path / "work/packs/example/media"
    media.mkdir(parents=True)
    linked = media / "external.png"
    linked.symlink_to(external)
    local = media / "local.png"
    local.write_bytes(payload)
    clean_workspace(tmp_path, execute=True, deduplicate_only=True)
    assert linked.is_symlink() and external.stat().st_ino != local.stat().st_ino
    assert external.read_bytes() == local.read_bytes() == payload


def test_deduplication_only_refuses_a_symlinked_work_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "work").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="Atlas-owned"):
        clean_workspace(tmp_path, execute=True, deduplicate_only=True)


def test_deduplication_only_refuses_a_live_coordinator(tmp_path):
    with acquire_coordinator_lock(tmp_path / "work"):
        with pytest.raises(ValueError, match="coordinating"):
            clean_workspace(tmp_path, execute=True, deduplicate_only=True)


@pytest.mark.parametrize("name", ["storage-admission.lock", "writer-0.lock", "writer-1.lock", "source-transfer.lock"])
def test_deduplication_only_refuses_a_preparation_writer_lease(tmp_path, name):
    directory = tmp_path / "work/preparation"
    directory.mkdir(parents=True)
    with (directory / name).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with pytest.raises(ValueError, match="being read or written"):
            clean_workspace(tmp_path, execute=True, deduplicate_only=True)


@pytest.mark.parametrize("kind", ["source", "derivative"])
def test_deduplication_only_refuses_metadata_changed_while_hashing(tmp_path, monkeypatch, kind):
    from dataset_atlas.storage import maintenance
    payload = b"original" * 150_000
    if kind == "source":
        original = tmp_path / "work/source-objects" / hashlib.sha256(payload).hexdigest()
        duplicate = tmp_path / "work/prepared/example/version/sources/native.bin"
    else:
        original = tmp_path / "work/packs/example/media/original.png"
        duplicate = tmp_path / "work/prepared/example/version/pack/media/original.png"
    for path in (original, duplicate):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    digest = hashlib.file_digest

    def hash_then_change_mode(stream, algorithm):
        result = digest(stream, algorithm)
        if stream.name == str(duplicate):
            duplicate.chmod(0o444)
        return result

    monkeypatch.setattr(maintenance.hashlib, "file_digest", hash_then_change_mode)
    with pytest.raises(ValueError, match="changed during cleanup"):
        clean_workspace(tmp_path, execute=True, deduplicate_only=True)
    assert original.stat().st_ino != duplicate.stat().st_ino


@pytest.mark.parametrize("kind", ["source", "derivative"])
@pytest.mark.parametrize("substitution", ["symlink", "regular"])
@pytest.mark.parametrize("deduplicate_only", [False, True])
def test_cleanup_refuses_source_swapped_at_hardlink_boundary(tmp_path, monkeypatch, kind, substitution, deduplicate_only):
    from dataset_atlas.storage import maintenance
    payload = b"verified original" * 100_000
    if kind == "source":
        original = tmp_path / "work/source-objects" / hashlib.sha256(payload).hexdigest()
        duplicate = tmp_path / "work/prepared/example/version/sources/native.bin"
    else:
        original = tmp_path / "work/packs/example/media/original.png"
        duplicate = tmp_path / "work/prepared/example/version/pack/media/original.png"
    for path in (original, duplicate):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    outside = tmp_path / "unverified.bin"
    outside.write_bytes(b"unverified bytes!" * 100_000)
    duplicate_inode = duplicate.stat().st_ino
    real_link = os.link
    swapped = False

    def swap_then_link(source, target, **kwargs):
        nonlocal swapped
        if not swapped and Path(source).name == original.name:
            swapped = True
            original.unlink()
            if substitution == "symlink":
                original.symlink_to(outside)
            else:
                original.write_bytes(outside.read_bytes())
        return real_link(source, target, **kwargs)

    monkeypatch.setattr(maintenance.os, "link", swap_then_link)
    with pytest.raises(ValueError, match="changed during cleanup"):
        clean_workspace(tmp_path, execute=True, deduplicate_only=deduplicate_only)
    assert swapped
    assert not duplicate.is_symlink() and duplicate.stat().st_ino == duplicate_inode
    assert duplicate.read_bytes() == payload
    assert outside.read_bytes() == b"unverified bytes!" * 100_000
    assert not list(duplicate.parent.glob(".atlas-link-*"))


@pytest.mark.parametrize("which_parent", ["source", "destination"])
def test_cleanup_refuses_parent_swapped_at_hardlink_boundary(tmp_path, monkeypatch, which_parent):
    from dataset_atlas.storage import maintenance
    payload = b"verified original" * 10_000
    original = tmp_path / "work/packs/example/media/original.png"
    duplicate = tmp_path / "work/prepared/example/version/pack/media/original.png"
    for path in (original, duplicate):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_original = outside / "original.png"
    outside_original.write_bytes(b"outside bytes")
    swapped_parent = original.parent if which_parent == "source" else duplicate.parent
    moved_parent = swapped_parent.with_name("retained-media")
    real_link = os.link
    swapped = False

    def swap_parent_then_link(source, target, **kwargs):
        nonlocal swapped
        if not swapped:
            swapped = True
            swapped_parent.rename(moved_parent)
            swapped_parent.symlink_to(outside, target_is_directory=True)
        return real_link(source, target, **kwargs)

    monkeypatch.setattr(maintenance.os, "link", swap_parent_then_link)
    with pytest.raises(ValueError, match="changed during cleanup"):
        clean_workspace(tmp_path, execute=True, deduplicate_only=True)
    assert swapped and outside_original.read_bytes() == b"outside bytes"
    protected_duplicate = moved_parent / duplicate.name if which_parent == "destination" else duplicate
    assert protected_duplicate.read_bytes() == payload and not protected_duplicate.is_symlink()
    assert not list(moved_parent.glob(".atlas-link-*"))
    assert not list(outside.glob(".atlas-link-*"))


@pytest.mark.parametrize("kind", ["source", "derivative"])
def test_cleanup_restores_verified_target_after_source_write_at_replace_boundary(tmp_path, monkeypatch, kind):
    from dataset_atlas.storage import maintenance
    payload = b"verified original" * 100_000
    if kind == "source":
        original = tmp_path / "work/source-objects" / hashlib.sha256(payload).hexdigest()
        duplicate = tmp_path / "work/prepared/example/version/sources/native.bin"
    else:
        original = tmp_path / "work/packs/example/media/original.png"
        duplicate = tmp_path / "work/prepared/example/version/pack/media/original.png"
    for path in (original, duplicate):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    duplicate_inode = duplicate.stat().st_ino
    real_replace = os.replace
    changed = False

    def write_then_replace(source, target, **kwargs):
        nonlocal changed
        if not changed:
            changed = True
            original.write_bytes(b"unverified bytes!" * 100_000)
        return real_replace(source, target, **kwargs)

    monkeypatch.setattr(maintenance.os, "replace", write_then_replace)
    with pytest.raises(ValueError, match="changed during cleanup"):
        clean_workspace(tmp_path, execute=True, deduplicate_only=True)
    assert changed and duplicate.stat().st_ino == duplicate_inode
    assert not duplicate.is_symlink() and duplicate.read_bytes() == payload
    assert not list(duplicate.parent.glob(".atlas-link-*"))
