"""Join explicitly selected immutable runs without changing source annotations."""
from __future__ import annotations
import math
from dataset_atlas.models import Pack,Artifact,FieldDescriptor

def attach_results(pack: Pack, artifacts: list[Artifact]) -> Pack:
    result=pack.model_copy(deep=True)
    if any(a.unit=='asset' for a in artifacts):
        from dataset_atlas.queries import materialize_records
        existing={r.id for r in result.records}
        result.records.extend(r for r in materialize_records(pack,'asset') if r.id not in existing)
    records={r.id:r for r in result.records}
    fields={f.id:f for f in result.fields}
    attached=[]
    for artifact in artifacts:
        if pack.dataset.snapshot_id not in artifact.snapshot_ids:raise ValueError('Result snapshot is incompatible with the dataset snapshot')
        attached.append(artifact)
        outputs=artifact.data.get('items',[])
        for item in outputs:
            record=records.get(item.get('id'))
            if record is None:continue
            prefix=artifact.id+'.'
            values={'status':item.get('status','unknown')}
            if item.get('status')=='completed':
                output=item.get('output',{})
                for key,value in output.items():
                    if value is None or isinstance(value,(str,bool,int,float)):
                        if isinstance(value,float) and not math.isfinite(value):continue
                        values[key]=value
                detections=output.get('detections')
                if isinstance(detections,list):values['detection_count']=len(detections)
                # Vision output retains original per-asset results separately.
                asset_outputs=output.get('assets')
                if isinstance(asset_outputs,list):
                    completed=[a for a in asset_outputs if a.get('status')=='completed']
                    if len(completed)==1 and len(asset_outputs)==1:
                        for key,value in completed[0].items():
                            if key not in {'asset_id','status'} and (value is None or isinstance(value,(str,bool,int,float))):values[key]=value
                    if len(completed)==len(asset_outputs):
                        detection_sets=[a.get('detections',a.get('output',{}).get('detections')) for a in completed]
                        if all(isinstance(d,list) for d in detection_sets):
                            boxes=[box for ds in detection_sets for box in ds]
                            values['detection_count']=len(boxes)
                            values['person_count']=sum(d.get('class')=='person' for d in boxes)
            for key,value in values.items():
                name=prefix+key
                record.prediction[name]=value
                field_id='prediction.'+name
                dtype='boolean' if isinstance(value,bool) else 'number' if isinstance(value,(int,float)) else 'string'
                fields.setdefault(field_id,FieldDescriptor(id=field_id,name=artifact.kind+' · '+key,namespace='prediction',dtype=dtype,unit=record.unit,provenance={'artifact_id':artifact.id,'run_id':artifact.run_id,'aggregation_version':'1.0'},query_ops=['eq','ne','in','contains','is_null']+(['gt','gte','lt','lte'] if dtype=='number' else [])))
    result.artifacts=attached
    result.fields=list(fields.values())
    return result
