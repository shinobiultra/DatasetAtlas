"""Native COCO question overlays; preserve source annotations and validate every join."""
from __future__ import annotations
import json
from pathlib import Path
import zipfile
from .structured_collection import StructuredCollectionAdapter
from .core import _safe_relative, SourceDescription


class CocoQuestionsAdapter(StructuredCollectionAdapter):
    def probe(self):
        keys = {entry[key] for entry in self.config['annotations'] for key in ('path_key', 'questions_path_key', 'answers_path_key') if key in entry}
        paths = [Path(self.config[key]) for key in keys]
        return SourceDescription('coco_questions', str(paths[0]) if paths else '', bool(paths) and all(p.is_file() for p in paths), self.revision,
                                 sum(p.stat().st_size for p in paths if p.is_file()), False, True, True, True, True, ())

    def _read_member(self, path_key, member):
        with zipfile.ZipFile(self.config[path_key]) as archive:
            info = archive.getinfo(_safe_relative(member))
            self._annotation_size += info.file_size
            if self._annotation_size > self.config.get('max_annotation_bytes', 1_500_000_000):
                raise ValueError('Annotations exceed declared read budget')
            return archive.read(info).decode('utf-8-sig')

    def _image_lookup(self):
        lookup = {}
        for key in self.config['remote_archives']:
            budget = self.config.get('annotation_transfer_bytes', 30_000_000) - self._annotation_bytes_fetched
            with self._remote(key, budget) as remote, zipfile.ZipFile(remote) as archive:
                for info in archive.infolist():
                    name = info.filename
                    if info.is_dir() or not name.lower().endswith('.jpg'): continue
                    image_id = int(Path(name).stem.rsplit('_', 1)[-1])
                    if image_id in lookup: raise ValueError('Duplicate COCO image ID across archives')
                    lookup[image_id] = f'zip/{key}/{_safe_relative(name)}'
                self._annotation_bytes_fetched += remote.bytes_fetched
        return lookup

    def _rows(self):
        if hasattr(self, '_annotation_rows'): return self._annotation_rows
        self._annotation_size = 0
        self._annotation_bytes_fetched = 0
        lookup = self._image_lookup() if self.config['dataset_kind'] == 'cocoqa' else None
        rows = []
        for entry in self.config['annotations']:
            split = entry['split']
            if self.config['dataset_kind'] == 'cocoqa':
                columns = {name: self._read_member(entry['path_key'], f'{entry["prefix"]}/{filename}.txt').splitlines()
                           for name, filename in [('image_id', 'img_ids'), ('question', 'questions'), ('answer', 'answers'), ('type', 'types')]}
                if len({len(values) for values in columns.values()}) != 1:
                    raise ValueError('COCO-QA line-aligned files have different lengths')
                data = []
                for ordinal in range(len(columns['question'])):
                    row = {key: values[ordinal] for key, values in columns.items()}
                    row['image_id'] = int(row['image_id'])
                    row['type'] = int(row['type'])
                    if row['type'] not in range(4): raise ValueError('Unknown native COCO-QA type')
                    row['type_name'] = ['object', 'number', 'color', 'location'][row['type']]
                    row['question_id'] = ordinal
                    data.append(row)
            else:
                questions = json.loads(self._read_member(entry['questions_path_key'], entry['questions_member']))['questions']
                annotations = json.loads(self._read_member(entry['answers_path_key'], entry['answers_member']))['annotations'] if entry.get('answers_path_key') else []
                by_id = {}
                for answer in annotations:
                    key = answer['question_id']
                    if key in by_id: raise ValueError('Duplicate annotation question ID')
                    by_id[key] = answer
                seen = set(); data = []
                for question in questions:
                    key = question['question_id']
                    if key in seen: raise ValueError('Duplicate input question ID')
                    seen.add(key)
                    answer = by_id.get(key)
                    if entry.get('answers_path_key') and answer is None: raise ValueError('Missing answer annotation')
                    if answer and answer['image_id'] != question['image_id']: raise ValueError('Question/annotation image ID mismatch')
                    data.append({**question, 'input_question': question, **({'annotation': answer} if answer is not None else {})})
                if set(by_id) - seen: raise ValueError('Orphan answer annotation')
            for ordinal, row in enumerate(data):
                image_id = row['image_id']
                if lookup is not None:
                    if image_id not in lookup: raise ValueError(f'Missing COCO image {image_id}')
                    ref = lookup[image_id]
                else:
                    key = entry['media_archive']; prefix = entry['media_prefix']
                    ref = f'zip/{key}/{prefix}/COCO_{prefix}_{image_id:012d}.jpg'
                rows.append({**row, '_atlas_origin': {'split': split, 'row': ordinal,
                             'identity': f'{split}:{row["question_id"]}', 'format': self.config['dataset_kind']},
                             '_atlas_media_refs': [ref]})
        self._annotation_rows = rows
        return rows
