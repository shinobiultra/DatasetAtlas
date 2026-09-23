"""NRC-VAD native versions, translations and redundant score exports."""
import csv
import io
import math
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile

from .structured_collection import StructuredCollectionAdapter


class NRCVADAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        rows = []
        consumed = 0
        self.table_counts = {}
        dimensions = ['valence', 'arousal', 'dominance']
        for spec in self.config['annotations']:
            version = spec['version']
            root = spec['prefix']
            with zipfile.ZipFile(self.config[spec['path_key']]) as archive:
                def table(name, headers=None):
                    nonlocal consumed
                    info = archive.getinfo(name)
                    consumed += info.file_size
                    if consumed > self.config.get('max_annotation_bytes', 200_000_000):
                        raise ValueError('NRC-VAD annotation byte budget exceeded')
                    values = list(csv.reader(io.StringIO(archive.read(info).decode('utf-8-sig')), delimiter='\t', quoting=csv.QUOTE_NONE))
                    if headers is None:
                        headers = values.pop(0)
                    if len(set(headers)) != len(headers) or any(len(value) != len(headers) for value in values):
                        raise ValueError('NRC-VAD table headers or row widths differ')
                    self.table_counts[version + ':' + name] = len(values)
                    return [dict(zip(headers, value)) for value in values]

                main = root + spec['main_member']
                data = table(main, ['term', *dimensions] if version == '1' else None)
                by_term: dict[str, dict[str, Any]] = {}
                for ordinal, item in enumerate(data, 1):
                    term = item['term']
                    if term in by_term:
                        raise ValueError('Duplicate NRC-VAD term in native main table')
                    scores = {key: float(item[key]) for key in dimensions}
                    low = 0 if version == '1' else -1
                    if any(not math.isfinite(value) or not low <= value <= 1 for value in scores.values()):
                        raise ValueError('NRC-VAD score outside its version-specific scale')
                    by_term[term] = {'term': term, 'lexicon_version': version, **scores, 'score_scale': [low, 1],
                        'source_attribution': 'NRC Valence, Arousal, and Dominance Lexicon, created by Saif M. Mohammad at the National Research Council Canada.',
                        'translations': {}, 'native_exports': {spec['main_member']: {'row_1based': ordinal, 'fields': item}},
                        '_atlas_origin': {'identity': version + ':' + term, 'group': version, 'split': version},
                        '_atlas_media_refs': []}
                for info in archive.infolist():
                    name = info.filename
                    if not name.startswith(root) or not name.endswith('.txt') or name == main:
                        continue
                    relative = name[len(root):]
                    if relative in {'README.txt', 'ListOfLanguages-For-Which-Lexicon-Availabale.txt'}:
                        continue
                    cancel = getattr(self, 'cancel', None)
                    if cancel:
                        cancel()
                    headers = None
                    if version == '1' and 'OneFilePerLanguage/' not in relative and relative != 'NRC-VAD-Lexicon-ForVariousLanguages.txt':
                        dimension = PurePosixPath(relative).name.split('-')[0]
                        headers = ['term', dimension] if dimension in dimensions else ['term', *dimensions]
                    exported = table(name, headers)
                    seen = set()
                    for ordinal, item in enumerate(exported, 1):
                        term = item.get('term', item.get('English Word'))
                        if term not in by_term or term in seen:
                            raise ValueError('NRC-VAD export has duplicate or unmatched terms')
                        seen.add(term)
                        row = by_term[term]
                        row['native_exports'][relative] = {'row_1based': ordinal, 'fields': item}
                        if relative == 'NRC-VAD-Lexicon-ForVariousLanguages.txt':
                            row['translations'] = {key: value for key, value in item.items() if key not in ['English Word', 'Valence', 'Arousal', 'Dominance']}
                        # Preserve native values even when a path says BipolarScale
                        # but its polar-subset table actually contains unipolar scores.
                        for field, value in item.items():
                            dimension = field.lower()
                            if dimension in dimensions:
                                number = float(value)
                                if not math.isfinite(number) or not -1 <= number <= 1:
                                    raise ValueError('Invalid NRC-VAD exported score')
                                expected = row[dimension]
                                if abs(number - expected) > 1e-8 and not (version == '1' and abs(number - (2 * expected - 1)) <= 1e-8):
                                    row.setdefault('native_score_disagreements', []).append({'member': relative, 'dimension': dimension, 'main': expected, 'export': number})
                if version == '1' and any(not row['translations'] for row in by_term.values()):
                    raise ValueError('NRC-VAD translation table does not cover all native terms')
                rows.extend(by_term.values())
        self._annotation_rows = rows
        return rows
