"""Native UCF101 video identities joined to all three recognition folds."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from .core import MediaHandle, _safe_relative
from .structured_collection import StructuredCollectionAdapter


class UCF101Adapter(StructuredCollectionAdapter):
    def prepare_media(self, plan):
        from .core import DatasetAdapter
        return DatasetAdapter.prepare(self, plan)

    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        path = Path(self.config['recognition_path'])
        if path.stat().st_size > 1_000_000:
            raise ValueError('Recognition annotations exceed one MB')
        tables = {}
        expected = {'classInd.txt', *(f'{kind}list{fold:02d}.txt' for kind in ('train', 'test') for fold in range(1, 4))}
        with zipfile.ZipFile(path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len({item.filename for item in members}) != len(members):
                raise ValueError('Duplicate recognition archive member')
            names = [PurePosixPath(_safe_relative(item.filename)).name for item in members]
            if len(members)!=7 or len(set(names))!=7 or set(names)!=expected or sum(item.file_size for item in members)>3_000_000:
                raise ValueError('Recognition release must contain seven bounded native tables')
            for item in members:
                name = PurePosixPath(_safe_relative(item.filename)).name
                if name in tables or item.file_size > 1_000_000:
                    raise ValueError('Duplicate or oversized recognition table')
                data = archive.read(item)
                tables[name] = (data.decode('utf-8-sig').splitlines(), hashlib.sha256(data).hexdigest(), item.filename)
        if set(tables) != expected:
            raise ValueError('Recognition release must contain exactly seven native tables')
        labels = {}
        for line in tables['classInd.txt'][0]:
            values = line.split()
            if len(values) != 2 or not values[0].isdigit() or values[1] in labels:
                raise ValueError('Invalid native class index')
            labels[values[1]] = {'index': int(values[0]), 'native_line': line}
        if len(labels) != self.config.get('expected_classes', 101) or len({x['index'] for x in labels.values()}) != len(labels):
            raise ValueError('Native class population differs from declared count')
        rows = {}
        for fold in range(1, 4):
            fold_ids = set()
            for kind in ('train', 'test'):
                table_name = f'{kind}list{fold:02d}.txt'
                lines, digest, member = tables[table_name]
                for ordinal, line in enumerate(lines):
                    parts = line.split()
                    if len(parts) != (2 if kind == 'train' else 1):
                        raise ValueError('Invalid native recognition split row')
                    native = _safe_relative(parts[0])
                    pieces = native.split('/')
                    if len(pieces) != 2 or pieces[0] not in labels or not pieces[1].endswith('.avi') or native in fold_ids:
                        raise ValueError('Duplicate or invalid recognition identity')
                    if kind == 'train' and parts[1] != str(labels[pieces[0]]['index']):
                        raise ValueError('Native split class disagrees with class index')
                    fold_ids.add(native)
                    row = rows.setdefault(native, {'native_path': native, 'native_class': pieces[0],
                        'native_class_index': labels[pieces[0]]['index'], 'native_class_index_line': labels[pieces[0]]['native_line'],
                        'native_split_rows': [], '_atlas_origin': {'identity': native, 'split': 'all_three_recognition_folds', 'group': 'released_mirror'},
                        '_atlas_media_refs': [f"zip/videos/{self.config['video_prefix']}{native}"]})
                    row[f'split_{fold}'] = kind
                    row['native_split_rows'].append({'member': member, 'row': ordinal, 'native_line': line, 'sha256': digest})
            if len(fold_ids) != self.config.get('expected_count', 13320) or (fold > 1 and fold_ids != set(rows)):
                raise ValueError('Recognition folds have different native populations')
        if any(len(row['native_split_rows']) != 3 for row in rows.values()):
            raise ValueError('Missing native recognition fold')
        self._annotation_rows = [rows[key] for key in sorted(rows)]
        self._annotation_bytes_fetched = 0
        return self._annotation_rows

    def validate_media(self, budget, cancel=None):
        wanted = {row['_atlas_media_refs'][0][len('zip/videos/'):] for row in self._rows()}
        with self._remote('videos', budget) as source, zipfile.ZipFile(source) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len({item.filename for item in members}) != len(members):
                raise ValueError('Duplicate native video member')
            inventory = [[item.filename, item.file_size, item.compress_size, item.CRC, item.compress_type, item.header_offset] for item in members]
            digest = hashlib.sha256(json.dumps(inventory, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            if digest != self.config['directory_members_sha256'] or {item.filename for item in members} != wanted:
                raise ValueError('Native video directory and recognition population differ')
            self._native_zip_metadata = {f'zip/videos/{item.filename}': {'native_member_bytes': item.file_size, 'zip_crc32': item.CRC,
                'browser_render_required': True, 'source_format': 'AVI'} for item in members}
            return {'referenced_videos': len(wanted), 'archives': 1, 'metadata_bytes_fetched': source.bytes_fetched,
                'integrity': 'Pinned mirror revision, size, strong ETag, complete directory SHA-256 and native member CRC; publisher archive equality is unverified.'}

    def iter_records(self, source, cursor=None, limit=None):
        result = super().iter_records(source, cursor, limit)
        for record in result.records:
            for asset in record.assets:
                asset.metadata.update(browser_render_required=True, source_format='AVI')
        return result

    def _image_handle(self, source, data, asset_ref):
        from dataset_atlas.storage.video import verify_avi
        verify_avi(data, decode=False, cancel=getattr(self,'cancel',None))
        source.charge(len(data))
        return MediaHandle(data, 'video/x-msvideo', hashlib.sha256(data).hexdigest(), asset_ref)
