"""Regenerate the synthetic JS/Python query parity fixture from canonical Python models."""
import json
from pathlib import Path

from dataset_atlas.models import Asset, Dataset, FieldDescriptor, Pack, Query, Record
from dataset_atlas.queries import aggregate_pack, query_pack


dataset = Dataset(id='synthetic-parity', name='Synthetic parity fixture', snapshot_id='synthetic-v1')
fields = [
    FieldDescriptor(id=f'source.{name}', name=name, dtype=dtype, query_ops=['eq', 'ne', 'in', 'contains', 'gt', 'gte', 'lt', 'lte', 'is_null'])
    for name, dtype in [('group', 'category'), ('score', 'number'), ('meta.key', 'string')]
]

sources = [
    ('α-1', 'A', 1, 'North', 'First blue cube', 'a-1'),
    ('β-2', 'B', 3, 'South', 'Second red sphere', 'a-1'),
    ('r-3', 'A', None, 'North', 'Third blue sphere', 'a-3'),
    ('r-4', 'B', 2, 'East', 'Fourth green cube', 'a-4'),
    ('r-5', 'A', 3, None, 'Fifth blue block', 'a-5'),
    ('r-6', 'B', 0, 'East', 'Sixth yellow block', 'a-6'),
]
records = [
    Record(
        id=identity, dataset_id=dataset.id, release_id='fixture-v1', snapshot_id=dataset.snapshot_id,
        question=text, source={'group': group, 'score': score, 'meta.key': nested},
        assets=[Asset(id=asset_id, dataset_id=dataset.id, release_id='fixture-v1', modality='image', metadata={'asset_group': group})],
    )
    for identity, group, score, nested, text, asset_id in sources
]
pack = Pack(dataset=dataset, fields=fields, records=records, population_scope='preview')
queries = {
    'base': Query(snapshot_id=dataset.snapshot_id, limit=3),
    'search': Query(snapshot_id=dataset.snapshot_id, search='BLUE'),
    'eq_dotted': Query(snapshot_id=dataset.snapshot_id, filter={'field_id': 'source.meta.key', 'op': 'eq', 'value': 'East'}),
    'ne_null': Query(snapshot_id=dataset.snapshot_id, filter={'field_id': 'source.score', 'op': 'ne', 'value': 1}),
    'is_null': Query(snapshot_id=dataset.snapshot_id, filter={'field_id': 'source.score', 'op': 'is_null', 'value': True}),
    'contains': Query(snapshot_id=dataset.snapshot_id, filter={'field_id': 'source.meta.key', 'op': 'contains', 'value': 'north'}),
    'sort_null_last': Query(snapshot_id=dataset.snapshot_id, sort=[{'field_id': 'source.score', 'direction': 'desc'}]),
    'random': Query(snapshot_id=dataset.snapshot_id, sample={'method': 'random', 'size': 4, 'seed': 42}),
    'stratified': Query(snapshot_id=dataset.snapshot_id, sample={'method': 'stratified', 'size': 5, 'seed': 5, 'field_id': 'source.group'}),
    'asset': Query(snapshot_id=dataset.snapshot_id, unit='asset'),
}

# Aggregate parity keeps the overview's counts identical in both providers.
aggregates = {
    'all_fields': (Query(snapshot_id=dataset.snapshot_id), ['source.group', 'source.score', 'source.meta.key']),
    'filtered': (Query(snapshot_id=dataset.snapshot_id, filter={'field_id': 'source.group', 'op': 'eq', 'value': 'A'}), ['source.group', 'source.score']),
    'searched': (Query(snapshot_id=dataset.snapshot_id, search='blue'), ['source.group']),
    'sample_ignored': (Query(snapshot_id=dataset.snapshot_id, sample={'method': 'random', 'size': 2, 'seed': 42}), ['source.group']),
    'asset_unit': (Query(snapshot_id=dataset.snapshot_id, unit='asset'), ['source.asset_group']),
}

fixture = {
    'pack': pack.model_dump(mode='json'),
    'cases': {name: {'query': query.model_dump(mode='json'), 'ids': [row.id for row in query_pack(pack, query).records], 'matched_count': query_pack(pack, query).matched_count} for name, query in queries.items()},
    'aggregates': {
        name: {'query': query.model_dump(mode='json'), 'field_ids': field_ids, 'expected': aggregate_pack(pack, query, field_ids)}
        for name, (query, field_ids) in aggregates.items()
    },
}
output = Path(__file__).resolve().parents[1] / 'src' / 'test-fixtures' / 'query-parity.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + '\n')
print(output)
