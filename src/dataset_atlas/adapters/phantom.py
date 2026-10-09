"""Native PHANTOM conversations and behaviours, including release discrepancies."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

from dataset_atlas.models import Asset, stable_id
from .core import _safe_relative
from .structured_collection import StructuredCollectionAdapter


class PhantomAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        used = 0

        def read(key, lines=False):
            nonlocal used
            path = Path(self.config[key])
            used += path.stat().st_size
            if used > self.config.get('max_annotation_bytes', 160_000_000):
                raise ValueError('PHANTOM annotations exceed declared read budget')
            with path.open(encoding='utf-8') as stream:
                return [json.loads(line) for line in stream if line.strip()] if lines else json.load(stream)

        inventory = self._inventory()
        rows = []

        def media(row, paths):
            row['_atlas_media_refs'] = []
            row['_atlas_unavailable_media'] = []
            for name in dict.fromkeys(paths):
                _safe_relative(name)
                if name in inventory:
                    row['_atlas_media_refs'].append('file/' + name)
                else:
                    row['_atlas_unavailable_media'].append(name)

        if self.config.get('population') != 'child_safety_behaviours':
            attacks = {}
            for item in read('phantom_attacks_json'):
                attack = item['attack']
                key = attack['id']
                if key in attacks:
                    raise ValueError('Duplicate PHANTOM conversation ID')
                attacks[key] = attack
            turns = defaultdict(dict)
            for turn in read('metadata_jsonl', lines=True):
                key, step = turn['id'], turn['step']
                if type(step) is not int or step < 1 or step in turns[key]:
                    raise ValueError('Duplicate or invalid PHANTOM turn')
                turns[key][step] = turn
            if set(attacks) - set(turns):
                raise ValueError('PHANTOM conversation has no turn metadata')
            for key, steps in turns.items():
                ordered = [steps[step] for step in sorted(steps)]
                if sorted(steps) != list(range(1, len(steps) + 1)):
                    raise ValueError('PHANTOM conversation has noncontiguous turns')
                attack = attacks.get(key)
                if attack:
                    if set(attack['conversation']) != {str(step) for step in steps}:
                        raise ValueError('PHANTOM conversation and turn IDs differ')
                    for step, turn in steps.items():
                        native = attack['conversation'][str(step)]
                        if native['prompt'] != turn['prompt'] or any(
                            attack[field] != turn[field] for field in
                            ('goal', 'target_model', 'main_category', 'subcategory', 'strategy', 'number_of_steps')
                        ):
                            raise ValueError('PHANTOM conversation and turn content differ')
                first = ordered[0]
                row = {field: first[field] for field in
                       ('id', 'goal', 'target_model', 'main_category', 'subcategory', 'strategy', 'number_of_steps')}
                row.update(native_attack=attack, native_turns=ordered,
                           _atlas_origin={'identity': 'attack:' + key, 'split': 'attacks', 'group': 'attacks'},
                           _atlas_source_status='Both annotation forms' if attack else 'Only released in metadata.jsonl')
                media(row, [turn['file_name'] for turn in ordered])
                rows.append(row)
        behaviours = read('phantom_behaviours_json')
        table = {}
        for item in read('behaviours_jsonl', lines=True):
            if item['id'] in table:
                raise ValueError('Duplicate PHANTOM behaviour ID')
            table[item['id']] = item
        if len({item['id'] for item in behaviours}) != len(behaviours) or {item['id'] for item in behaviours} != set(table):
            raise ValueError('PHANTOM behaviour IDs differ between annotation forms')
        for item in behaviours:
            mirror = table[item['id']]
            if any(item.get(field) != mirror.get(field) for field in set(item) | set(mirror)
                   if field not in {'image_path', 'embedding'}):
                raise ValueError('PHANTOM behaviour content differs between annotation forms')
            mirror_paths = list(dict.fromkeys(mirror['image_path'].split(', '))) if mirror['image_path'] else []
            if mirror_paths != item['image_path']:
                raise ValueError('PHANTOM behaviour image paths differ between annotation forms')
            if self.config.get('population') == 'child_safety_behaviours' and item['benchmark'] != 'PHANTOM':
                continue
            row = {**item, 'native_jsonl': mirror,
                   '_atlas_origin': {'identity': f"behaviour:{item['id']}", 'split': 'behaviours', 'group': 'behaviours'}}
            media(row, item['image_path'])
            rows.append(row)
        self._annotation_rows = rows
        return rows

    def validate_media(self, budget, cancel=None):
        result = super().validate_media(budget, cancel)
        result['absent_media_references'] = len({name for row in self._rows() for name in row['_atlas_unavailable_media']})
        result['records_with_absent_media'] = sum(bool(row['_atlas_unavailable_media']) for row in self._rows())
        return result

    def iter_records(self, source, cursor=None, limit=None):
        batch = super().iter_records(source, cursor, limit)
        for record in batch.records:
            for name in record.source['_atlas_unavailable_media']:
                asset = Asset(id=stable_id(self.dataset.id, self.revision, 'asset', 'file/' + name),
                              dataset_id=self.dataset.id, release_id=self.revision, modality='image',
                              metadata={'availability': 'absent_from_pinned_release', 'source_path': name})
                record.assets.append(asset)
                record.asset_ids.append(asset.id)
            turns = record.source.get('native_turns')
            if turns:
                record.source['_atlas_example_kind'] = 'conversation'
                by_name = {(asset.uri or 'file/' + asset.metadata['source_path']): asset.id for asset in record.assets}
                record.conversation = [
                    {'role': 'user', 'content': turn['prompt'], 'step': turn['step'],
                     'asset_ids': [by_name['file/' + turn['file_name']]],
                     'provenance': {'source': 'metadata.jsonl', 'id': turn['id'], 'step': turn['step']}}
                    for turn in turns]
                record.text = record.source['goal']
            else:
                record.text = record.source['original_prompt']
            # The parent charged the base record; account for this canonical projection too.
            source.charge(len(json.dumps(record.conversation).encode()) + sum(
                len(asset.model_dump_json().encode()) for asset in record.assets if asset.uri is None))
        return batch
