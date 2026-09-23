"""Join the five native RAVEL entity, attribute, template and split inventories."""
from __future__ import annotations
import json
import tarfile
from .core import DatasetAdapter, DirectoryArchiveAdapter, RecordBatch


class RavelAdapter(DirectoryArchiveAdapter):
    def _rows(self):
        if hasattr(self, '_metadata_rows'):
            return self._metadata_rows
        groups = []
        with tarfile.open(self._path()) as archive:
            members = {m.name: m for m in archive.getmembers() if m.isfile()}
            consumed = 0
            def read(name):
                nonlocal consumed
                member = members['data/' + name + '.json']
                consumed += member.size
                if consumed > self.config.get('max_annotation_bytes', 20_000_000):
                    raise ValueError('RAVEL annotations exceed byte budget')
                with archive.extractfile(member) as stream:
                    return json.load(stream)
            for domain in self.config.get('domains', ['city', 'nobel_prize_winner', 'occupation', 'physical_object', 'verb']):
                attributes = read(f'ravel_{domain}_entity_attributes')
                entities = read(f'ravel_{domain}_entity_to_split')
                prompts = read(f'ravel_{domain}_attribute_to_prompts')
                prompt_splits = read(f'ravel_{domain}_prompt_to_split')
                wikipedia = read(f'wikipedia_{domain}_entity_prompts')
                if set(attributes) != set(entities):
                    raise ValueError('RAVEL entity split inventory differs from attributes')
                if {p for ps in prompts.values() for p in ps} != set(prompt_splits):
                    raise ValueError('RAVEL prompt split inventory differs from templates')
                rows = []
                for entity, values in attributes.items():
                    if set(values) - set(prompts):
                        raise ValueError('RAVEL entity attribute has no template taxonomy entry')
                    rows.append({'identity': json.dumps([domain, 'entity', entity]), 'record_kind': 'entity_inventory',
                        'domain': domain, 'entity': entity, 'text': entity,
                        'attributes': values, 'entity_split': entities[entity],
                        'attributes_without_released_values': sorted(set(prompts) - set(values)),
                        'attribute_templates': {name: [{'prompt': p, 'split': prompt_splits[p]} for p in ps] for name, ps in prompts.items()}})
                groups.append(rows)
                # Wikipedia prompts are a separate control population. Their
                # entities need not occur in the benchmark attribute inventory.
                groups.append([{'identity': json.dumps([domain, 'wikipedia', prompt]), 'record_kind': 'wikipedia_prompt',
                    'domain': domain, 'entity': info['entity'], 'text': prompt, 'prompt_split': info['split'],
                    'entity_in_attribute_inventory': info['entity'] in entities} for prompt, info in wikipedia.items()])
        # Deterministic domain interleaving makes the preview inspect all five domains.
        self._metadata_rows = [rows[i] for i in range(max(map(len, groups), default=0)) for rows in groups if i < len(rows)]
        return self._metadata_rows

    @property
    def count(self):
        return len(self._rows())

    def iter_records(self, source, cursor=None, limit=None):
        start = int(cursor or 0)
        if start < 0:
            raise ValueError('Negative cursor')
        rows = self._rows()
        end = min(start + min(limit or source.limit, source.limit), len(rows))
        self.config['mapping'] = {'id': 'identity', 'text': 'text'}
        records = [DatasetAdapter._record(self, row, i) for i, row in enumerate(rows[start:end], start)]
        source.charge(sum(len(record.model_dump_json().encode()) for record in records))
        return RecordBatch(records, str(end) if end < len(rows) else None, len(records))
