"""Native file variants joined from a checksummed source inventory."""
import re

from .structured_collection import StructuredCollectionAdapter


class InventoryVariantsAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        pattern = re.compile(self.config['member_regex'])
        rows = {}
        for name, entry in sorted(self._inventory().items()):
            match = pattern.fullmatch(name)
            if not match:
                raise ValueError('Source inventory member does not match the native layout')
            fields = match.groupdict()
            identity = fields['image_id']
            variant = self.config['variant_template'].format(**fields)
            row = rows.setdefault(identity, {'native_id': identity,
                '_atlas_origin': {'identity': identity, 'group': 'native', 'split': 'benchmark'},
                '_atlas_media_refs': [], '_atlas_media_conditions': {}, 'native_variants': {}})
            if variant in row['native_variants']:
                raise ValueError('Duplicate source image variant')
            metadata = {'condition': variant, 'source_role': fields['role'],
                        'downscale_factor': int(fields['scale']), 'source_path': name,
                        'source_note': self.config['variant_note']}
            row['native_variants'][variant] = metadata
            ref = 'file/' + name
            row['_atlas_media_refs'].append(ref)
            row['_atlas_media_conditions'][ref] = metadata
        expected = set(self.config['expected_variants'])
        for row in rows.values():
            if set(row['native_variants']) != expected:
                raise ValueError('Source image has an incomplete variant set')
        self._annotation_rows = list(rows.values())
        return self._annotation_rows
