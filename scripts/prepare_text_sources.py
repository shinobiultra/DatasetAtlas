"""Reproduce local, lossless GLUE/SentEval/CEBaB conversions from acquired originals.

No downloads or upstream code execution. Keeps task splits and original columns;
GLUE hidden labels remain null. CEBaB split alternatives intentionally overlap.
"""
from __future__ import annotations
import collections,hashlib,json,zipfile
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from dataset_atlas.registry import Registry
from dataset_atlas.adapters import build_preview,get_adapter
from dataset_atlas.queries.parquet import build_parquet_snapshot

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'work/sources/glue'
EXPECTED_SHA256 = {'CoLA.zip': 'f212fcd832b8f7b435fb991f101abf89f96b933ab400603bf198960dfc32cbff', 'QNLIv2.zip': 'e634e78627a29adaecd4f955359b22bf5e70f2cbd93b493f2d624138a0c0e5f5', 'QQP-clean.zip': '40e7c862c04eb26ee04b67fd900e76c45c6ba8e6d8fab4f8f1f8072a1a3fbae0', 'WNLI.zip': 'ae0e8e4d16f4d46d4a0a566ec7ecceccfd3fbfaa4a7a4b4e02848c0f2561ac46', 'CEBaB-v1.1.zip': 'afe8ebcb5d18f33297512cd5c7e05f1590b82fb0683367042454c3eda7d5c6ae', 'msr_paraphrase_train.txt': '60a9b09084528f0673eedee2b69cb941920f0b8cd0eeccefc464a98768457f89', 'msr_paraphrase_test.txt': 'a04e271090879aaba6423d65b94950c089298587d9c084bf9cd7439bd785f784'}
CONFIG={
 'glue-cola':('CoLA.zip','CoLA','GLUE CoLA','linguistic acceptability'),
 'qnli':('QNLIv2.zip','QNLI','GLUE QNLI v2','question-answer entailment'),
 'qqp':('QQP-clean.zip','QQP','GLUE QQP clean','duplicate question classification'),
 'wnli':('WNLI.zip','WNLI','GLUE WNLI','natural language inference'),
}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def tsv_rows(text,headers=None):
    lines=text.splitlines()
    if headers is None:headers=lines.pop(0).split('\t')
    for ordinal,line in enumerate(lines):
        values=line.split('\t')
        if len(values)!=len(headers):raise ValueError(f'Malformed source row {ordinal}: expected {len(headers)} columns, got {len(values)}')
        yield ordinal,dict(zip(headers,values,strict=True))

def glue_rows(dataset_id):
    archive,folder,_,_=CONFIG[dataset_id]
    with zipfile.ZipFile(SOURCE/archive) as z:
        for split in ('train','dev','test'):
            member=f'{folder}/{split}.tsv'
            headers=['publication','label','author_annotation','sentence'] if dataset_id=='glue-cola' and split!='test' else None
            for ordinal,row in tsv_rows(z.read(member).decode('utf-8-sig'),headers):
                label=row.get('label',row.get('is_duplicate'))
                row.update(source_id=f'{split}:{ordinal}',split=split,source_member=member,label=label,label_status='withheld_by_glue' if label is None else 'source_labeled')
                row['display_text']=row.get('sentence',row.get('question1',row.get('sentence1','')))
                if 'question2' in row:row['display_text']+='\n\n'+row['question2']
                if 'sentence2' in row:row['display_text']+='\n\n'+row['sentence2']
                yield row

def mrpc_rows():
    for split in ('train','test'):
        path=SOURCE/f'msr_paraphrase_{split}.txt'
        for ordinal,row in tsv_rows(path.read_text(encoding='utf-8-sig')):
            row.update(source_id=f'{split}:{ordinal}',split=split,source_member=path.name,label=row['Quality'],label_status='source_labeled',display_text=row['#1 String']+'\n\n'+row['#2 String'])
            yield row

def cebab_rows():
    with zipfile.ZipFile(SOURCE/'CEBaB-v1.1.zip') as z:
        for split in ('train_inclusive','train_exclusive','train_observational','dev','test'):
            member=f'CEBaB-v1.1/{split}.json'
            for original in json.loads(z.read(member)):
                yield {**original,'source_id':split+':'+original['id'],'split':split,'source_member':member}

