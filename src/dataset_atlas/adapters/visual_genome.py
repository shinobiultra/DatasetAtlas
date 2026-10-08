"""Stream native Visual Genome annotation tables into a bounded local join index."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import urlsplit
import zipfile

from .core import DatasetAdapter, RecordBatch, _safe_relative
from .structured_collection import StructuredCollectionAdapter


class VisualGenomeAdapter(StructuredCollectionAdapter):
    def _index_path(self):
        if self.config.get('join_index_path'):
            return Path(self.config['join_index_path'])
        # Older prepared versions already own this derivative. Read it without
        # creating files next to a caller's original annotation archives.
        existing = Path(self.config['image_data_path']).parent / 'visual-genome-join.sqlite'
        if existing.is_file():
            return existing
        raise ValueError('Visual Genome requires an explicit writable join_index_path')

    def _ensure_index(self):
        if hasattr(self, '_index_ready'):
            return
        import fcntl
        path = self._index_path()
        fingerprint = hashlib.sha256(json.dumps({
            'sources': self.config.get('source_files', []),
            'tables': self.config['tables'], 'version': 2,
        }, sort_keys=True).encode()).hexdigest()
        def verify():
            if path.stat().st_size > self.config.get('max_join_bytes', 8_000_000_000):
                raise ValueError('Existing Visual Genome join exceeds disk budget')
            with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
                row = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
                if row != (fingerprint,):
                    raise ValueError('Visual Genome join index does not match pinned sources')
        if path.is_file():
            verify()
            self._index_ready = True
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if path.is_file():
                verify()
            else:
                self._build_index(path, fingerprint)
        self._index_ready = True

    def _build_index(self, path, fingerprint):
        try:
            import ijson
        except ImportError as exc:
            raise ValueError('Visual Genome streaming annotations require dataset-atlas[datasets]') from exc
        maximum = self.config.get('max_join_bytes', 8_000_000_000)
        if type(maximum) is not int or not 4096 <= maximum <= 50_000_000_000:
            raise ValueError('Invalid Visual Genome join byte budget')
        stage = path.with_suffix(f'.{os.getpid()}.tmp')
        consumed = 0
        db = sqlite3.connect(stage)
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA temp_store=FILE')
            db.execute('PRAGMA cache_size=-16384')
            db.execute(f'PRAGMA max_page_count={maximum // 4096}')
            db.executescript('''
                CREATE TABLE images (ordinal INTEGER PRIMARY KEY, id INTEGER UNIQUE NOT NULL, data TEXT NOT NULL);
                CREATE TABLE annotations (image_id INTEGER NOT NULL, field TEXT NOT NULL, data TEXT NOT NULL,
                    ordinal INTEGER NOT NULL, PRIMARY KEY (image_id, field, ordinal)) WITHOUT ROWID;
                CREATE TABLE qas (id INTEGER PRIMARY KEY, image_id INTEGER NOT NULL);
                CREATE TABLE regions (id INTEGER PRIMARY KEY, image_id INTEGER NOT NULL);
                CREATE TABLE orphans (ordinal INTEGER PRIMARY KEY, qa_id INTEGER UNIQUE NOT NULL, region_id INTEGER NOT NULL);
                CREATE TABLE qa_annotations (image_id INTEGER NOT NULL, field TEXT NOT NULL, qa_id INTEGER NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY (image_id, field, qa_id)) WITHOUT ROWID;
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
            stats = {}
            for spec in self.config['tables']:
                file = Path(self.config[spec['path_key']])
                field = spec['field']
                count = 0
                with zipfile.ZipFile(file) as archive:
                    info = archive.getinfo(_safe_relative(spec['member']))
                    consumed += info.file_size
                    if consumed > self.config.get('max_annotation_bytes', 8_000_000_000):
                        raise ValueError('Visual Genome annotations exceed read budget')
                    with archive.open(info) as stream:
                        rows = ijson.kvitems(stream, '', use_float=True) if spec.get('qa_keyed') else ijson.items(stream, 'item', use_float=True)
                        for row in rows:
                            cancel = getattr(self, '_cancel', None)
                            if count % 256 == 0 and callable(cancel):
                                cancel()
                            encoded = json.dumps(row[1] if spec.get('qa_keyed') else row, ensure_ascii=False, separators=(',', ':'))
                            if spec.get('qa_keyed'):
                                qa_id = int(row[0])
                                parent = db.execute('SELECT image_id FROM qas WHERE id=?', (qa_id,)).fetchone()
                                if parent and spec.get('region_mapping'):
                                    region_parent = db.execute('SELECT image_id FROM regions WHERE id=?', (row[1],)).fetchone()
                                    if region_parent and region_parent != parent:
                                        raise ValueError('Visual Genome QA and region mapping refer to different images')
                                if not parent and spec.get('region_mapping'):
                                    parent = db.execute('SELECT image_id FROM regions WHERE id=?', (row[1],)).fetchone()
                                    if not parent:
                                        db.execute('INSERT INTO orphans(qa_id,region_id) VALUES (?,?)', (qa_id, row[1]))
                                        count += 1
                                        continue
                                if not parent:
                                    raise ValueError(f'Unmatched Visual Genome QA ID in {field}: {qa_id}')
                                db.execute('INSERT INTO qa_annotations VALUES (?,?,?,?)', (parent[0], field, qa_id, encoded))
                            else:
                                image_id = row[spec['key']]
                                if type(image_id) is not int:
                                    raise ValueError('Invalid Visual Genome image ID')
                                if field == 'image':
                                    db.execute('INSERT INTO images VALUES (?,?,?)', (count, image_id, encoded))
                                else:
                                    if not db.execute('SELECT 1 FROM images WHERE id=?', (image_id,)).fetchone():
                                        raise ValueError(f'Unmatched Visual Genome image ID in {field}: {image_id}')
                                    db.execute('INSERT INTO annotations VALUES (?,?,?,?)', (image_id, field, encoded, count if spec.get('multiple') else 0))
                                if spec.get('region_list'):
                                    for region in row[spec['region_list']]:
                                        if region['image_id'] != image_id:
                                            raise ValueError('Visual Genome region image ID disagrees with parent')
                                        previous = db.execute('SELECT image_id FROM regions WHERE id=?', (region['region_id'],)).fetchone()
                                        if previous and previous[0] != image_id:
                                            raise ValueError('Ambiguous Visual Genome region ID')
                                        db.execute('INSERT OR IGNORE INTO regions VALUES (?,?)', (region['region_id'], image_id))
                                if spec.get('qa_list'):
                                    for qa in row[spec['qa_list']]:
                                        if qa['image_id'] != image_id:
                                            raise ValueError('Visual Genome QA image ID disagrees with its parent')
                                        db.execute('INSERT INTO qas VALUES (?,?)', (qa['qa_id'], image_id))
                            count += 1
                stats[field] = count
                db.commit()
            db.execute('INSERT INTO metadata VALUES (?,?)', ('fingerprint', fingerprint))
            db.execute('INSERT INTO metadata VALUES (?,?)', ('tables', json.dumps(stats)))
            db.commit()
            db.close()
            if stage.stat().st_size > maximum:
                raise ValueError('Visual Genome join exceeds disk budget')
            stage.replace(path)
        except Exception:
            db.close()
            stage.unlink(missing_ok=True)
            raise

    def prepare(self, approved_plan):
        source = self.prepare_media(approved_plan)
        self._ensure_index()
        return source

    def prepare_media(self, approved_plan):
        """Resolve a canonical native ZIP reference without rebuilding annotations."""
        source = DatasetAdapter.prepare(self, approved_plan)
        if not hasattr(self, '_sources_checked'):
            for item in self.config.get('source_files', []):
                with Path(item['path']).open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                        raise ValueError('Visual Genome annotation checksum changed')
            self._sources_checked = True
        return source

    def validate_media(self, budget, cancel=None):
        self._cancel = cancel
        return super().validate_media(budget, cancel)

    @property
    def derived_sources(self):
        self._ensure_index()
        path = self._index_path()
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest,
                 'representation': 'Lossless disk-backed joins of pinned native JSON tables'}]

    @property
    def count(self):
        self._ensure_index()
        with sqlite3.connect(f'file:{self._index_path()}?mode=ro', uri=True) as db:
            return db.execute('SELECT (SELECT COUNT(*) FROM images)+(SELECT COUNT(*) FROM orphans)').fetchone()[0]

    def _media_ref(self, image):
        member = _safe_relative(urlsplit(image['url']).path.lstrip('/'))
        prefix = self.config['media_path_remove_prefix']
        if not member.startswith(prefix):
            raise ValueError('Visual Genome image URL lacks declared prefix')
        member = _safe_relative(member[len(prefix):])
        key = self.config['media_archive_by_prefix'].get(member.split('/')[0])
        if key not in self.config['remote_archives']:
            raise ValueError('Visual Genome image lacks a configured archive')
        return f'zip/{key}/{member}'

    def _rows(self):
        # Directory validation needs only image metadata, not all annotation payloads.
        self._ensure_index()
        with sqlite3.connect(f'file:{self._index_path()}?mode=ro', uri=True) as db:
            for (data,) in db.execute('SELECT data FROM images ORDER BY ordinal'):
                yield {'_atlas_media_refs': [self._media_ref(json.loads(data))]}

    def source_field_types(self):
        return {'image_id': 'number', '_atlas_identity': 'string', '_atlas_source_status': 'string', 'orphan_qa_to_region_mapping': 'object',
                **{spec['field']: 'array' if spec.get('multiple') else 'object' for spec in self.config['tables']}}

    def iter_records(self, source, cursor=None, limit=None):
        self._ensure_index()
        start = int(cursor or 0)
        if start < 0:
            raise ValueError('Negative cursor')
        size = min(limit or source.limit, source.limit)
        records = []
        self.config['mapping'] = {'id': '_atlas_identity', 'media': '_atlas_media_refs'}
        multiple = {spec['field'] for spec in self.config['tables'] if spec.get('multiple')}
        with sqlite3.connect(f'file:{self._index_path()}?mode=ro', uri=True) as db:
            rows = db.execute('SELECT ordinal,id,data FROM images WHERE ordinal>=? ORDER BY ordinal LIMIT ?', (start, size)).fetchall()
            for ordinal, image_id, data in rows:
                image = json.loads(data)
                row: dict[str, Any] = {'_atlas_identity': f'image:{image_id}', 'image_id': image_id, 'image': image, '_atlas_media_refs': [self._media_ref(image)]}
                for field, encoded in db.execute('SELECT field,data FROM annotations WHERE image_id=? ORDER BY field,ordinal', (image_id,)):
                    if field in multiple:
                        row.setdefault(field, []).append(json.loads(encoded))
                    else:
                        row[field] = json.loads(encoded)
                for field, qa_id, encoded in db.execute('SELECT field,qa_id,data FROM qa_annotations WHERE image_id=?', (image_id,)):
                    row.setdefault(field, {})[str(qa_id)] = json.loads(encoded)
                record = DatasetAdapter._record(self, row, ordinal)
                record.source.pop('_atlas_media_refs', None)
                for asset in record.assets:
                    if not asset.uri:
                        raise ValueError('Visual Genome image lacks a native media reference')
                    asset.metadata.update(width=image['width'], height=image['height'], representation='original ZIP member',
                                          source_etag=self.config['remote_archives'][asset.uri.split('/')[1]]['etag'])
                source.charge(len(record.model_dump_json().encode()))
                records.append(record)
            image_count = db.execute('SELECT COUNT(*) FROM images').fetchone()[0]
            if len(records) < size and start + size > image_count:
                offset = max(0, start - image_count)
                for ordinal, qa_id, region_id in db.execute('SELECT ordinal,qa_id,region_id FROM orphans ORDER BY ordinal LIMIT ? OFFSET ?', (size-len(records), offset)):
                    row = {'_atlas_identity': f'orphan-qa-mapping:{qa_id}',
                           'orphan_qa_to_region_mapping': {str(qa_id): region_id},
                           '_atlas_source_status': 'Native mapping: QA and region IDs absent from released annotation tables'}
                    record = DatasetAdapter._record(self, row, image_count + ordinal - 1)
                    source.charge(len(record.model_dump_json().encode()))
                    records.append(record)
        end = start + len(records)
        return RecordBatch(records, str(end) if end < self.count else None, len(records))
