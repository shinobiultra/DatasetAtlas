"""Exercise installed local processors through the live API on frozen real records.

No datasets or weights are downloaded; no external model provider is contacted.
Receipts retain run identities, exact source snapshots and processor provenance.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time

import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8766')
    parser.add_argument('--dataset',default='clevr')
    parser.add_argument('--records',type=int,default=16)
    parser.add_argument('--embedding',choices=['minilm','siglip2'],default='minilm',
        help='Embedding space that drives projection, clustering and outliers; siglip2 for image-only datasets, whose text is only a display label')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 6<=args.records<=100:raise ValueError('Verification uses 6..100 real preview records')
    client=httpx.Client(base_url=args.url,timeout=90,headers={'X-Atlas-Request':'1'})
    def get(path):
        response=client.get('/api/v1'+path);response.raise_for_status();return response.json()
    def post(path,body):
        response=client.post('/api/v1'+path,json=body);response.raise_for_status();return response.json()
    pack=get('/datasets/'+args.dataset+'/pack')
    selected=pack['records'][:args.records]
    selection=post('/selections',{'id':'','name':'Local processor runtime verification '+datetime.now(timezone.utc).isoformat(),
        'ids':[r['id'] for r in selected],'dataset_ids':[args.dataset],
        'snapshot_ids':sorted({r['snapshot_id'] for r in selected}),'unit':'example','method':'source',
        'created_at':datetime.now(timezone.utc).isoformat()})
    receipt={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'api':args.url,'selection_id':selection['id'],
             'snapshot_ids':selection['snapshot_ids'],'record_count':len(selected),'runs':{},
             'scope':'Functional local runtime verification on a frozen preview selection; no benchmark-accuracy claim.',
             'external_model_requests':0}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    def run(processor,config):
        body={'selection_id':selection['id'],'processor_id':processor,'config':{
            'max_records':args.records,'max_wall_seconds':600,'max_cpu_seconds':600,'max_rss_bytes':8_000_000_000,
            'device':'auto','validation_checkpoint':receipt['checked_at_utc'],**config}}
        estimate=post('/runs/estimate',body)
        body['estimate_digest']=estimate['estimate_digest']
        started=post('/runs',body)
        receipt['runs'][processor]={'run_id':started['id'],'estimate_digest':body['estimate_digest'],'status':started['status']};save()
        deadline=time.monotonic()+630
        while True:
            current=get('/runs/'+started['id'])
            if current['status'] in {'completed','failed','partial','cancelled'}:break
            if time.monotonic()>deadline:
                post('/runs/'+started['id']+'/cancel',{})
                raise TimeoutError('Bounded runtime verification timed out')
            time.sleep(1)
        receipt['runs'][processor].update(status=current['status'],artifact_ids=current['artifact_ids'],errors=current['errors'])
        save()
        if current['status']!='completed':raise RuntimeError(processor+' failed; inspect the retained run receipt')
        artifact=get('/artifacts/'+current['artifact_ids'][0])
        receipt['runs'][processor].update(coverage=artifact['coverage'],provenance=artifact['provenance']);save()
        print(json.dumps({'processor':processor,'status':current['status'],'run_id':current['id']}),flush=True)
        return artifact
    embeddings={}
    sequence=['quality.basic','detect.nudenet','detect.coco_v1']+(['embed.minilm','embed.siglip2'] if args.embedding=='minilm' else ['embed.siglip2'])
    for processor in sequence:
        artifact=run(processor,{})
        if processor.startswith('embed.'):embeddings[processor.split('.',1)[1]]=artifact
    mini=embeddings[args.embedding]
    for processor,config in [('project.pca',{}),('project.umap',{'neighbors':5,'seed':42}),
                             ('cluster.kmeans',{'clusters':3,'seed':42}),('outlier.knn',{'neighbors':3})]:
        run(processor,{'embedding_artifact_id':mini['id'],**config})
    exported=get('/selections/'+selection['id']+'/export')
    receipt['selection_export_checksum']=exported['checksum'];receipt['completed']=True;save()
    client.close()


if __name__=='__main__':main()
