"""Join native image variants by IDs declared in pinned ZIP member names."""
import re
import zipfile

from .structured_collection import StructuredCollectionAdapter


class ArchiveVariantsAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        rows = {}
        self._annotation_bytes_fetched = 0
        budget = getattr(self, '_annotation_transfer_budget', self.config.get('annotation_transfer_bytes', 20_000_000))
        for key, spec in self.config['remote_archives'].items():
            if getattr(self, 'cancel', None):
                self.cancel()
            pattern = re.compile(spec['member_regex'])
            count = 0
            with self._remote(key, budget - self._annotation_bytes_fetched) as source, zipfile.ZipFile(source) as archive:
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    match = pattern.fullmatch(item.filename)
                    if not match:
                        raise ValueError(f'Unexpected native variant archive member: {key}/{item.filename}')
                    native_id = match.group('image_id')
                    identity = spec['split'] + ':' + native_id
                    row = rows.setdefault(identity, {'native_id': native_id, 'split': spec['split'],
                        '_atlas_origin': {'identity': identity, 'split': spec['split'], 'group': spec['split']},
                        '_atlas_media_refs': [], '_atlas_media_conditions': {}, 'native_variants': {}})
                    variant = spec['variant'].format(**match.groupdict())
                    if variant in row['native_variants']:
                        raise ValueError('Duplicate native image variant')
                    ref = f'zip/{key}/{item.filename}'
                    metadata = {'condition': variant, 'source_role': spec['role'], 'downscale_factor': spec.get('downscale_factor'),
                                'native_member': item.filename, 'native_member_bytes': item.file_size, 'zip_crc32': item.CRC}
                    row['native_variants'][variant] = metadata
                    row['_atlas_media_refs'].append(ref)
                    row['_atlas_media_conditions'][ref] = metadata
                    count += 1
                self._annotation_bytes_fetched += source.bytes_fetched
            if count != spec['expected_count']:
                raise ValueError('Native archive population differs from declared count')
        for row in rows.values():
            declared = self.config['expected_variants']
            expected = set(declared[row['split']] if isinstance(declared, dict) else declared)
            if set(row['native_variants']) != expected:
                raise ValueError('Native image has an incomplete set of released variants')
        self._annotation_rows = [rows[key] for key in sorted(rows)]
        return self._annotation_rows
