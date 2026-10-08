"""Native released collections; no generator or publisher code is executed."""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path, PurePosixPath
import zipfile

from . import converter, file_sha256, write_rows


@converter('pile_heldout')
def pile_heldout(params,inputs,output_dir,check):
    """Native author validation/test documents; no training-population inference."""
    import pyarrow as pa
    def rows():
        for split in ('validation','test'):
            path=inputs[split];source_sha=file_sha256(path)
            with path.open(encoding='utf-8',newline='') as stream:
                for ordinal,line in enumerate(stream):
                    check()
                    if len(line.encode())>16_000_000:raise ValueError('Native Pile document exceeds row limit')
                    native=json.loads(line)
                    if set(native)!={'text','meta'} or not isinstance(native['text'],str) or not isinstance(native['meta'],dict):
                        raise ValueError('Native Pile document schema changed')
                    # JSON retains the complete native metadata value, including
                    # heterogeneous component fields that cannot share Arrow structs.
                    yield {'source_id':f'{split}:{ordinal}','source_split':split,'source_row':ordinal,
                           'text':native['text'],'native_meta_json':json.dumps(native['meta'],ensure_ascii=False),
                           'pile_set_name':native['meta']['pile_set_name'],'source_file_sha256':source_sha}
    fields=['source_id','source_split','text','native_meta_json','pile_set_name','source_file_sha256']
    schema=pa.schema([(key,pa.string()) for key in fields]+[('source_row',pa.int64())])
    result=write_rows(rows,output_dir/'heldout.parquet','parquet',check,schema=schema)
    result['adapter_config']={'mapping':{'id':'source_id','text':'text','label':'pile_set_name'},'sequential_index':True,
                              'max_record_bytes':16_000_000}
    return result


@converter('objaverse_annotations')
def objaverse_annotations(params,inputs,output_dir,check):
    """All author 1.0 objects, native metadata and LVIS annotations by UID."""
    import gzip
    import re
    import pyarrow as pa
    def load(path,maximum):
        with gzip.open(path,'rb') as stream:
            payload=stream.read(maximum+1)
            if len(payload)>maximum:raise ValueError('Objaverse native metadata exceeds decoded budget')
            return json.loads(payload)
    paths=load(inputs['object_paths'],100_000_000);lvis=load(inputs['lvis_annotations'],20_000_000)
    if not isinstance(paths,dict) or not isinstance(lvis,dict):raise ValueError('Native Objaverse UID tables changed')
    categories={}
    for category,uids in lvis.items():
        if not isinstance(uids,list) or len(uids)!=len(set(uids)):raise ValueError('Duplicate native Objaverse LVIS UID')
        for uid in uids:
            if uid not in paths:raise ValueError('Native Objaverse LVIS annotation lacks an original object')
            categories.setdefault(uid,[]).append(category)
    def rows():
        seen=set()
        for key in params['metadata_order']:
            check();sha=file_sha256(inputs[key]);annotations=load(inputs[key],100_000_000)
            if not isinstance(annotations,dict):raise ValueError('Native Objaverse annotations must be keyed by UID')
            for uid,native in annotations.items():
                if uid not in paths or uid in seen or native['uid']!=uid:raise ValueError('Native Objaverse object/metadata join changed')
                path=paths[uid]
                if not re.fullmatch(r'glbs/[0-9]{3}-[0-9]{3}/[A-Za-z0-9]{16,64}\.glb',path) or path.rsplit('/',1)[-1]!=uid+'.glb':
                    raise ValueError('Unsafe or mismatched native Objaverse object path')
                seen.add(uid)
                yield {'source_id':uid,'media_ref':path,'name':native['name'],'description':native['description'],
                       'native_annotation_json':json.dumps(native,ensure_ascii=False),'native_lvis_categories':categories.get(uid,[]),
                       'license_slug':native['license'] if isinstance(native['license'],str) else native['license']['slug'],'face_count':native['faceCount'],
                       'vertex_count':native['vertexCount'],'source_metadata_sha256':sha}
        if seen!=set(paths):raise ValueError('Native Objaverse metadata does not cover the complete object population')
    fields=['source_id','media_ref','name','description','native_annotation_json','license_slug','source_metadata_sha256']
    schema=pa.schema([(key,pa.string()) for key in fields]+[('face_count',pa.int64()),('vertex_count',pa.int64()),('native_lvis_categories',pa.list_(pa.string()))])
    result=write_rows(rows,output_dir/'objects.parquet','parquet',check,schema=schema)
    result['adapter_config']={'mapping':{'id':'source_id','text':'name','label':'license_slug','media':'media_ref','media_modality':'model3d'},'sequential_index':True}
    return result


