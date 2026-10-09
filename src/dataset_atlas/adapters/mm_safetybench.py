"""Native MM-SafetyBench question variants and source-only image groups."""
import json
from pathlib import Path
import re
import zipfile

from .structured_collection import StructuredCollectionAdapter


class MMSafetyBenchAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        rows = {}
        consumed = 0
        for spec in self.config['annotations']:
            path = Path(self.config[spec['path_key']])
            consumed += path.stat().st_size
            if consumed > self.config.get('max_annotation_bytes', 20_000_000):
                raise ValueError('MM-SafetyBench annotations exceed byte budget')
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict):
                raise ValueError('MM-SafetyBench annotations must be keyed objects')
            for key, value in data.items():
                if not key.isdigit() or not isinstance(value, dict):
                    raise ValueError('Invalid MM-SafetyBench question identity')
                if any(k.startswith('_atlas_') for k in value):
                    raise ValueError('Reserved annotation key')
                if any(not isinstance(value.get(k), str) for k in ['Question', 'Rephrased Question', 'Rephrased Question(SD)']):
                    raise ValueError('MM-SafetyBench question variant is absent or not text')
                identity = spec['scenario'] + ':' + key
                if identity in rows:
                    raise ValueError('Duplicate MM-SafetyBench question')
                rows[identity] = {**value, 'native_id': key, 'scenario': spec['scenario'],
                                  'annotation_status': 'released',
                                  'native_annotation_file': spec['source_name'],
                                  '_atlas_media_refs': [], '_atlas_media_conditions': {},
                                  '_atlas_origin': {'identity': identity, 'group': spec['scenario'], 'split': 'native'}}
        variants = {'SD': 'Rephrased Question(SD)', 'SD_TYPO': 'Rephrased Question', 'TYPO': 'Rephrased Question'}
        with zipfile.ZipFile(self.config['images_path']) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                match = re.fullmatch(r'MM-SafetyBench\(imgs\)/([^/]+)/(SD|SD_TYPO|TYPO)/(\d+)\.jpg', info.filename)
                if not match:
                    raise ValueError('Unexpected MM-SafetyBench image member')
                scenario, variant, key = match.groups()
                if scenario not in {spec['scenario'] for spec in self.config['annotations']}:
                    raise ValueError('Unknown MM-SafetyBench scenario')
                identity = scenario + ':' + key
                if identity not in rows:
                    rows[identity] = {'native_id': key, 'scenario': scenario, 'annotation_status': 'not_released',
                                      '_atlas_media_refs': [], '_atlas_media_conditions': {},
                                      '_atlas_origin': {'identity': identity, 'group': scenario, 'split': 'native'}}
                row = rows[identity]
                ref = 'zip/images/' + info.filename
                if ref in row['_atlas_media_refs']:
                    raise ValueError('Duplicate MM-SafetyBench image member')
                field = variants[variant]
                row['_atlas_media_refs'].append(ref)
                row['_atlas_media_conditions'][ref] = {'condition': variant, 'question_source_field': field,
                                                       'question': row.get(field), 'annotation_status': row['annotation_status']}
        for row in rows.values():
            present = {v['condition'] for v in row['_atlas_media_conditions'].values()}
            if present != set(variants):
                raise ValueError('MM-SafetyBench question has incomplete image variants')
            row['_atlas_media_refs'].sort(key=lambda ref: list(variants).index(row['_atlas_media_conditions'][ref]['condition']))
        self._annotation_rows = [rows[k] for k in sorted(rows)]
        return self._annotation_rows