def prepare(dataset_id):
    if dataset_id=='cebab':
        generator=cebab_rows;archives=['CEBaB-v1.1.zip'];name='CEBaB v1.1';task='concept-based causal explanation';fmt='jsonl'
        source_url='https://github.com/CEBaBing/CEBaB'
        note='All five source split files; train_inclusive, train_exclusive and train_observational are alternative overlapping populations, not independent pooled examples. Original review IDs, edit IDs, label distributions, disagreement and worker fields are preserved. Corpus role remains related-work mention.'
        source_download='https://raw.githubusercontent.com/CEBaBing/CEBaB/40e68518fe66a3b5e53b52741c5b180c8a096295/CEBaB-v1.1.zip'
    elif dataset_id=='mrpc':
        generator=mrpc_rows;archives=['msr_paraphrase_train.txt','msr_paraphrase_test.txt'];name='MRPC (SentEval-hosted tokenized distribution)';task='paraphrase classification';fmt='parquet'
        source_url='https://github.com/nyu-mll/GLUE-baselines/blob/master/download_glue_data.py'
        note='SentEval-hosted tokenized train/test files explicitly linked by GLUE baseline authors. This preserves original 4,076 train and 1,725 labeled test rows; it does not invent a GLUE train/dev partition or hide the available original test labels.'
        source_download=source_url
    else:
        archive,_,name,task=CONFIG[dataset_id];archives=[archive];generator=lambda:glue_rows(dataset_id);fmt='parquet'
        source_url='https://gluebenchmark.com/tasks'
        source_download='https://dl.fbaipublicfiles.com/glue/data/'+archive
        note='Official GLUE ZIP train/dev/test task files, original TSV columns preserved, withheld test labels null. Auxiliary original/tokenized copies in CoLA ZIP are not double-counted. Release is pinned by downloaded archive SHA-256, not an inferred paper-specific subset.'
    directory=ROOT/'work/sources'/dataset_id;directory.mkdir(exist_ok=True)
    output=directory/f'records.{fmt}'
    hashes={filename:sha(SOURCE/filename) for filename in archives}
    if any(digest!=EXPECTED_SHA256[filename] for filename,digest in hashes.items()):raise ValueError("Original source bytes differ from reviewed source release")
    count=0;counts=collections.Counter();labels=set();columns=set();source_ids=set();upstream_ids=set()
    # Determine complete schema, count, and IDs without retaining the population.
    for row in generator():
        count+=1;counts[row['split']]+=1;columns.update(row)
        if row['source_id'] in source_ids:raise ValueError('Duplicate split/source identity')
        source_ids.add(row['source_id'])
        if row.get('id'):upstream_ids.add(row['id'])
        if row.get('label') is not None:labels.add(row['label'])
    if fmt=='jsonl':
        with output.open('w') as stream:
            for row in generator():stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    else:
        schema=pa.schema([(column,pa.string()) for column in sorted(columns)])
        with pq.ParquetWriter(output,schema,compression='zstd') as writer:
            batch=[]
            for row in generator():
                batch.append(row)
                if len(batch)==10000:writer.write_table(pa.Table.from_pylist(batch,schema=schema));batch=[]
            if batch:writer.write_table(pa.Table.from_pylist(batch,schema=schema))
    converted_sha=sha(output)
    path=ROOT/'registry/datasets'/f'{dataset_id}.yaml';manifest=yaml.safe_load(path.read_text())
    fields={key:{'dtype':'string','description':'Original source field; see source_member and release provenance'} for key in sorted(columns) if key!='display_text'}
    fields['split']={'dtype':'category','values':list(counts),'description':'Original split; CEBaB train alternatives overlap'}
    if labels:fields['label']={'dtype':'category','values':sorted(labels),'description':'Original source label; null only when source does not provide it'}
    if dataset_id=='cebab':
        for key in columns:
            if key.endswith('_distribution') or key.endswith('_workers') or key=='opentable_metadata':fields[key]={'dtype':'object','description':'Original annotation/metadata mapping; empty-string sentinels retained'}
        fields['is_original']={'dtype':'boolean','description':'Original source review versus counterfactual edit'}
        for key in ('edit_type','edit_goal','review_majority','food_aspect_majority','ambiance_aspect_majority','service_aspect_majority','noise_aspect_majority'):
            fields[key]={'dtype':'category','description':'Source annotation; empty/unknown/no-majority values are not relabeled'}
    snapshot=f'{dataset_id}-sha256-{converted_sha}'
    manifest.update(name=name,description=note,release=('CEBaB-v1.1-40e68518' if dataset_id=='cebab' else 'source-sha256-'+hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:16]),snapshot_id=snapshot,adapter='structured',source_url=source_url,modalities=['text'],tasks=[task],labels=sorted(labels))
    manifest['adapter_config']={'path':str(output.relative_to(ROOT)),'format':fmt,'sha256':converted_sha,'mapping':{'id':'source_id','text':'description' if dataset_id=='cebab' else 'display_text',**({'question':'question'} if dataset_id=='qnli' else {})},'fields':fields,'source_files_sha256':hashes}
    manifest['coverage'].update(identity='resolved',source='verified',access='public',adapter='tested',preview='complete_target',complete_data='supported',publication='metadata_only',preview_count=100,total_count=count,blockers=['Public redistribution has not been approved; local inspection is supported.',*(['Train alternatives overlap; filter split before population statistics.'] if dataset_id=='cebab' else [])])
    manifest['rights']={'records':'CC-BY-4.0' if dataset_id=='cebab' else 'not_reviewed','annotations':'CC-BY-4.0' if dataset_id=='cebab' else 'not_reviewed','images':'not_applicable','external_provider':'local_only','source':source_url,'basis':'Author repository specifies CC BY 4.0; review-text and worker metadata not approved for static publication.' if dataset_id=='cebab' else 'GLUE/task text rights vary; public download does not establish redistribution permission.'}
    evidence={'kind':'verified_source_acquisition','source_url':source_download,'checked_at':'2026-09-22','sha256':hashes,'scope':note,'counts_by_split':dict(counts)}
    if evidence not in manifest.setdefault('evidence',[]):manifest['evidence'].append(evidence)
    path.write_text(yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True))
    dataset=Registry(ROOT).dataset(dataset_id)
    pack=build_preview(dataset,ROOT/'work/packs'/dataset_id,limit=100,max_bytes=50_000_000)
    adapter=get_adapter(dataset)
    snapshots=ROOT/'work/snapshots'
    build_parquet_snapshot((adapter._record(row,index) for index,row in enumerate(adapter._rows())),pack.fields,snapshots/dataset_id,root=snapshots,dataset_id=dataset_id,release_id=dataset.release,snapshot_id=snapshot,expected_count=count,population_scope='complete',max_bytes=2_000_000_000)
    receipt={'dataset_id':dataset_id,'source_sha256':hashes,'converted_sha256':converted_sha,'count':count,'counts_by_split':dict(counts),'distinct_upstream_ids':len(upstream_ids),'preview_records':len(pack.records),'scope':note}
    (ROOT/'reports'/f'{dataset_id}-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    import sys
    for identity in sys.argv[1:] or ['glue-cola','qnli','qqp','wnli','mrpc','cebab']:prepare(identity)