@converter('sorrybench_variants')
def sorrybench_variants(params,inputs,output_dir,check):
    """Retain each native base/variant instruction and all ordered conversation turns."""
    def rows():
        base_ids=None
        for key in params['source_order']:
            seen=set()
            with inputs[params.get('input_keys',{}).get(key,key)].open(encoding='utf-8') as stream:
                for ordinal,line in enumerate(stream):
                    if not line.strip():continue
                    native=json.loads(line);identity=native['question_id']
                    if identity in seen:raise ValueError('Duplicate SORRY-Bench question within a native variant')
                    seen.add(identity)
                    turns=native['turns']
                    if not isinstance(turns,list) or any(turn is not None and not isinstance(turn,str) for turn in turns):
                        raise ValueError('Native SORRY-Bench turns must remain ordered strings or nulls')
                    yield {'source_id':f'{key}:{identity}','source_file':key,'source_row':ordinal,
                           'native_question':native,'question_id':identity,'category':native['category'],
                           'prompt_style':native['prompt_style'],'turns':turns,
                           'text':'\n'.join(turns) if all(isinstance(turn,str) for turn in turns) else None,
                           'native_null_turns':sum(turn is None for turn in turns)}
            if base_ids is None:base_ids=seen
            elif seen!=base_ids:raise ValueError('SORRY-Bench native variant question membership changed')
    result=write_rows(rows,output_dir/'questions.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','text':'text'},'sequential_index':True}
    return result


@converter('fivek_renditions')
def fivek_renditions(params,inputs,output_dir,check):
    """All five native expert conditions with source cells and input references."""
    from html.parser import HTMLParser
    class Table(HTMLParser):
        def __init__(self):super().__init__();self.inside=False;self.rows=[]
        def handle_starttag(self,tag,attrs):
            if tag=='tr':self.inside=True;self.cells=[];self.links=[];self.text=[]
            if self.inside and tag in ('td','th'):self.text=[]
            if self.inside and tag=='a':
                link=dict(attrs).get('href')
                if link:self.links.append(link)
        def handle_data(self,data):
            if self.inside:self.text.append(data)
        def handle_endtag(self,tag):
            if self.inside and tag in ('td','th'):self.cells.append(''.join(self.text).strip())
            if self.inside and tag=='tr':self.rows.append((self.cells,self.links));self.inside=False
    parser=Table();parser.feed(inputs['source_page'].read_text())
    def rows():
        seen=set()
        for cells,links in parser.rows:
            raw=[link for link in links if link.startswith('img/dng/')]
            if not raw:continue
            if len(raw)!=1 or raw[0] in seen:raise ValueError('Duplicate or ambiguous FiveK input')
            _name(raw[0]);seen.add(raw[0])
            renditions=[link for link in links if link.startswith('img/tiff16_')]
            if len(renditions)!=5:raise ValueError('FiveK expert conditions differ from the native release')
            for link in renditions:
                _name(link)
                expert=link.split('/')[1].removeprefix('tiff16_')
                if expert not in 'abcde' or len(expert)!=1:raise ValueError('Unknown FiveK expert')
                yield {'source_id':link,'photo_id':cells[0],'expert':expert,'raw_input':raw[0],
                       'expert_renditions':renditions,'source_table_cells':cells,'media_ref':link}
    result=write_rows(rows,output_dir/'renditions.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','media':'media_ref'},'sequential_index':True}
    return result


@converter('snli_ve_native')
def snli_ve_native(params,inputs,output_dir,check):
    import gzip
    def rows():
        for split in ('train','dev','test'):
            seen=set();decoded=0
            with gzip.open(inputs[split],'rt',encoding='utf-8') as stream:
                for ordinal,line in enumerate(stream):
                    check();decoded+=len(line.encode())
                    if decoded>1_000_000_000:raise ValueError('Native SNLI-VE annotations exceed decoded budget')
                    if not line.strip():continue
                    native=json.loads(line);identity=native['pairID']
                    if identity in seen:raise ValueError('Duplicate native SNLI-VE pair ID')
                    seen.add(identity)
                    filename=_name(native['Flickr30K_ID'])
                    if not filename.endswith('.jpg'):filename+='.jpg'
                    yield {**native,'source_id':f'{split}:{identity}','source_split':split,'source_row':ordinal,
                           'media_ref':'flickr30k-images/'+filename}
    result=write_rows(rows,output_dir/'entailment.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','text':'sentence2','label':'gold_label'},'sequential_index':True}
    return result


