"""Native BAPPS human patch judgements with explicit reference/p0/p1 roles."""
from __future__ import annotations

import io
from pathlib import Path
import re
import zipfile

import numpy as np

from .structured_collection import StructuredCollectionAdapter


class PerceptualAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        rows = []
        consumed = 0
        for key, spec in self.config['local_archives'].items():
            task = spec['task']
            if task not in {'2afc', 'jnd'}:
                raise ValueError('Unsupported perceptual judgement protocol')
            annotation_folder = 'judge' if task == '2afc' else 'same'
            roles = ['ref', 'p0', 'p1'] if task == '2afc' else ['p0', 'p1']
            with zipfile.ZipFile(self.config[spec['path_key']]) as archive:
                entries = {item.filename: item for item in archive.infolist() if not item.is_dir()}
                used = set()
                for name in sorted(entries):
                    match = re.fullmatch(r'(.+)/' + annotation_folder + r'/([^/]+)\.npy', name)
                    if not match:
                        continue
                    if len(rows) % 256 == 0 and getattr(self, 'cancel', None):
                        self.cancel()
                    group, identity = match.groups()
                    parts = group.split('/')
                    if parts[-2] not in {'train', 'val'}:
                        raise ValueError('Unknown native BAPPS partition')
                    info = entries[name]
                    consumed += info.file_size
                    if info.file_size > 4096 or consumed > self.config.get('max_annotation_bytes', 100_000_000):
                        raise ValueError('Perceptual judgement exceeds annotation byte budget')
                    value = np.load(io.BytesIO(archive.read(info)), allow_pickle=False)
                    if not isinstance(value, np.ndarray) or value.size != 1 or value.dtype.kind not in 'biuf':
                        raise ValueError('Perceptual judgement must be a numeric scalar array')
                    judgement = float(value.reshape(-1)[0])
                    if not np.isfinite(judgement) or not 0 <= judgement <= 1:
                        raise ValueError('Perceptual judgement outside [0,1]')
                    refs = []
                    role_map = {}
                    for role in roles:
                        member = f'{group}/{role}/{identity}.png'
                        if member not in entries:
                            raise ValueError('Perceptual judgement has a missing patch counterpart')
                        ref = f'zip/{key}/{member}'
                        refs.append(ref)
                        role_map[ref] = role
                        used.add(member)
                    rows.append({'native_id': identity, 'protocol': task, 'split': parts[-2], 'distortion': parts[-1],
                                 'judgement': judgement, 'native_judgement_shape': list(value.shape),
                                 'native_judgement_dtype': str(value.dtype), 'native_annotation_member': name,
                                 'judgement_meaning': 'Human preference for p1 over p0 relative to ref' if task == '2afc' else 'Human judgement that p0 and p1 are the same',
                                 '_atlas_origin': {'identity': f'{task}:{group}:{identity}', 'group': f'{task}/{group}', 'split': parts[-2]},
                                 '_atlas_media_roles': role_map, '_atlas_media_refs': refs})
                images = {name for name in entries if re.fullmatch(r'.+/(ref|p0|p1)/[^/]+\.png', name)}
                if images != used:
                    raise ValueError('Perceptual source contains unjoined patch images')
                if not used:
                    raise ValueError('No native perceptual judgements found')
        self._annotation_rows = rows
        return rows

    def iter_records(self, source, cursor=None, limit=None):
        batch = super().iter_records(source, cursor, limit)
        for record in batch.records:
            for asset in record.assets:
                asset.metadata['source_role'] = record.source['_atlas_media_roles'][asset.uri]
        return batch
