"""Native TID2013 images and score tables; archive programs are never executed."""
import hashlib,io,math,os,re,select,shutil,subprocess,time,zipfile,zlib
from decimal import Decimal
from pathlib import Path,PurePosixPath

from PIL import Image

from . import converter,file_sha256,write_rows
from dataset_atlas.adapters.core import _safe_relative


def _read_decoder(stream,size,check):
    """Read a bounded segment while observing cancellation even on a stalled pipe."""
    parts=[];remaining=size
    while remaining:
        check()
        if not select.select([stream],[],[],0.1)[0]:continue
        part=os.read(stream.fileno(),min(remaining,1024*1024))
        if not part:break
        parts.append(part);remaining-=len(part)
    check()
    return b''.join(parts)


def _members(source,check,max_expanded_bytes):
    import rarfile
    seen=set();expanded=0;selected=[]
    with rarfile.RarFile(source) as archive:
        for entry in archive.infolist():
            check();name=_safe_relative(entry.filename.rstrip('/'))
            if name in seen:raise ValueError('Duplicate native archive member')
            seen.add(name)
            if len(seen)>10_000:raise ValueError('Native archive member inventory exceeds its bound')
            if entry.isdir():continue
            if entry.is_symlink() or getattr(entry,'file_redir',None) or entry.needs_password():raise ValueError('Native archive requires unencrypted regular files without links')
            if type(entry.file_size) is not int or not 0<=entry.file_size<=20_000_000:raise ValueError('Native archive member exceeds its byte bound')
            expanded+=entry.file_size
            if expanded>max_expanded_bytes:raise ValueError('Native archive exceeds its expansion bound')
            if name.lower().endswith(('.bmp','.txt')):selected.append((name,entry.file_size,entry.CRC))
    if not selected:raise ValueError('Native archive contains no images or tables')
    command=shutil.which('7zz') or shutil.which('7z')
    if command is None:raise ValueError('Native RAR decoding requires the system 7-Zip command')
    # Stream exact selected members in native archive order. Nothing is extracted
    # to the filesystem, and every segment is checked against its native CRC.
    process=subprocess.Popen([command,'x','-so','-bd','-bb0','-mmt=1','-p-','-spd','--',str(source),*[name for name,_,_ in selected]],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        if process.stdout is None:raise ValueError('Native archive decoder stream is unavailable')
        for name,size,crc in selected:
            check();data=_read_decoder(process.stdout,size,check)
            if len(data)!=size or zlib.crc32(data)&0xffffffff!=crc:raise ValueError('Native archive decoder member length, order or CRC changed')
            yield name,data
        if _read_decoder(process.stdout,1,check):raise ValueError('Native archive decoder returned extra bytes or an error')
        deadline=time.monotonic()+30
        while process.poll() is None:
            check()
            if time.monotonic()>deadline:raise ValueError('Native archive decoder did not exit within its bound')
            time.sleep(0.1)
        check()
        if process.returncode!=0:raise ValueError('Native archive decoder returned extra bytes or an error')
    finally:
        if process.poll() is None:process.kill()
        process.wait(timeout=30)
        if process.stdout is not None:process.stdout.close()


@converter('tid2013_native')
def tid2013_native(params,inputs,output_dir,check):
    source=Path(inputs['archive_path']);output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    maximum=params.get('max_expanded_bytes',3_000_000_000)
    if type(maximum) is not int or not 1<=maximum<=4_000_000_000 or source.stat().st_size>1_000_000_000:
        raise ValueError('Native TID2013 input or expansion limit is invalid')
    archive_sha=file_sha256(source);native={};images={};tables={};zip_path=output_dir/'native-images-and-tables.zip'
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as derived:
        for name,data in _members(source,check,maximum):
            digest=hashlib.sha256(data).hexdigest();native[name]={'sha256':digest,'bytes':len(data)}
            if name.lower().endswith('.bmp'):
                if not data.startswith(b'BM'):raise ValueError('Native TID2013 image is not a BMP')
                with Image.open(io.BytesIO(data)) as image:
                    if image.format!='BMP' or image.width*image.height>50_000_000:raise ValueError('Native BMP exceeds its decoder bound')
                    image.load();images[name]={'width':image.width,'height':image.height,'mode':image.mode}
            elif name.endswith('.txt'):
                if len(data)>1_000_000:raise ValueError('Native TID2013 table exceeds its bound')
                tables[name]=data.decode('utf-8-sig').splitlines(keepends=True)
            else:continue
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED
            derived.writestr(info,data)
    references={};distorted={}
    for name in images:
        leaf=PurePosixPath(name).name.lower()
        match=re.fullmatch(r'i(\d{2})_(\d{2})_([1-5])\.bmp',leaf)
        if match:
            key=leaf
            if key in distorted:raise ValueError('Duplicate native distorted image name')
            distorted[key]=(name,*map(int,match.groups()))
        elif (match:=re.fullmatch(r'i(\d{2})\.bmp',leaf)):
            identity=int(match[1])
            if identity in references:raise ValueError('Duplicate native reference image identity')
            references[identity]=name
        else:raise ValueError('Unknown native TID2013 image naming scheme')
    expected=params.get('distorted_count',3000);reference_count=params.get('reference_count',25)
    if len(distorted)!=expected or len(references)!=reference_count or len(images)!=expected+reference_count:
        raise ValueError('Native TID2013 image populations differ from the pinned release')
    named=tables.get('mos_with_names.txt');scores=tables.get('mos.txt');deviations=tables.get('mos_std.txt')
    if named is None or scores is None or deviations is None or any(len(value)!=expected for value in tables.values()):
        raise ValueError('Native TID2013 score table populations differ')
    numeric={}
    for name,lines in tables.items():
        if name=='mos_with_names.txt':continue
        values=[]
        for line in lines:
            if len(line.split())!=1:raise ValueError('Native TID2013 numeric table shape changed')
            number=float(line);values.append(number if math.isfinite(number) else None)
        numeric[name]=values
    order=[];used=set()
    for ordinal,line in enumerate(named):
        cells=line.split()
        if len(cells)!=2 or cells[1].lower() not in distorted or cells[1].lower() in used:
            raise ValueError('Native TID2013 MOS/image join is duplicate or absent')
        if Decimal(cells[0])!=Decimal(scores[ordinal].strip()):raise ValueError('Native named and unnamed MOS tables disagree')
        used.add(cells[1].lower());order.append(cells[1].lower())
    if used!=set(distorted):raise ValueError('Native TID2013 distorted images are unjoined')
    def rows():
        for ordinal,key in enumerate(order):
            name,reference,distortion,level=distorted[key]
            if reference not in references:raise ValueError('Native distorted image has no reference')
            reference_name=references[reference]
            if images[name]!=images[reference_name]:raise ValueError('Native distorted and reference image layouts disagree')
            yield {'image_name':key,'native_mos_row':ordinal,'reference_index':reference,'distortion_type_index':distortion,'distortion_level_index':level,
                'native_image_member':name,'native_reference_member':reference_name,'image_sha256':native[name]['sha256'],
                'reference_image_sha256':native[reference_name]['sha256'],'native_archive_sha256':archive_sha,**images[name],
                'mos':numeric['mos.txt'][ordinal],'mos_std':numeric['mos_std.txt'][ordinal],
                'native_table_rows':{table:{'line':lines[ordinal],'table_sha256':native[table]['sha256']} for table,lines in tables.items()},
                'native_metric_values':{table:value[ordinal] for table,value in numeric.items() if table.startswith('metrics_values/')},
                'media_refs':['zip/native/'+name,'zip/native/'+reference_name]}
    result=write_rows(rows,output_dir/'records.jsonl','jsonl',check)
    result['adapter_config']={'native_media_archive_path':str(zip_path),'derived_archive_checksums':{'native_media_archive_path':file_sha256(zip_path)},
        'local_archives':{'native':{'path_key':'native_media_archive_path'}},'annotations':[{'path_key':'path','format':'jsonl','split':'native',
            'media_archive':'native','media_templates':['{native_image_member}','{native_reference_member}']}],
        'media_sha256_fields':[{'prefix':'zip/native/','member_field':'native_image_member','sha256_field':'image_sha256'},
            {'prefix':'zip/native/','member_field':'native_reference_member','sha256_field':'reference_image_sha256'}],
        'mapping':{'id':'image_name','media':'media_refs'},'fields':{'mos':{'dtype':'number','description':'Authors mean opinion score; exact native value.'},
        'mos_std':{'dtype':'number','description':'Authors mos_std.txt value; native table lines retained.'},
        'distortion_type_index':{'dtype':'number','description':'Native filename distortion index; no inferred category names.'}}}
    result['native_scope_counts']={'distorted_images':len(distorted),'reference_images':len(references),'native_score_tables':len(tables),
        'native_archive_files_hashed':len(native),'native_image_and_table_bytes_preserved':sum(int(item['bytes']) for name,item in native.items() if name in images or name in tables),
        'derived_media_archive_bytes':zip_path.stat().st_size,'derived_media_archive_sha256':result['adapter_config']['derived_archive_checksums']['native_media_archive_path']}
    return result
