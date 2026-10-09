"""Preserve every native FFHQ metadata object and its published checksums."""
from pathlib import Path
import json
import re
from urllib.parse import parse_qs,urlsplit
from . import converter,write_rows


@converter('ffhq_metadata')
def ffhq_metadata(params,inputs,output_dir,check):
    import ijson
    if set(inputs)!={'metadata'}:raise ValueError('FFHQ requires its single native metadata file')
    expected=params.get('count',70000)
    if type(expected) is not int or not 1<=expected<=70000:raise ValueError('Invalid FFHQ population bound')
    def rows():
        count=0;seen=set()
        with Path(inputs['metadata']).open('rb') as stream:
            for identity,native in ijson.kvitems(stream,'',use_float=True):
                check()
                if not re.fullmatch(r'[0-9]+',identity) or identity in seen or len(seen)>=expected:raise ValueError('FFHQ identity/count differs from declared population')
                seen.add(identity);image=native.get('image',{})
                url=urlsplit(image.get('file_url',''));query=parse_qs(url.query)
                if url.scheme!='https' or url.hostname!='drive.google.com' or url.path!='/uc' or url.username or url.password or set(query)!={'id'} or len(query['id'])!=1:
                    raise ValueError('FFHQ original image URL is outside the native Drive layout')
                source_id=query['id'][0]
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',source_id) or image.get('pixel_size')!=[1024,1024]:raise ValueError('FFHQ original image shape/identity changed')
                md5=image.get('file_md5','');pixels=image.get('pixel_md5','');size=image.get('file_size')
                if any(not re.fullmatch('[a-f0-9]{32}',value) for value in [md5,pixels]) or type(size) is not int or not 1<=size<=5_000_000:
                    raise ValueError('FFHQ original image checksums/size are invalid')
                count+=1
                yield {'source_id':identity,'native_metadata_json':json.dumps(native,ensure_ascii=False,separators=(',',':')),
                       'category':native.get('category'),'native_image_path':image['file_path'],'native_file_md5':md5,
                       'native_pixel_md5':pixels,'native_image_bytes':size,'native_license':native.get('metadata',{}).get('license'),
                       'media_ref':f'drive/{source_id}/{md5}/{pixels}/{size}.png'}
        if count!=expected:raise ValueError('FFHQ native population differs from declared count')
    result=write_rows(rows,Path(output_dir)/'ffhq.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'source_id','media':'media_ref'},'sequential_index':True}
    return result
