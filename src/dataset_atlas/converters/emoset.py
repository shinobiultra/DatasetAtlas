"""Preserve the native EmoSet 118K splits, annotations and original access index."""
from pathlib import Path
import json
import zipfile
from . import converter,write_rows,file_sha256
from dataset_atlas.adapters.core import _safe_relative
from dataset_atlas.storage.hash_ranges import block_manifest
from dataset_atlas.storage.indexed_zip import build_zip_index


@converter('emoset_native')
def emoset_native(params,inputs,output_dir,check):
    if set(inputs)!={'archive'}:raise ValueError('EmoSet requires the native archive')
    source=Path(inputs['archive']);output_dir=Path(output_dir);expected=params.get('count',118102)
    if type(expected) is not int or not 1<=expected<=118102:raise ValueError('Invalid EmoSet native population bound')
    output_dir.mkdir(parents=True,exist_ok=True)
    sha=file_sha256(source)
    if params.get('source_sha256')!=sha:raise ValueError('EmoSet original differs from pinned whole-file SHA-256')
    remote={**block_manifest(source,block_bytes=1<<20,check=check),'url':params['url'],'allowed_hosts':params['allowed_hosts']}
    if remote['source_sha256']!=sha:raise ValueError('EmoSet original changed during block hashing')
    index=output_dir/'native-index'
    if index.exists():
        if {p.name for p in index.iterdir()}!={'receipt.json','members.sqlite'}:raise ValueError('Existing EmoSet index is incomplete or has undeclared files')
        if (index/'receipt.json').stat().st_size>2_000_000 or (index/'members.sqlite').stat().st_size>200_000_000:raise ValueError('Existing EmoSet index exceeds bounds')
        proof=json.loads((index/'receipt.json').read_text())
        if (proof.get('format'),proof.get('source_sha256'),proof.get('source_bytes'),proof.get('remote'))!=('atlas-remote-zip-v1',sha,source.stat().st_size,remote):
            raise ValueError('Existing EmoSet index differs from pinned original')
        if file_sha256(index/'members.sqlite')!=proof.get('checksums',{}).get('members.sqlite'):raise ValueError('Existing EmoSet index checksum changed')
    else:
        proof=build_zip_index(source,index,source_sha256=sha,remote=remote,max_input_bytes=params.get('max_input_bytes',12_000_000_000),cancel=check)
    totals={};annotation_names=set();image_names=set()
    with zipfile.ZipFile(source) as archive:
        members={i.filename:i for i in archive.infolist() if not i.is_dir()}
        if len(members)!=proof['members']:raise ValueError('EmoSet has duplicate native archive names')
        protocol={}
        for base in ('info.json','train.json','val.json','test.json'):
            names=[name for name in members if Path(name).name==base]
            if len(names)!=1:raise ValueError('EmoSet protocol table is missing or ambiguous')
            name=names[0]
            if members[name].file_size>20_000_000:raise ValueError('EmoSet protocol table exceeds bound')
            protocol[base]=(name,json.loads(archive.read(name)))
        info=protocol['info.json'][1]
        if not isinstance(info,dict) or set(info)!={'label2idx','idx2label'}:raise ValueError('Unknown EmoSet label-map structure')
        def rows():
            seen=set();count=0
            for split in ('train','val','test'):
                table_name,table=protocol[split+'.json']
                if not isinstance(table,list) or len(table)>expected:raise ValueError('Invalid native EmoSet split table')
                totals[split]=len(table)
                for ordinal,row in enumerate(table):
                    check()
                    if not isinstance(row,list) or len(row)!=3 or not all(isinstance(x,str) for x in row):raise ValueError('Unknown EmoSet native split-row structure')
                    label,image_name,annotation_name=row
                    image_name=_safe_relative(image_name);annotation_name=_safe_relative(annotation_name)
                    if image_name not in members or annotation_name not in members or not image_name.endswith('.jpg') or not annotation_name.endswith('.json'):
                        raise ValueError('EmoSet split references an absent native member')
                    if members[annotation_name].file_size>1_000_000:raise ValueError('EmoSet annotation exceeds bound')
                    native=json.loads(archive.read(annotation_name));identity=native.get('image_id') if isinstance(native,dict) else None
                    if not isinstance(identity,str) or identity!=Path(image_name).stem or native.get('emotion')!=label:
                        raise ValueError('EmoSet native image identity/emotion join differs')
                    if identity in seen or image_name in image_names or annotation_name in annotation_names:raise ValueError('Duplicate native EmoSet split membership')
                    if label not in info['label2idx']:raise ValueError('EmoSet emotion is absent from native label map')
                    seen.add(identity);image_names.add(image_name);annotation_names.add(annotation_name);count+=1
                    if count>expected:raise ValueError('EmoSet population exceeds declaration')
                    result={'source_id':identity,'split':split,'split_ordinal':ordinal,'emotion':label,'native_split_table':table_name,
                            'native_split_row_json':json.dumps(row,ensure_ascii=False,separators=(',',':')),
                            'native_annotation_json':json.dumps(native,ensure_ascii=False,separators=(',',':')),
                            'native_annotation_path':annotation_name,'native_image_path':image_name,
                            'native_label_maps_json':json.dumps(info,ensure_ascii=False,separators=(',',':')),'media_ref':image_name}
                    for key,value in native.items():result['attribute_'+key]=value
                    yield result
            json_members={name for name in members if name.endswith('.json')} - {value[0] for value in protocol.values()}
            jpg_members={name for name in members if name.endswith('.jpg')}
            if count!=expected or image_names!=jpg_members or annotation_names!=json_members:
                raise ValueError('EmoSet full annotation/image population differs from pinned native split membership')
            if set(members)!=(image_names|annotation_names|{value[0] for value in protocol.values()}):raise ValueError('Undeclared EmoSet native archive members')
        result=write_rows(rows,output_dir/'emoset.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','media':'media_ref','split':'split'},'sequential_index':True,'native_zip_index':str(index)}
    result['native_source_checks']={'native_population':result['count'],'split_counts':totals,'indexed_members':proof['members'],
       'whole_source_sha256_checked':True,'publisher_checksum_checked':False,'native_member_crc_and_sha256_checked':True}
    result['derived_sources']=[{'path':str(path),'bytes':path.stat().st_size,'sha256':file_sha256(path),
                               'kind':'verified native ZIP original retrieval index'} for path in sorted(index.iterdir()) if path.is_file()]
    return result
