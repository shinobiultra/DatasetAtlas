"""Prepare pinned original MMBench and RealWorldQA, no external model calls."""
from pathlib import Path
import base64,collections,csv,hashlib,io,json
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
import yaml
from dataset_atlas.adapters import get_adapter,build_preview
from dataset_atlas.registry import Registry
from dataset_atlas.queries.parquet import build_parquet_snapshot
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def resolve_reference(identity,images):
    seen=set()
    while True:
        if identity in seen:raise ValueError('Cyclic image reference')
        seen.add(identity)
        if identity not in images:raise ValueError('Missing image reference')
        value=images[identity]
        if len(value)>64:return identity,base64.b64decode(value,validate=True)
        identity=value

def mmbench():
    root=ROOT/'work/sources/mmbench-en-dev';original=root/'MMBench_DEV_EN.tsv'
    if sha(original)!='64baa14c5ec650302f428212a0b3efc5c88fbf9236d0d6fdea45c555f0b02d7a':raise ValueError('MMBench source SHA mismatch')
    if hashlib.md5(original.read_bytes()).hexdigest()!='b6caf1133a01c6bb705cf753bb527ed8':raise ValueError('MMBench differs from author VLMEvalKit MD5')
    csv.field_size_limit(10_000_000)
    with original.open() as stream:raw=list(csv.DictReader(stream,delimiter='\t'))
    images={row['index']:row['image'] for row in raw}
    if len(images)!=len(raw):raise ValueError('Duplicate source indices')
    media=root/'images';media.mkdir(exist_ok=True);prepared=[];image_ids=set()
    for row in raw:
        original_image_index,data=resolve_reference(row['index'],images)
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'JPEG','PNG'}:raise ValueError('Unsupported source image encoding')
            suffix='.jpg' if image.format=='JPEG' else '.png';width,height=image.size;image.verify()
        digest=hashlib.sha256(data).hexdigest();filename=digest+suffix
        if not (media/filename).exists():(media/filename).write_bytes(data)
        image_ids.add(original_image_index)
        record={**row,'image':filename,'source_id':row['index'],'source_image_index':original_image_index,'image_sha256':digest,'image_width':width,'image_height':height,'choices':[f'{key}. {row[key]}' for key in 'ABCD' if row.get(key)]}
        prepared.append(record)
    if len(prepared)!=4329 or len(image_ids)!=1164:raise ValueError('MMBench CircularEval source counts changed')
    output=root/'records.parquet';pq.write_table(pa.Table.from_pylist(prepared),output,compression='zstd')
    return dict(identity='mmbench-en-dev',name='MMBench English dev v1.0 (CircularEval)',source_url='https://github.com/open-compass/MMBench',release='MMBench_DEV_EN-v1.0-md5-b6caf1133a01c6bb705cf753bb527ed8',output=output,count=4329,adapter='structured',media_root=str(media.relative_to(ROOT)),mapping={'id':'source_id','media':'image','question':'question','text':'hint','choices':'choices'},fields={'answer':{'dtype':'category','values':list('ABCD')},'category':{'dtype':'category'},'l2-category':{'dtype':'category'},'source':{'dtype':'category'},'split':{'dtype':'category','values':['dev']},'source_image_index':{'dtype':'string'},'index':{'dtype':'string'},'choices':{'dtype':'array'}},scope='Original English dev v1.0: 4,329 CircularEval choice-order variants of 1,164 questions/image entries, not 4,329 independent base questions. Base64 image references resolved to exact original bytes; all original question/hint/options/answers and categories retained. HTTPS endpoint certificate was expired; official HTTP bytes match MD5 published in author VLMEvalKit HTTPS source.',evidence={'source_download':'http://opencompass.openxlab.space/utils/benchmarks/MMBench/MMBench_DEV_EN.tsv','source_sha256':sha(original),'author_expected_md5':'b6caf1133a01c6bb705cf753bb527ed8','question_image_groups':1164,'variant_rows':4329,'distinct_image_hashes':len(list(media.iterdir()))},rights='Source aggregates public datasets and Internet images; code/repository license alone does not authorize media publication.')

