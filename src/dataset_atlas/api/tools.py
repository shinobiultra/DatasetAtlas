"""Trusted read-only tools scoped to IDs explicitly approved in model context."""
from __future__ import annotations
from collections import Counter
import math
from dataset_atlas.queries import field_value
from dataset_atlas.providers.schemas import ToolResult

def make_tool_backend(registry, record_lookup, jobs, result_artifacts=None):
    def version_pack(record):
        from dataset_atlas.models import Pack
        for dataset,path,_ in registry.versions(record.dataset_id):
            if (dataset.release,dataset.snapshot_id)==(record.release_id,record.snapshot_id) and path.is_file():
                if path.stat().st_size > 100_000_000:
                    raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
                pack=Pack.model_validate_json(path.read_text())
                chosen=[artifact for artifact in (result_artifacts or ()) if record.snapshot_id in artifact.snapshot_ids and artifact.unit==record.unit]
                if chosen:
                    from dataset_atlas.queries.results import attach_results
                    pack=attach_results(pack.model_copy(update={'records':[record]}),chosen)
                return pack
        raise ValueError('Approved snapshot metadata is unavailable')
    def backend(name,args,scope,remaining_rows):
        limit=min(args.get('limit',100),remaining_rows)
        if not 0<=limit<=1000:raise ValueError('Invalid row budget')
        ids=args.get('record_ids',sorted(scope))
        if not set(ids)<=scope:raise ValueError('Record outside approved selection')
        records=[record_lookup(id) for id in ids]
        if any(r is None for r in records):raise ValueError('Approved record unavailable')
        dataset_id=args.get('dataset_id')
        if dataset_id:
            if dataset_id not in {r.dataset_id for r in records}:raise ValueError('Dataset outside approved scope')
            records=[r for r in records if r.dataset_id==dataset_id]
        refs=[r.id for r in records]
        result=ToolResult(population_scope='approved_selection',coverage={'available':len(records),'unit': sorted({r.unit for r in records})},source_refs=refs)
        if name in {'describe_dataset','describe_fields'}:
            datasets=sorted({r.dataset_id for r in records})
            versions=sorted({(r.dataset_id,r.release_id,r.snapshot_id) for r in records})
            if name=='describe_dataset':
                result.data={'datasets':[{'id':d.id,'name':d.name,'description':d.description,'release':d.release,'snapshot_id':d.snapshot_id} for d in (registry.dataset_version(*version) for version in versions)]}
            else:
                fields={id:{} for id in datasets}
                for record in records:
                    for field in version_pack(record).fields:fields[record.dataset_id][field.id]=field.model_dump()
                result.data={'fields':{id:list(items.values()) for id,items in fields.items()},'snapshot_versions':[{'dataset_id':id,'release_id':release,'snapshot_id':snapshot} for id,release,snapshot in versions]}
        elif name in {'search_records','get_records'}:
            search=args.get('query','').lower()
            matched=[r for r in records if not search or search in ((r.text or '')+'\n'+(r.question or '')).lower()]
            result.rows=[{'id':r.id,'dataset_id':r.dataset_id,'snapshot_id':r.snapshot_id,'unit':r.unit,'text':r.text,'question':r.question,'choices':r.choices} for r in matched[:limit]]
            result.coverage.update({'matched':len(matched),'returned':len(result.rows),'searched_fields':['text','question']})
            result.truncated=len(matched)>limit
        elif name=='aggregate':
            field=args.get('field_id')
            known={f.id for r in records for f in version_pack(r).fields}|{'id','text','question'}
            if field not in known:raise ValueError('Unknown aggregation field')
            values=[field_value(r,field) for r in records]
            valid=[v for v in values if v is not None]
            numbers=[float(v) for v in valid if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)]
            result.data={'field_id':field,'denominator':len(values),'missing':len(values)-len(valid)}
            if valid and len(numbers)==len(valid):result.data.update({'mean':sum(numbers)/len(numbers),'min':min(numbers),'max':max(numbers)})
            else:result.data['counts']=dict(Counter(str(v) for v in valid).most_common(50))
        elif name=='inspect_images':
            result.rows=[{'id':r.id,'images':[{'asset_id':a.id,'modality':a.modality,'representation':a.representation} for a in r.assets if a.modality=='image'],'notice':'No image pixels returned by tools; pixels require approved context preview.'} for r in records[:limit]]
            result.truncated=len(records)>limit
        elif name=='get_run_results':
            if not jobs:raise ValueError('Runs unavailable')
            run_id=args.get('run_id')
            run=jobs.get_run(run_id)
            allowed=None if result_artifacts is None else {artifact.id for artifact in result_artifacts}
            selected=[identity for identity in run.artifact_ids if allowed is None or identity in allowed]
            if not selected:raise ValueError('Run results were not included in the inspected context approval')
            for artifact_id in selected:
                artifact=jobs.get_artifact(artifact_id)
                if artifact.run_id is not None and artifact.run_id!=run_id:raise ValueError('Approved result run binding is incompatible')
                if any(r.snapshot_id not in artifact.snapshot_ids or r.unit!=artifact.unit for r in records):raise ValueError('Run results do not match approved snapshots or units')
                for item in artifact.data.get('items',[]):
                    if item.get('id') in set(refs):
                        if item['id'] not in artifact.ids:raise ValueError('Result item is outside its registered subjects')
                        result.rows.append({'id':item['id'],'run_id':run_id,'artifact_id':artifact.id,'prediction':item})
            statuses=Counter(row['prediction'].get('status','unknown') for row in result.rows)
            result.coverage.update({'run_status':run.status,'requested_records':len(refs),'records_with_results':len({row['id'] for row in result.rows}),'item_statuses':dict(statuses),'partial':run.status!='completed' or any(status!='completed' for status in statuses) or len({row['id'] for row in result.rows})<len(refs)})
            result.truncated=len(result.rows)>limit;result.rows=result.rows[:limit]
            result.coverage['returned']=len(result.rows)
        else:raise ValueError('Unsupported read-only tool')
        return result
    # Production tools run in a disposable subprocess. The child reconstructs
    # metadata-only readers; no callable or dataset body crosses a model boundary.
    if registry is not None:
        backend._atlas_tool_root = str(registry.root)
        backend._atlas_tool_jobs = jobs is not None
    return backend
