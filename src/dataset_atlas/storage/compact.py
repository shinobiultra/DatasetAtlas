"""Full-dimension AVIF browsing copies, isolated from canonical model inputs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path
import sqlite3
import struct
import tempfile
import time

from PIL import Image, features


def encode_image(data, *, protected=False, quality=60, speed=6):
    if type(quality) is not int or not 1 <= quality <= 100 or type(speed) is not int or not 0 <= speed <= 10:
        raise ValueError('Invalid AVIF encoding settings')
    if len(data) > 50_000_000:
        raise ValueError('Image exceeds compressed-input byte budget')
    original_sha = hashlib.sha256(data).hexdigest()
    with Image.open(io.BytesIO(data)) as source:
        mime = Image.MIME.get(source.format, 'application/octet-stream')
        metadata = {'original_sha256': original_sha, 'original_bytes': len(data),
                    'width': source.width, 'height': source.height, 'original_mode': source.mode,
                    'protected_preview': protected, 'orientation_handling': 'native pixels and EXIF orientation retained; no transpose or resize',
                    'pillow_version': Image.__version__}
        reason = ('protected_preview' if protected else 'decoded_pixel_budget_preserved' if source.width * source.height > 50_000_000
                  else 'multiframe_original' if getattr(source, 'n_frames', 1) != 1
                  else 'unsupported_pixel_mode_preserved' if source.mode not in {'RGB', 'RGBA', 'L'} else None)
        if reason:
            return data, mime, {**metadata, 'representation': 'original', 'reason': reason}
        if not features.check('avif'):
            raise ImportError('AVIF encoding requires an AVIF-enabled Pillow build (Pillow >=12 recommended)')
        source.load()
        out = io.BytesIO()
        image = source.convert('RGB') if source.mode == 'L' else source
        settings = {'quality': quality, 'speed': speed, 'subsampling': '4:4:4', 'max_threads': 2}
        for key in ('icc_profile', 'exif'):
            if source.info.get(key):
                if not isinstance(source.info[key], bytes):
                    return data, mime, {**metadata, 'representation': 'original', 'reason': 'unsupported_source_metadata_preserved'}
                settings[key] = source.info[key]
        try:
            image.save(out, format='AVIF', **settings)
        except (TypeError, ValueError, OSError, struct.error, OverflowError) as exc:
            # Some native EXIF entries decode but cannot be serialized by Pillow
            # into AVIF. Keep their bytes instead of stripping research metadata.
            return data, mime, {**metadata, 'representation': 'original',
                               'reason': 'AVIF_encoder_rejected_source_preserved',
                               'encoder_error': f'{type(exc).__name__}: {exc}'}
        payload = out.getvalue()
        with Image.open(io.BytesIO(payload)) as decoded:
            decoded.load()
            if decoded.size != source.size:
                return data, mime, {**metadata, 'representation': 'original', 'reason': 'AVIF_dimension_change_avoided'}
            if decoded.getexif().get(274, 1) != source.getexif().get(274, 1):
                return data, mime, {**metadata, 'representation': 'original', 'reason': 'AVIF_orientation_change_avoided'}
        if len(payload) >= len(data):
            return data, mime, {**metadata, 'representation': 'original', 'reason': 'AVIF_was_not_smaller'}
        return payload, 'image/avif', {**metadata, 'representation': 'compressed_avif',
                'codec': 'AVIF', 'quality': quality, 'speed': speed, 'subsampling': '4:4:4', 'lossy': True}


def store_directory(root, dataset_id, snapshot_id):
    # Neither caller-supplied ID is interpreted as a filesystem path.
    identity = hashlib.sha256(json.dumps([dataset_id, snapshot_id], separators=(',', ':')).encode()).hexdigest()
    return Path(root) / 'work/compact-media' / identity


def compact_entry(root, dataset_id, snapshot_id, asset_ref):
    directory = store_directory(root, dataset_id, snapshot_id)
    path = directory / 'index.sqlite'
    if not path.is_file(): return None
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT metadata FROM media WHERE ref=?', (asset_ref,)).fetchone()
    if row is None: return None
    return json.loads(row[0])


def read_compact(root, dataset_id, snapshot_id, asset_ref, max_bytes):
    entry = compact_entry(root, dataset_id, snapshot_id, asset_ref)
    if entry is None: return None
    digest = entry['sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Invalid compact object identity')
    from .local import SafeRoots
    directory = store_directory(root, dataset_id, snapshot_id)
    with SafeRoots({'compact': directory}).open('compact', 'objects/' + digest) as source:
        if os.fstat(source.fileno()).st_size > max_bytes:
            raise ValueError('Compact media exceeds per-image byte budget')
        data = source.read(max_bytes + 1)
    if len(data) > max_bytes or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Compact media checksum or byte budget mismatch')
    return data, entry['mime'], entry


def compact_dataset(root, dataset_id, *, max_input_bytes, max_output_bytes, quality=60, speed=6, cancel=None, progress=None):
    """Resume bounded conversion. Original archives and canonical records stay intact.

    All media referenced by the current preview is protected, including every
    image variant. Other local images use AVIF only when it actually saves bytes.
    An object is exposed only after a successful decode and atomic write.
    """
    if min(max_input_bytes, max_output_bytes) < 1:
        raise ValueError('Explicit positive compaction input/output budgets are required')
    from dataset_atlas.registry import Registry
    from dataset_atlas.models import Record
    from dataset_atlas.adapters import resolve_dataset_asset
    import pyarrow.parquet as pq
    root = Path(root).resolve(); registry = Registry(root); dataset = registry.dataset(dataset_id)
    snapshot = registry.snapshot_path(dataset_id)
    if snapshot is None: raise ValueError('Compaction requires a complete local metadata index')
    if snapshot.is_dir(): snapshot = snapshot / 'records.parquet'
    preview = registry.pack(dataset_id)
    protected_ids = {a.id for r in preview.records for a in r.assets if a.uri and a.modality == 'image'}
    protected = {a.uri for r in preview.records for a in r.assets if a.uri and a.modality == 'image'}
    # Materialized preview packs can use "media/..." paths while the full index
    # keeps native archive references. Match stable asset identities before the
    # conversion pass, including reused images whose first example differs.
    found = set()
    for batch in pq.ParquetFile(snapshot).iter_batches(columns=['record_json'], batch_size=128):
        if cancel: cancel()
        for value in batch.column(0).to_pylist():
            for asset in json.loads(value)['assets']:
                if asset['id'] in protected_ids and asset.get('uri'):
                    protected.add(asset['uri']); found.add(asset['id'])
    if found != protected_ids:
        raise ValueError('Preview images do not belong to the complete snapshot; refusing unprotected compaction')
    directory = store_directory(root, dataset.id, dataset.snapshot_id)
    directory.mkdir(parents=True, exist_ok=True); (directory / 'objects').mkdir(exist_ok=True)
    import fcntl
    with (directory / 'writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        policy = {'dataset_id': dataset.id, 'snapshot_id': dataset.snapshot_id,
                  'protected_refs_sha256': hashlib.sha256(json.dumps(sorted(protected)).encode()).hexdigest(),
                  'quality': quality, 'speed': speed, 'format': 'atlas-compact-media-v1'}
        policy_path = directory / 'policy.json'
        if policy_path.exists() and json.loads(policy_path.read_text()) != policy:
            raise ValueError('Compaction policy or preview changed; use a new snapshot')
        policy_path.write_text(json.dumps(policy, indent=2) + '\n')
        with sqlite3.connect(directory / 'index.sqlite') as db, ThreadPoolExecutor(max_workers=4) as pool:
            db.execute('CREATE TABLE IF NOT EXISTS media (ref TEXT PRIMARY KEY, metadata TEXT NOT NULL)')
            # SQLite removes repeated images without retaining all IDs in RAM.
            db.execute('CREATE TEMP TABLE seen (ref TEXT PRIMARY KEY)')
            used = sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())
            if used > max_output_bytes:
                raise ValueError('Existing compaction already exceeds the requested output budget')
            read_bytes = 0; added = 0; reused = 0; skipped = 0; pending = []
            def commit_pending():
                nonlocal used, added
                for ref, future in pending:
                    try:
                        data, mime, metadata = future.result()
                    except Exception as exc:
                        raise ValueError(f'Image compaction failed for {ref}: {exc}') from exc
                    digest = hashlib.sha256(data).hexdigest(); target = directory / 'objects' / digest
                    # Reserve space for the SQLite index and provenance before writing.
                    if used + len(data) + 4096 > max_output_bytes:
                        raise ValueError('Compaction output budget exhausted; completed images are reusable')
                    if not target.exists():
                        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                            temporary = Path(stream.name); stream.write(data)
                        try: os.replace(temporary, target)
                        finally: temporary.unlink(missing_ok=True)
                        used += len(data)
                    metadata.update(sha256=digest, bytes=len(data), mime=mime)
                    db.execute('INSERT INTO media VALUES (?,?)', (ref, json.dumps(metadata, separators=(',', ':'))))
                    db.commit(); used += 4096; added += 1
                    if progress and added % 100 == 0: progress({'added': added, 'reused': reused, 'source_bytes_read': read_bytes, 'output_budget_accounted_bytes': used})
                pending.clear()
            for batch in pq.ParquetFile(snapshot).iter_batches(columns=['record_json'], batch_size=64):
                if cancel: cancel()
                for value in batch.column(0).to_pylist():
                    record = Record.model_validate_json(value)
                    for asset in record.assets:
                        ref = asset.uri
                        if asset.modality != 'image' or not ref: skipped += 1; continue
                        if not db.execute('INSERT OR IGNORE INTO seen VALUES (?)', (ref,)).rowcount: continue
                        old = db.execute('SELECT metadata FROM media WHERE ref=?', (ref,)).fetchone()
                        if old:
                            read_compact(root, dataset.id, dataset.snapshot_id, ref, 50_000_000)
                            reused += 1; continue
                        allowance = min(50_000_000, max_input_bytes - read_bytes)
                        if allowance < 1: raise ValueError('Compaction input budget exhausted')
                        candidate = Path(ref)
                        if not candidate.is_absolute(): candidate = root / 'work/packs' / dataset.id / candidate
                        if candidate.is_file():
                            from .local import read_rooted_file
                            data = read_rooted_file(candidate, [p for p in (root / 'work', root / 'examples') if p.is_dir()], allowance)
                        else:
                            data = resolve_dataset_asset(dataset, ref, max_bytes=allowance, workspace_root=root).data
                        read_bytes += len(data)
                        pending.append((ref, pool.submit(encode_image, data, protected=ref in protected, quality=quality, speed=speed)))
                        if len(pending) >= 8: commit_pending()
                commit_pending()
            entries = [json.loads(row[0]) for row in db.execute('SELECT metadata FROM media')]
        report = {**policy, 'status': 'completed', 'assets': len(entries), 'reused_assets': reused,
                  'protected_preview_assets': sum(e['protected_preview'] for e in entries),
                  'compressed_assets': sum(e['representation'] == 'compressed_avif' for e in entries),
                  'original_media_bytes': sum(e['original_bytes'] for e in entries),
                  'stored_media_bytes': sum(e['bytes'] for e in entries), 'source_bytes_read_this_run': read_bytes,
                  'skipped_nonimage_or_absent_references': skipped, 'completed_at_unix': time.time(),
                  'originals_removed': False, 'note': 'Browsing derivatives only. Original-source eviction requires separate verified on-demand retrieval.'}
        (directory / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
