#!/usr/bin/env python3
"""Compare every prepared transistor with the pinned Visual6502 source table."""
import ast
import hashlib
import json
from pathlib import Path

import httpx
import pyarrow.parquet as pq

from dataset_atlas.registry import Registry


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'work/sources/visual6502-d8ecc129/transdefs.js'
BASE = 'http://127.0.0.1:8765'


def main():
    registry = Registry(ROOT)
    dataset = registry.dataset('visual6502-transistor-netlist')
    if dataset.coverage.identity != 'candidate':
        raise ValueError('Paper-specific 6507 identity was prematurely resolved')
    source_bytes = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != dataset.adapter_config['sha256']:
        raise ValueError('Pinned Visual6502 source differs')
    native = ast.literal_eval(source_bytes.decode().split('=', 1)[1].strip())
    rows = pq.read_table(registry.snapshot_path(dataset.id) / 'records.parquet',
        columns=['record_json'])['record_json'].to_pylist()
    if not (len(native) == len(rows) == 3510):
        raise ValueError('Native and indexed transistor counts differ')
    ids = set()
    for index, (row, serialized) in enumerate(zip(native, rows)):
        record = json.loads(serialized); source = record['source']
        if (source['transistor_id'] != row[0] or source['gate_node'] != row[1]
                or source['channel_node_1'] != row[2] or source['channel_node_2'] != row[3]
                or source['bounding_box'] != row[4] or source['geometry'] != row[5]
                or source['_atlas_origin']['row'] != index or record['id'] in ids):
            raise ValueError(f'Native/index transistor mismatch at {index}')
        ids.add(record['id'])
    pack = registry.pack(dataset.id)
    if len(pack.records) != 100 or any(record.id not in ids for record in pack.records):
        raise ValueError('Preview is not a 100-record subset of the pinned source')
    with httpx.Client(timeout=30) as client:
        response = client.post(BASE + '/api/v1/queries/' + dataset.id,
            json={'population_scope':'complete','snapshot_id':dataset.snapshot_id,'limit':10},
            headers={'X-Atlas-Request':'1'})
        response.raise_for_status()
        queried = response.json()['records']
        if len(queried) != 10 or any(row['id'] not in ids for row in queried):
            raise ValueError('Live complete-population query did not return native transistors')
    report = {'dataset_id':dataset.id, 'snapshot_id':dataset.snapshot_id,
        'source_commit':dataset.adapter_config['commit'], 'source_file_sha256':source_hash,
        'native_rows_compared':len(rows), 'preview_records':len(pack.records),
        'live_complete_query_records_checked':len(queried),
        'scope_note':'Complete pinned Visual6502 6502 revD transdefs.js. The citing paper used a 6507 netlist; equality of its exact input remains unverified.',
        'publication_note':'Source file-specific copyright requires review; no records or media added to the public pack.'}
    path=ROOT/'reports/visual6502-live-verification-20260924.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