@converter('oasis_normative')
def oasis_normative(params,inputs,output_dir,check):
    import hashlib
    import io
    with zipfile.ZipFile(inputs['media_archive']) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate native OASIS member names')
        images={PurePosixPath(name).stem:name for name in names if name.startswith('images/') and name.lower().endswith('.jpg')}
        if len(images)!=900:raise ValueError('OASIS release must contain its 900 original JPEGs')
        native=archive.read('OASIS.csv');corrected=archive.read('OASIS_bygender_CORRECTED_092617.csv')
        main=list(csv.DictReader(io.StringIO(native.decode('utf-8-sig'),newline='')))
        gender=list(csv.DictReader(io.StringIO(corrected.decode('utf-8-sig'),newline='')))
        by_id={row['']:row for row in gender}
        if len(by_id)!=len(gender):raise ValueError('Duplicate corrected OASIS normative ID')
        def rows():
            seen=set()
            for ordinal,row in enumerate(main):
                check();name=row['Theme'];join=name if name in images else name.rstrip()
                if join not in images or join in seen:raise ValueError('Missing or ambiguous native OASIS image join')
                seen.add(join)
                if row[''] not in by_id:raise ValueError('OASIS corrected gender table lacks a normative row')
                yield {'source_id':row[''],'source_row':ordinal,'native_norms':row,'native_corrected_gender_norms':by_id[row['']],
                       'theme':name,'category':row['Category'],'media_ref':images[join],
                       'join_trailing_whitespace_removed':join!=name,'source_norms_sha256':hashlib.sha256(native).hexdigest(),
                       'corrected_gender_norms_sha256':hashlib.sha256(corrected).hexdigest()}
            if len(seen)!=len(images) or len(main)!=len(gender):raise ValueError('OASIS native population membership differs')
        result=write_rows(rows,output_dir/'norms.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','text':'theme','label':'category','media':'media_ref'},'sequential_index':True,
                              'media_archive_sha256':file_sha256(inputs['media_archive'])}
    return result


