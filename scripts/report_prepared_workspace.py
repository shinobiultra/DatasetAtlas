#!/usr/bin/env python3
"""Refresh local coverage receipts from immutable prepared versions and the registry."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from dataset_atlas.registry import Registry
from dataset_atlas.preparation import PreparationManager

root=Path(__file__).resolve().parents[1]
registry=Registry(root)
datasets=registry.datasets()
receipts=[]
for dataset in datasets:
    active=registry.active_directory(dataset.id)
    if active is None:continue
    receipt=json.loads((active/'receipt.json').read_text())
    receipts.append({'dataset_id':dataset.id,'release':dataset.release,'snapshot_id':dataset.snapshot_id,
        'records':dataset.coverage.total_count,'preview_records':dataset.coverage.preview_count,
        'scope':receipt['scope'],'plan_id':receipt['plan_id'],
        'prepared_receipt':str((active/'receipt.json').relative_to(root))})
preview_count=sum(d.coverage.preview_count>0 for d in datasets)
index_count=sum((registry.snapshot_path(d.id)/'manifest.json').is_file() for d in datasets)
report={'checked_at':datetime.now(timezone.utc).isoformat(),'datasets':receipts,'catalogue_entries':len(datasets),
    'with_previews':preview_count,'without_previews':len(datasets)-preview_count,'full_population_indices':index_count,
    'all_requested_datasets_complete':False,
    'note':'Acquired source populations and on-demand infrastructure; catalogue-wide coverage is not complete.'}
(root/'reports/on-demand-preparation.json').write_text(json.dumps(report,indent=2)+'\n')
path=root/'reports/dataset_coverage.csv'
with path.open(newline='') as stream:
    reader=csv.DictReader(stream);columns=reader.fieldnames;rows=list(reader)
by_id={d.id:d for d in datasets}
rows=[row for row in rows if row['dataset_id'] in by_id]  # entries moved to registry/excluded leave the matrix
missing=sorted(set(by_id)-{row['dataset_id'] for row in rows})
if missing:raise SystemExit('The coverage matrix has no row for: '+', '.join(missing)+'. Add one (copy a row from git history) and rerun.')
for row in rows:
    dataset=by_id[row['dataset_id']]
    for key,value in dataset.coverage.model_dump().items():
        if key in columns and key!='blockers':row[key]='' if value is None else value
    row.update(blockers=' | '.join(dataset.coverage.blockers),release=dataset.release,snapshot_id=dataset.snapshot_id or '',
               source_url=dataset.source_url or '',evidence_count=len(dataset.evidence))
    if registry.active_directory(dataset.id):
        pending=[]
        if dataset.coverage.identity!='resolved':pending.append('identity')
        if dataset.coverage.complete_data=='indexed_metadata_partial_media':pending.append('partial_media')
        pending.append('publication_review')
        row['blocker_type']='_and_'.join(pending)
with path.open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=columns,lineterminator="\n");writer.writeheader();writer.writerows(rows)
status_path=root/'reports/final-status.json'
status=json.loads(status_path.read_text())
status.pop('active_download', None)  # Superseded by the actual preparation list.
status.update(checked_at_utc=report['checked_at'],catalogue_entries=len(datasets),tested_local_previews=preview_count,
              verified_preview_records=sum(d.coverage.preview_count for d in datasets),canonical_full_scope_indices=index_count,
              entries_without_preview=len(datasets)-preview_count,full_v1_complete=False,
              active_preparations=[s for s in PreparationManager(root).list() if s['status'] in {'queued','running'}],
              gqa_browsing_snapshot_media_scope=registry.dataset('gqa').adapter_config.get('media_scope'))
status_path.write_text(json.dumps(status,indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items() if key!='datasets'},indent=2))
