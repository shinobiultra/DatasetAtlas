"""Join native image variants by IDs declared in pinned ZIP member names."""
import re
import zipfile
import hashlib
import json

from .core import DatasetAdapter
from .structured_collection import StructuredCollectionAdapter


class ArchiveVariantsAdapter(StructuredCollectionAdapter):
    def prepare_media(self, approved_plan):
        """Reading one image needs only its own archive.

        `prepare` rebuilds the whole release inventory, opening every remote archive directory (22 for DIV2K); when a publisher moves or
        removes one archive, that would make every media read fail, including images whose archive is intact. Preparation still validates
        the complete inventory; the media path does not repeat it."""
        return DatasetAdapter.prepare(self, approved_plan)

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
                files = [item for item in archive.infolist() if not item.is_dir()]
                if len({item.filename for item in files}) != len(files):
                    raise ValueError('Duplicate native archive member')
                if spec.get('directory_members_sha256'):
                    inventory = [[item.filename, item.file_size, item.compress_size, item.CRC,
                                  item.compress_type, item.header_offset] for item in files]
                    digest = hashlib.sha256(json.dumps(inventory, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                    if digest != spec['directory_members_sha256']:
                        raise ValueError('Native archive directory fingerprint changed')
                prefix = spec.get('selected_prefix')
                ignored = set(spec.get('ignored_members', []))
                observed_ignored = set()
                excluded = 0
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    if prefix and not item.filename.startswith(prefix):
                        excluded += 1
                        continue
                    if item.filename in ignored:
                        observed_ignored.add(item.filename)
                        continue
                    match = pattern.fullmatch(item.filename)
                    if not match:
                        raise ValueError(f'Unexpected native variant archive member: {key}/{item.filename}')
                    native_id = match.group('image_id')
                    identity = spec['split'] + ':' + native_id
                    fields = {name: template.format(**match.groupdict())
                              for name, template in spec.get('source_fields', {}).items()}
                    if any(name.startswith('_') or name in {'native_id', 'split', 'native_variants'} for name in fields):
                        raise ValueError('Archive source field collides with an identity or reserved field')
                    row = rows.setdefault(identity, {'native_id': native_id, 'split': spec['split'],
                        '_atlas_origin': {'identity': identity, 'split': spec['split'], 'group': spec['split']},
                        '_atlas_media_refs': [], '_atlas_media_conditions': {}, 'native_variants': {}, **fields})
                    if any(row.get(name) != value for name, value in fields.items()):
                        raise ValueError('Archive variants disagree on native source fields')
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
                if observed_ignored != ignored:
                    raise ValueError('Declared ignored archive members differ from source')
                if prefix and excluded != spec.get('expected_excluded_members'):
                    raise ValueError('Excluded archive population differs from declared count')
            if count != spec['expected_count']:
                raise ValueError('Native archive population differs from declared count')
        for row in rows.values():
            declared = self.config['expected_variants']
            expected = set(declared[row['split']] if isinstance(declared, dict) else declared)
            if set(row['native_variants']) != expected:
                raise ValueError('Native image has an incomplete set of released variants')
        self._annotation_rows = [rows[key] for key in sorted(rows)]
        return self._annotation_rows
