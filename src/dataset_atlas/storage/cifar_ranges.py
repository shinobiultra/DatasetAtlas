"""Exact CIFAR-C RGB array rows through whole-original SHA-256 block pins."""
from pathlib import Path
import hashlib
import io
import json
import re
import numpy as np
from PIL import Image
from dataset_atlas.adapters.corruptions import CIFARCorruptionsAdapter
from dataset_atlas.models import Dataset
from .hash_ranges import block_manifest,HashPinnedRangeReader
from .indexed_tar import _file_identity


def build_cifar_index(source,output,*,source_sha256,url,allowed_hosts,config=None,cancel=None):
    source=Path(source);output=Path(output)
    if source.stat().st_size>4_000_000_000:raise ValueError('Native CIFAR-C archive exceeds source bound')
    before=_file_identity(source)
    check=cancel or (lambda:None)
    remote={**block_manifest(source,1<<20,check),'url':url,'allowed_hosts':allowed_hosts}
    if remote['source_sha256']!=source_sha256:raise ValueError('Native CIFAR-C source checksum changed')
    adapter=CIFARCorruptionsAdapter(Dataset(id='native-cifar-index',name='Native CIFAR index',adapter='cifar_c_npy',
       adapter_config={**(config or {}),'path':str(source),'sha256':source_sha256}))
    arrays=adapter._arrays();entries={}
    for name,array in arrays.items():
        check();offset=int(array.offset);size=int(array.nbytes)
        if not 0<=offset<offset+size<=remote['bytes']:raise ValueError('Native CIFAR-C array lies outside archive')
        entries[name]={'offset':offset,'shape':list(array.shape),'dtype':'uint8','bytes':size}
    if _file_identity(source)!=before:raise ValueError('Native CIFAR-C original changed during indexing')
    result={'format':'atlas-native-cifar-c-v1','source_sha256':source_sha256,'source_bytes':remote['bytes'],'remote':remote,
            'arrays':entries,'labels_sha256':hashlib.sha256(adapter._labels.tobytes()).hexdigest(),
            'examples_per_severity':adapter._per_severity,'records':adapter.count,
            'representation':'Lossless PNG of original C-order uint8 RGB 32×32 array row; no resizing, normalization or pixel changes.'}
    output.mkdir(parents=True,exist_ok=False);(output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def read_cifar_row(index,asset_ref,*,max_bytes=1_000_000,transfer_bytes=16_000_000,cache=None,cancel=None,reader_factory=None):
    path=Path(index)/'receipt.json'
    if path.stat().st_size>2_000_000:raise ValueError('Native CIFAR-C receipt exceeds bounds')
    receipt=json.loads(path.read_text())
    match=re.fullmatch(r'([a-z_]+)/([0-9]{1,7})\.png',asset_ref)
    if receipt.get('format')!='atlas-native-cifar-c-v1' or not match:raise ValueError('Invalid native CIFAR-C row reference')
    remote=receipt['remote'];spec=receipt['arrays'].get(match[1]);row=int(match[2])
    if remote['source_sha256']!=receipt['source_sha256'] or remote['bytes']!=receipt['source_bytes']:raise ValueError('Native CIFAR-C source identity differs')
    if not spec or spec.get('dtype')!='uint8' or spec['shape'][1:]!=[32,32,3] or not 1<=spec['shape'][0]<=1_000_000 or not 0<=row<spec['shape'][0]:
        raise ValueError('Native CIFAR-C row/shape lies outside bounds')
    if spec['bytes']!=spec['shape'][0]*3072 or not 0<=spec['offset']<spec['offset']+spec['bytes']<=remote['bytes']:
        raise ValueError('Native CIFAR-C array offset/length changed')
    factory=reader_factory or HashPinnedRangeReader
    with factory(remote['url'],size=remote['bytes'],source_sha256=receipt['source_sha256'],block_bytes=remote['block_bytes'],
         block_sha256=remote['block_sha256'],allowed_hosts=remote['allowed_hosts'],byte_budget=transfer_bytes,cache=cache,cancel=cancel) as source:
        source.seek(spec['offset']+row*3072);pixels=source.read(3072);transferred=source.bytes_fetched
    if len(pixels)!=3072:raise ValueError('Truncated native CIFAR-C RGB row')
    check=cancel or (lambda:None);check()
    stream=io.BytesIO();Image.fromarray(np.frombuffer(pixels,dtype=np.uint8).reshape(32,32,3)).save(stream,format='PNG');data=stream.getvalue()
    if len(data)>max_bytes:raise ValueError('Native CIFAR-C PNG exceeds output bound')
    return data,{'sha256':hashlib.sha256(data).hexdigest(),'source_sha256':receipt['source_sha256'],'native_rgb_sha256':hashlib.sha256(pixels).hexdigest(),
                'transferred_bytes':transferred,'bytes':len(data),'fingerprint_type':'sha256-blocks','media_type':'image/png',
                'representation':receipt['representation']}


def retire_cifar_archive(root,dataset_id,*,max_transfer_bytes=20_000_000,execute=False):
    """Pin previews, verify every canonical row, install routes, then unlink owned copies."""
    import os
    import pyarrow.parquet as pq
    from dataset_atlas.preparation import PreparationManager,atomic
    from dataset_atlas.preparation.slots import try_writer_slot
    from dataset_atlas.registry import Registry
    from .compact import pin_preview_originals,read_compact
    from .indexed_tar import route_path
    from .retention import _local_config_path
    if dataset_id not in {'cifar-10-c','cifar-100-c'}:raise ValueError('Only pinned native CIFAR-C releases are supported')
    if type(max_transfer_bytes) is not int or not 1<=max_transfer_bytes<=100_000_000:raise ValueError('Native CIFAR-C transfer cap must be within 1..100 MB')
    root=Path(root).resolve();manager=PreparationManager(root);lease=try_writer_slot(manager.directory,dataset_id)
    if lease is None:raise RuntimeError('A preparation owns the source writer')
    def strings(v):
        if isinstance(v,str):yield v
        elif isinstance(v,dict):
            for x in v.values():yield from strings(x)
        elif isinstance(v,list):
            for x in v:yield from strings(x)
    with lease:
        registry=Registry(root);dataset=registry.dataset(dataset_id)
        if dataset.adapter!='cifar_c_npy':raise ValueError('Native CIFAR-C adapter required')
        source=Path(dataset.adapter_config['path'])
        if source.is_symlink():raise ValueError('Native source retirement cannot follow symlinks')
        source=source.resolve();owned=[root/'work/prepared',root/'work/sources',root/'work/source-objects']
        if not source.is_file() or not any(source.is_relative_to(p) for p in owned):raise ValueError('Native CIFAR-C source is outside acquired directories')
        file=next(f for f in dataset.adapter_config['source_files'] if Path(f['path']).resolve()==source)
        before=_file_identity(source);index=root/'work/original-access'/('cifar-c-'+file['sha256'])
        base=(root/'work/original-access').resolve()
        if index.is_symlink() or not index.resolve().is_relative_to(base):raise ValueError('Native CIFAR-C index is outside configured root')
        if index.exists():
            receipt_path=index/'receipt.json'
            if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size>2_000_000:raise ValueError('Invalid native CIFAR-C index receipt')
            proof=json.loads(receipt_path.read_text())
            if (proof['source_sha256'],proof['remote']['url'])!=(file['sha256'],file['url']):raise ValueError('Existing native CIFAR-C index identity differs')
        else:
            proof=build_cifar_index(source,index,source_sha256=file['sha256'],url=file['url'],allowed_hosts=['zenodo.org'],config=dataset.adapter_config)
        # Resumption verifies all block pins against the acquired original again.
        current_blocks=block_manifest(source,proof['remote']['block_bytes'])
        if any(current_blocks[k]!=proof['remote'][k] for k in current_blocks):raise ValueError('Native CIFAR-C source or block checksums changed')
        pin_preview_originals(root,dataset_id,max_input_bytes=5_000_000,max_output_bytes=5_000_000)
        adapter=CIFARCorruptionsAdapter(dataset);arrays=adapter._arrays();routes=[];checked=0;previews=0
        expected_arrays={name:{'offset':int(a.offset),'shape':list(a.shape),'dtype':'uint8','bytes':int(a.nbytes)} for name,a in arrays.items()}
        if expected_arrays!=proof['arrays']:raise ValueError('Native CIFAR-C array index changed')
        for version,pack_path,snapshot in registry.versions(dataset_id):
            values=set(strings(version.adapter_config));uses_source=False
            for value in values:
                p=_local_config_path(root,value)
                if p is not None and p.is_file() and p.samefile(source):uses_source=True
            if uses_source and file['sha256'] not in values:raise ValueError('Retained CIFAR-C source dependency lacks verified source identity')
            if file['sha256'] not in values:continue
            if not snapshot.is_dir():
                if pack_path.is_file():raise ValueError('Retained CIFAR-C preview has no complete canonical snapshot')
                continue
            manifest=json.loads((snapshot/'manifest.json').read_text());table=snapshot/'records.parquet'
            with table.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=manifest['checksums']['records.parquet']:raise ValueError('Canonical CIFAR-C snapshot checksum changed')
            count=0;seen=set()
            for batch in pq.ParquetFile(table).iter_batches(columns=['record_json'],batch_size=256):
                for value in batch.column(0).to_pylist():
                    record=json.loads(value);native=record['source'];name=native['corruption']
                    if any(type(native[k]) is not int for k in ['severity','original_test_index','label']) or not 1<=native['severity']<=int(adapter.config.get('severities',5)):
                        raise ValueError('Canonical CIFAR-C severity/index/label is not a native integer')
                    ordinal=(native['severity']-1)*adapter._per_severity+native['original_test_index']
                    if name not in arrays or not 0<=native['original_test_index']<adapter._per_severity or not 0<=ordinal<len(arrays[name]) or native['label']!=int(adapter._labels[native['original_test_index']]):raise ValueError('Canonical CIFAR-C row differs from native array membership')
                    key=(name,ordinal)
                    if key in seen or len(record['assets'])!=1 or record['assets'][0]['uri']!=f'{name}/{ordinal}.png':raise ValueError('Canonical CIFAR-C media identity differs')
                    seen.add(key);count+=1
            if count!=proof['records']:raise ValueError('Canonical CIFAR-C population differs from native arrays')
            pack=json.loads(pack_path.read_text())
            previews+=len(pack['records']);checked+=count
            for record in pack['records']:
                for asset in record['assets']:
                    ref=asset['metadata'].get('source_ref') or asset['uri']
                    match=re.fullmatch(r'([a-z_]+)/([0-9]+)\.png',ref)
                    if not match:raise ValueError('Native CIFAR-C preview reference changed')
                    original=read_compact(root,version.id,version.snapshot_id,ref,1_000_000)
                    if not original or original[2]['representation']!='original' or not original[2]['protected_preview']:raise ValueError('Original CIFAR-C preview is not protected')
                    with Image.open(io.BytesIO(original[0])) as image:
                        if not np.array_equal(np.asarray(image),np.asarray(arrays[match[1]][int(match[2])])):raise ValueError('Native CIFAR-C preview pixels changed')
            receipt_sha=hashlib.sha256((index/'receipt.json').read_bytes()).hexdigest()
            config={'dataset_id':version.id,'snapshot_id':version.snapshot_id,'archives':[{'index':index.name,'receipt_sha256':receipt_sha,'asset_prefix':'','member_prefix':''}]}
            routes.append((route_path(root,version.id,version.snapshot_id),config))
        if not routes:raise ValueError('Native CIFAR-C retirement has no retained complete snapshot')
        transfer=0;probes=[];names=sorted(arrays)
        for name,ordinal in [(names[0],0),(names[len(names)//2],len(arrays[names[0]])//2),(names[-1],len(arrays[names[-1]])-1)]:
            data,evidence=read_cifar_row(index,f'{name}/{ordinal}.png',transfer_bytes=max_transfer_bytes-transfer);transfer+=evidence['transferred_bytes']
            with Image.open(io.BytesIO(data)) as image:
                if not np.array_equal(np.asarray(image),np.asarray(arrays[name][ordinal])):raise ValueError('Cold native CIFAR-C pixels changed')
            probes.append({**evidence,'asset_ref':f'{name}/{ordinal}.png'})
        inode=tuple(before[:2]);paths=[]
        for directory,_,files in os.walk(root/'work'):
            for name in files:
                p=Path(directory)/name
                if p.is_symlink():continue
                try:s=p.stat()
                except FileNotFoundError:continue
                if (s.st_dev,s.st_ino)==inode:
                    if not any(p.is_relative_to(x) for x in owned):raise ValueError('Native CIFAR-C hard link lies outside acquired directories')
                    paths.append(p)
        if len(paths)!=source.stat().st_nlink:raise ValueError('Native CIFAR-C hard links exist outside Atlas')
        for other in registry.datasets():
            if other.id==dataset_id:continue
            for version,_,_ in registry.versions(other.id):
                for value in strings(version.adapter_config):
                    p=_local_config_path(root,value)
                    if p is not None and p.is_file() and p.samefile(source):raise ValueError('Native CIFAR-C source has another retained dataset dependency')
        result={'dataset_id':dataset_id,'status':'verified_plan','source_sha256':file['sha256'],'source_bytes':source.stat().st_size,
                'canonical_records_checked':checked,'protected_preview_records_checked':previews,'retained_snapshots':len(routes),
                'cold_original_probes':probes,'network_bytes':transfer,'paths':[str(p.relative_to(root)) for p in paths],
                'scope':'Complete canonical rows and original preview pixels preserved; exact native RGB rows available by whole-source SHA-block verified ranges.'}
        if execute:
            for path,config in routes:atomic(path,config)
            if _file_identity(source)!=before:raise ValueError('Native CIFAR-C source changed during verification')
            receipt=root/'work/original-access/retirements'/(dataset_id+'-'+file['sha256']+'.json');atomic(receipt,result)
            for p in paths:p.unlink()
            result.update(status='executed',freed_unique_file_bytes=result['source_bytes']);atomic(receipt,result)
        return result