@converter('spoken_wikipedia_sentences')
def spoken_wikipedia_sentences(params,inputs,output_dir,check):
    """All native sentence elements, retaining their token/phoneme XML and article provenance."""
    import hashlib
    import tarfile
    import xml.etree.ElementTree as ET
    import pyarrow as pa
    import sqlite3
    audio_indices={language:inputs['audio_index_'+language] for language in ('Dutch','English','German') if 'audio_index_'+language in inputs}
    if audio_indices and len(audio_indices)!=3:raise ValueError('Native audio requires all three declared language archives')
    audio_members={};audio_proofs={}
    for language,index in audio_indices.items():
        proof=json.loads((Path(index)/'receipt.json').read_text())
        if proof.get('format')!='atlas-remote-zip-deflate-tar-v1' or not proof.get('whole_native_tar_sha256_checked'):
            raise ValueError('Native article audio requires a verified complete TAR index')
        for name,sha in proof['checksums'].items():
            with (Path(index)/name).open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:raise ValueError('Native audio derivative checksum changed')
        with sqlite3.connect((Path(index)/'members.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
            audio_members[language]={name:(size,sha) for name,size,sha in db.execute('SELECT name,bytes,sha256 FROM members')}
        audio_proofs[language]=proof
    def read(archive,info):
        _name(info.name)
        if not info.isreg() or info.size>64_000_000:raise ValueError('Spoken Wikipedia annotation exceeds member limit')
        handle=archive.extractfile(info)
        if handle is None:raise ValueError('Missing native annotation member')
        with handle:return handle.read()
    def rows():
        for language in ('Dutch','English','German'):
            path=inputs[language]
            articles={}
            article_audio={}
            with tarfile.open(path,mode='r|xz') as archive:
                for info in archive:
                    check()
                    if info.name.endswith('/info.json'):
                        payload=read(archive,info);base=info.name.rsplit('/',1)[0]
                        articles[base]=payload.decode('utf-8')
                        if audio_indices:
                            native=audio_members[language].get(info.name.removeprefix('./'))
                            if native!=(len(payload),hashlib.sha256(payload).hexdigest()):
                                raise ValueError('Native full-audio and no-audio article metadata differ')
                            article_audio[base.removeprefix('./')]=[]
            if audio_indices:
                for name,(size,sha) in sorted(audio_members[language].items()):
                    if Path(name).suffix.lower() not in {'.ogg','.mp3','.wav','.flac'}:continue
                    base=name.rsplit('/',1)[0]
                    if base in article_audio:
                        article_audio[base].append({'ref':f'audio/{language}/{name}','member':name,'bytes':size,'sha256':sha,
                            'source_tar_sha256':audio_proofs[language]['source_sha256']})
            with tarfile.open(path,mode='r|xz') as archive:
                for info in archive:
                    check()
                    if not info.name.endswith('/aligned.swc'):continue
                    payload=read(archive,info)
                    upper=payload.upper()
                    if b'<!DOCTYPE' in upper or b'<!ENTITY' in upper:raise ValueError('XML entities are not admitted')
                    article=ET.fromstring(payload)
                    if article.tag!='article':raise ValueError('Unexpected native SWC XML root')
                    digest=hashlib.sha256(payload).hexdigest()
                    if audio_indices and audio_members[language].get(info.name.removeprefix('./'))!=(len(payload),digest):
                        raise ValueError('Native full-audio and no-audio aligned sentence source differs')
                    base=info.name.rsplit('/',1)[0]
                    attribution=articles.get(base)
                    if attribution is None:raise ValueError('Native SWC article has no info.json join')
                    for ordinal,sentence in enumerate(article.iter('s')):
                        tokens=list(sentence.iter('n'))
                        row={'source_id':f'{language}:{info.name}:sentence:{ordinal}','language':language,
                               'article_path':base,'sentence_ordinal':ordinal,'native_token_count':len(tokens),
                               'normalized_text':' '.join(''.join(token.itertext()) for token in tokens),
                               'native_sentence_attributes':json.dumps(sentence.attrib,ensure_ascii=False),
                               'native_alignment_xml':ET.tostring(sentence,encoding='unicode'),
                               'article_info_json':attribution,'source_swc_sha256':digest,
                               'media_availability':'Audio not acquired; native aligned sentence annotations only'}
                        if audio_indices:
                            audio=article_audio.get(base.removeprefix('./'),[])
                            row.update(media_refs=[item['ref'] for item in audio],native_audio_json=json.dumps(audio,ensure_ascii=False,sort_keys=True),
                                media_availability='Complete native article audio parts available by bounded original access; sentence clips are not created' if audio else 'Native aligned article has no supported released audio member')
                        yield row
    fields=['source_id','language','article_path','normalized_text','native_sentence_attributes','native_alignment_xml',
            'article_info_json','source_swc_sha256','media_availability']
    schema=pa.schema([(key,pa.string()) for key in fields]+[('sentence_ordinal',pa.int64()),('native_token_count',pa.int32())])
    if audio_indices:schema=pa.schema(list(schema)+[('media_refs',pa.list_(pa.string())),('native_audio_json',pa.string())])
    result=write_rows(rows,output_dir/'sentences.parquet','parquet',check,schema=schema)
    result['adapter_config']={'mapping':{'id':'source_id','text':'normalized_text'},'sequential_index':True}
    if audio_indices:
        result['adapter_config']['mapping'].update(media='media_refs',media_modality='audio')
    return result


def _name(value):
    path=PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '\\' in value:
        raise ValueError('Unsafe native collection filename')
    return value


@converter('shapeworld_examples')
def shapeworld_examples(params,inputs,output_dir,check):
    """The author's fixed examples, including every caption alternative and world model."""
    archive_path=inputs['media_archive']
    with zipfile.ZipFile(archive_path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ShapeWorld archive members')
        configs=sorted(name.rsplit('/',1)[0] for name in names if name.endswith('/world_model.json') and '/examples/' in name)
        def read(name):
            info=archive.getinfo(_name(name))
            if info.file_size>20_000_000:raise ValueError('ShapeWorld annotation member exceeds limit')
            return archive.read(info).decode('utf-8')
        def rows():
            for base in configs:
                check()
                models=json.loads(read(base+'/world_model.json'))
                if not isinstance(models,list):raise ValueError('ShapeWorld world models must be an array')
                count=len(models)
                fields={}
                for name in names:
                    if name.rsplit('/',1)[0]!=base:continue
                    field=PurePosixPath(name).stem
                    if name.endswith('.txt'):
                        raw=read(name)
                        # This is the publisher's serialization: captions with
                        # alternatives use blank-line-separated world groups.
                        values=raw.removesuffix('\n\n').split('\n\n') if '\n\n' in raw else raw.splitlines()
                        if len(values)!=count:raise ValueError('ShapeWorld native row counts disagree')
                        fields[field]=values
                    elif name.endswith('_model.json'):
                        values=json.loads(read(name))
                        if not isinstance(values,list) or len(values)!=count:raise ValueError('ShapeWorld model row counts disagree')
                        fields[field]=values
                for index in range(count):
                    media=_name(f'{base}/world-{index}.png')
                    if media not in names:raise ValueError('ShapeWorld native world image is absent')
                    native={key:values[index] for key,values in fields.items()}
                    caption=native.get('caption')
                    alternatives=int(native.get('alternatives','1'))
                    if caption is not None:
                        captions=caption.splitlines()
                        agreement=native.get('agreement','').split(';')
                        if len(captions)!=alternatives or len(agreement)!=alternatives:
                            raise ValueError('ShapeWorld caption/agreement alternatives disagree')
                        native.update(captions=captions,agreements=[float(value) for value in agreement])
                    yield {**native,'source_id':f'{base}:{index}','configuration':base.split('/examples/',1)[1],
                           'source_row':index,'media_ref':media}
        result=write_rows(rows,output_dir/'examples.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','media':'media_ref','text':'caption','choices':'captions'},
                              'media_archive_sha256':file_sha256(archive_path)}
    return result


@converter('flickr30k_mirror')
def flickr30k_mirror(params,inputs,output_dir,check):
    """Preserve the mirror's native CSV and safely decode its ordered caption lists."""
    def rows():
        seen=set()
        with inputs['annotation_csv'].open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                name=_name(row['filename'])
                if name in seen:raise ValueError('Duplicate Flickr30K image row')
                seen.add(name)
                captions=ast.literal_eval(row['raw'])
                sentence_ids=ast.literal_eval(row['sentids'])
                if not isinstance(captions,list) or any(not isinstance(value,str) for value in captions):
                    raise ValueError('Flickr30K captions must be an ordered string list')
                if not isinstance(sentence_ids,list) or len(sentence_ids)!=len(captions):
                    raise ValueError('Flickr30K caption and sentence ID counts differ')
                yield {**row,'captions':captions,'sentence_ids':sentence_ids,'caption_text':'\n'.join(captions)}
    return write_rows(rows,output_dir/'annotations.jsonl','jsonl',check)


@converter('miap_images')
def miap_images(params,inputs,output_dir,check):
    """One row per native image key, retaining all native person-box annotations."""
    def rows():
        all_keys=set()
        for split in ('train','val','test'):
            boxes={}
            with inputs['boxes_'+split].open(encoding='utf-8-sig',newline='') as stream:
                for ordinal,row in enumerate(csv.DictReader(stream)):
                    boxes.setdefault(row['ImageID'],[]).append({**row,'source_box_row':ordinal})
            used=set()
            for ordinal,key in enumerate(inputs['images_'+split].read_text().splitlines()):
                _name(key)
                parts=key.split('/')
                if len(parts)!=2 or parts[0] not in ('train','validation','test'):
                    raise ValueError('Invalid native MIAP image key')
                if key in all_keys:raise ValueError('Duplicate MIAP image key')
                all_keys.add(key)
                image_id=parts[1]
                if image_id not in boxes:raise ValueError('MIAP image key has no native box annotations')
                used.add(image_id)
                native_boxes=boxes[image_id]
                yield {'source_id':key,'ImageID':image_id,'image_key':key,'split':split,'source_image_row':ordinal,
                       'boxes':native_boxes,'box_count':len(native_boxes),
                       'gender_presentations':list(dict.fromkeys(row['GenderPresentation'] for row in native_boxes)),
                       'age_presentations':list(dict.fromkeys(row['AgePresentation'] for row in native_boxes)),
                       'media_ref':key+'.jpg'}
            if used!=set(boxes):raise ValueError('Unmatched native MIAP box image IDs')
    result=write_rows(rows,output_dir/'images.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','media':'media_ref'}}
    return result
