"""Bounded, revision-aware disposable cache. Originals remain untouched."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class CacheIdentity:
    source_revision: str
    asset_id: str
    representation: str
    transformation: str = ""

    def __post_init__(self) -> None:
        if not self.source_revision or not self.asset_id or not self.representation:
            raise ValueError("Cache identity requires revision, asset ID, and representation")

    @property
    def key(self) -> str:
        value = [self.source_revision, self.asset_id, self.representation, self.transformation]
        return hashlib.sha256(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class BoundedCache:
    def __init__(self, root: str | Path, max_bytes: int):
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        (self.root / "objects").mkdir(exist_ok=True)
        (self.root / "partial").mkdir(exist_ok=True)
        self.db_path = self.root / "cache.sqlite3"
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS entries (
                key TEXT PRIMARY KEY, path TEXT NOT NULL, size INTEGER NOT NULL,
                sha256 TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0,
                last_access REAL NOT NULL, source_revision TEXT NOT NULL,
                asset_id TEXT NOT NULL, representation TEXT NOT NULL,
                transformation TEXT NOT NULL, fingerprint_type TEXT NOT NULL,
                fingerprint TEXT
            )""")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30)
        # Switching a brand-new database to WAL needs exclusive access and ignores the busy timeout, so
        # concurrent first use can fail instantly with "database is locked". Retrying is safe: it is idempotent.
        for attempt in range(40):
            try:
                db.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as error:
                if "locked" not in str(error) or attempt == 39:
                    db.close()
                    raise
                time.sleep(0.05)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def get(self, identity: CacheIdentity) -> Path | None:
        with self._db() as db:
            row = db.execute("SELECT path,size,sha256 FROM entries WHERE key=?", (identity.key,)).fetchone()
            if not row:
                return None
            path = self.root / row[0]
            if not path.is_file() or path.stat().st_size != row[1] or _file_sha256(path) != row[2]:
                db.execute("DELETE FROM entries WHERE key=?", (identity.key,))
                return None
            db.execute("UPDATE entries SET last_access=? WHERE key=?", (time.time(), identity.key))
            return path

    def partial_path(self, identity: CacheIdentity) -> Path:
        return self.root / "partial" / (identity.key + ".part")

    def commit(self, identity: CacheIdentity, source: Path, *, fingerprint_type: str = "none",
               fingerprint: str | None = None, expected_sha256: str | None = None) -> Path:
        if source != self.partial_path(identity) or source.is_symlink():
            raise ValueError("Only this identity's cache partial may be committed")
        size = source.stat().st_size
        if size > self.max_bytes:
            raise ValueError("Asset exceeds cache capacity")
        sha = _file_sha256(source)
        if expected_sha256 and sha.lower() != expected_sha256.lower():
            raise ValueError("Asset checksum mismatch")
        relative = f"objects/{identity.key}"
        destination = self.root / relative
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT path,pinned FROM entries WHERE key=?", (identity.key,)).fetchone()
            if existing and (self.root / existing[0]).exists():
                if _file_sha256(self.root / existing[0]) != sha:
                    raise ValueError("Same cache identity produced different bytes; change source revision")
                source.unlink(missing_ok=True)
                return destination
            total = db.execute("SELECT COALESCE(SUM(size),0) FROM entries").fetchone()[0]
            for old_key, old_path, old_size in db.execute(
                "SELECT key,path,size FROM entries WHERE pinned=0 ORDER BY last_access ASC").fetchall():
                if total + size <= self.max_bytes:
                    break
                (self.root / old_path).unlink(missing_ok=True)
                db.execute("DELETE FROM entries WHERE key=?", (old_key,))
                total -= old_size
            if total + size > self.max_bytes:
                raise ValueError("Pinned cache entries leave insufficient capacity")
            if destination.exists():
                if _file_sha256(destination) != sha:
                    raise ValueError("Existing cache object differs for this identity")
                source.unlink()
            else:
                os.replace(source, destination)
            db.execute("INSERT OR REPLACE INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (identity.key, relative, size, sha, existing[1] if existing else 0, time.time(), identity.source_revision,
                        identity.asset_id, identity.representation, identity.transformation,
                        fingerprint_type, fingerprint))
        return destination

    def pin(self, identity: CacheIdentity, pinned: bool = True) -> None:
        with self._db() as db:
            if not db.execute("SELECT 1 FROM entries WHERE key=?", (identity.key,)).fetchone():
                raise KeyError(identity.key)
            db.execute("UPDATE entries SET pinned=? WHERE key=?", (int(pinned), identity.key))

    def evict(self, identity: CacheIdentity) -> None:
        with self._db() as db:
            row = db.execute("SELECT path,pinned FROM entries WHERE key=?", (identity.key,)).fetchone()
            if not row:
                return
            if row[1]:
                raise ValueError("Pinned entry cannot be evicted")
            (self.root / row[0]).unlink(missing_ok=True)
            db.execute("DELETE FROM entries WHERE key=?", (identity.key,))

    def usage(self) -> dict[str, int]:
        with self._db() as db:
            size, count = db.execute("SELECT COALESCE(SUM(size),0),COUNT(*) FROM entries").fetchone()
        return {"bytes": size, "entries": count, "max_bytes": self.max_bytes}