def realworld():
    root=ROOT/'work/sources/realworldqa';output=root/'records.parquet'
    expected=['2cf29e308a34e0255f23520796fc04445a01b8baab18686f1a4b3c3943f695b2','dac5b9f7cfb947a4865ea3424abfbdb3449d09e0a0b911a787cdc930cefefdc0'];count=0
    writer=None
    try:
        for shard,digest in enumerate(expected):
            path=root/f'test-{shard:05d}-of-00002.parquet'
            if sha(path)!=digest:raise ValueError('Author Parquet shard changed')
            offset=0
            for batch in pq.ParquetFile(path).iter_batches(batch_size=8):
                table=pa.Table.from_batches([batch]);length=table.num_rows
                table=table.append_column('source_id',pa.array([f'{shard}:{offset+i}' for i in range(length)]))
                table=table.append_column('source_shard',pa.array([path.name]*length))
                table=table.append_column('source_row',pa.array(list(range(offset,offset+length))))
                if writer is None:writer=pq.ParquetWriter(output,table.schema,compression='zstd')
                writer.write_table(table);offset+=length;count+=length
    finally:
        if writer:writer.close()
    if count!=765:raise ValueError('RealWorldQA source count changed')
    return dict(identity='realworldqa',name='RealWorldQA',source_url='https://huggingface.co/datasets/xai-org/RealworldQA/tree/17e7f75e092e47169732462ea3cdfebe911105dd',release='hf-17e7f75e092e47169732462ea3cdfebe911105dd',output=output,count=count,adapter='embedded_parquet',mapping={'id':'source_id','media':'image','question':'question'},fields={'answer':{'dtype':'string'},'source_shard':{'dtype':'category'},'source_row':{'dtype':'number'},'image':{'dtype':'object','description':'Original embedded image metadata; binary pixels stay outside JSON records'}},scope='All 765 author image/question/answer rows from two pinned Parquet shards. Original image bytes retained; local consolidation only adds exact source shard and row provenance. Questions retain their original inline options.',evidence={'source_shards_sha256':expected,'source_rows':count},rights='Author dataset card specifies CC BY-ND 4.0. No public image approval; original embedded bytes remain unchanged in local browsing.')

def prepare(config):
    identity=config['identity'];output=config['output'];digest=sha(output)
    path=ROOT/'registry/datasets'/f'{identity}.yaml';manifest=yaml.safe_load(path.read_text())
    manifest.update(name=config['name'],description=config['scope'],release=config['release'],source_url=config['source_url'],snapshot_id=identity+'-'+digest,adapter=config['adapter'],modalities=['image','text'],tasks=['visual question answering'])
    adapter_config={'path':str(output.relative_to(ROOT)),'format':'parquet','sha256':digest,'mapping':config['mapping'],'fields':config['fields']}
    if config.get('media_root'):adapter_config['media_root']=config['media_root']
    if config['adapter']=='embedded_parquet':adapter_config['media_columns']=['image']
    manifest['adapter_config']=adapter_config
    manifest['coverage'].update(identity='resolved',source='verified',access='public',adapter='tested',preview='complete_target',complete_data='supported',publication='metadata_only',preview_count=100,total_count=config['count'],blockers=['Public media redistribution has not been approved; local original media is available.'])
    manifest['rights']={'records':'CC-BY-ND-4.0' if identity=='realworldqa' else 'not_reviewed','annotations':'not_reviewed','images':'not_reviewed','external_provider':'local_only','source':config['source_url'],'basis':config['rights']}
    evidence={'kind':'verified_source_acquisition','checked_at':'2026-09-22','source_url':config['source_url'],**config['evidence'],'scope':config['scope']}
    if evidence not in manifest.setdefault('evidence',[]):manifest['evidence'].append(evidence)
    path.write_text(yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True))
    dataset=Registry(ROOT).dataset(identity)
    pack=build_preview(dataset,ROOT/'work/packs'/identity,limit=100,max_bytes=300_000_000,distinct_assets=True,include_media=True)
    adapter=get_adapter(dataset);snapshots=ROOT/'work/snapshots'
    build_parquet_snapshot((adapter._record(row,index) for index,row in enumerate(adapter._rows())),pack.fields,snapshots/identity,root=snapshots,dataset_id=identity,release_id=dataset.release,snapshot_id=dataset.snapshot_id,expected_count=config['count'],population_scope='complete',max_bytes=500_000_000)
    source=adapter.prepare(adapter.plan(1,10_000_000));last=adapter.iter_records(source,str(config['count']-1),1).records[0]
    handle=adapter.resolve_asset(source,last.assets[0].uri)
    report={**evidence,'prepared_parquet_sha256':digest,'preview_records':len(pack.records),'preview_assets':len({asset.id for record in pack.records for asset in record.assets}),'final_record_id':last.id,'final_image_sha256':handle.sha256,'final_image_bytes':len(handle.data)}
    (ROOT/'reports'/f'{identity}-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':
    import sys
    for identity in sys.argv[1:] or ['mmbench-en-dev','realworldqa']:prepare(mmbench() if identity=='mmbench-en-dev' else realworld())
