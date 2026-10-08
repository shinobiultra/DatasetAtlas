"""Interpret the documented native DataFrame layout without invoking pickle code."""
from __future__ import annotations
import datetime
import json
import math
import hashlib
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import struct
from dataclasses import dataclass
from typing import Any, Callable
from dataset_atlas.converters import RowDigest, converter
from .neutral_pickle import Node, Symbol, parse_gzip


@dataclass(frozen=True)
class FloatBits:
    code: str
    bits: str


def named(value: Any, name: str) -> bool:
    return isinstance(value, Node) and isinstance(value.symbol, Symbol) and value.symbol.module + '.' + value.symbol.name == name


def array(value: Any):
    if not isinstance(value,Node) or value.kind!='REDUCE':
        raise ValueError('Unsupported native array constructor kind')
    if named(value, 'numpy.core.numeric._frombuffer'):
        if value.state is not None:raise ValueError('Unsupported native frombuffer BUILD state')
        data, dtype, shape, order = value.args
    elif named(value, 'numpy.core.multiarray._reconstruct'):
        if not isinstance(value.state, tuple) or len(value.state) != 5 or value.state[0] != 1:
            raise ValueError('Unsupported native ndarray state')
        _, shape, dtype, fortran, data = value.state
        if type(fortran) is not bool:
            raise ValueError('Invalid native ndarray storage order')
        order = 'F' if fortran else 'C'
    else:
        raise ValueError('Unsupported native array constructor')
    if not named(dtype, 'numpy.dtype') or dtype.kind!='REDUCE' or not isinstance(dtype.args, tuple) or not dtype.args or not isinstance(dtype.args[0], str):
        raise ValueError('Native ndarray lacks a literal dtype')
    if (not isinstance(shape, tuple) or not 1 <= len(shape) <= 2
            or any(type(size) is not int or not 0 <= size <= 10_000_000 for size in shape)
            or math.prod(shape) > 20_000_000 or order not in {'C', 'F'}):
        raise ValueError('Native ndarray shape/order exceeds its bounds')
    code = dtype.args[0]
    if code in {'O', 'O8'}:
        if not isinstance(data, list) or len(data) != math.prod(shape):
            raise ValueError('Native object array length differs from its shape')
        values = data
    else:
        formats = {'i8': 'q', 'i4': 'i', 'u8': 'Q', 'u4': 'I', 'f8': 'd', 'f4': 'f', 'b1': '?', '?': '?'}
        if code not in formats or not isinstance(data, (bytes,bytearray)) or len(data) > 100_000_000:
            raise ValueError('Unsupported native binary dtype or buffer')
        byteorder = dtype.state[1] if isinstance(dtype.state, tuple) and len(dtype.state) > 1 else '='
        if byteorder not in {'<', '>', '|'}:
            raise ValueError('Unsupported native byte order')
        if byteorder == '|' and struct.calcsize(formats[code]) != 1:
            raise ValueError('Native multibyte dtype lacks explicit byte order')
        prefix = '>' if byteorder == '>' else '<'
        fmt = prefix + formats[code]
        if len(data) != math.prod(shape) * struct.calcsize(fmt):
            raise ValueError('Native numeric array byte length differs')
        if code == 'f4':
            values = [FloatBits('float32', (data[n:n+4] if prefix == '>' else data[n:n+4][::-1]).hex()) for n in range(0,len(data),4)]
        else:
            values = [entry[0] for entry in struct.iter_unpack(fmt, data)]
    return shape, values, order


def literal(value: Any, depth: int = 0, *, shared_ids: dict[int,int] | None = None,
            ancestors: set[int] | None = None, metadata: bool = False):
    if depth > 64:
        raise ValueError('Native value nesting exceeds its bound')
    ancestry = set() if ancestors is None else ancestors
    compound = isinstance(value, (list, tuple, dict, bytearray, Node))
    key = id(value)
    if compound and key in ancestry:
        raise ValueError('Native object cycle is unsupported; no values were manufactured')
    if compound: ancestry.add(key)
    def child(v):return literal(v, depth+1, shared_ids=shared_ids, ancestors=ancestry, metadata=metadata)
    try:
        if value is None or type(value) in {str, int, bool}: result = value
        elif type(value) is float:
            result = value if math.isfinite(value) else {'_atlas_native_type':'float64','ieee754_hex':struct.pack('>d',value).hex()}
        elif isinstance(value, FloatBits):
            result = {'_atlas_native_type':value.code,'ieee754_hex':value.bits}
        elif isinstance(value, bytearray):result = {'_atlas_native_type':'bytearray','hex':value.hex()}
        elif isinstance(value, bytes):result = {'_atlas_native_type':'bytes','hex':value.hex()}
        elif isinstance(value, tuple):result = {'_atlas_native_type':'tuple','values':[child(v) for v in value]}
        elif isinstance(value, list):result = [child(v) for v in value]
        elif isinstance(value, dict):
            if any(type(k) is not str for k in value) or '_atlas_native_type' in value:
                result = {'_atlas_native_type':'mapping','items':[[child(k),child(v)] for k,v in value.items()]}
            else:result = {k:child(v) for k,v in value.items()}
        elif metadata and isinstance(value, Symbol):
            result = {'_atlas_native_type':'serialization_symbol','module':value.module,'name':value.name}
        elif metadata and isinstance(value, Node):
            result = {'_atlas_native_type':'serialization_node','kind':value.kind,'symbol':child(value.symbol),'args':child(value.args),'state':child(value.state)}
        elif named(value,'datetime.datetime'):
            if (value.kind!='REDUCE' or not isinstance(value.args,tuple) or len(value.args)!=1 or not isinstance(value.args[0],bytes)
                    or len(value.args[0])!=10 or value.state is not None):raise ValueError('Unsupported native datetime serialization')
            raw=value.args[0];year=int.from_bytes(raw[:2],'big');month,fold=raw[2]&127,raw[2]>>7
            stamp=datetime.datetime(year,month,raw[3],raw[4],raw[5],raw[6],int.from_bytes(raw[7:],'big'),fold=fold)
            result={'_atlas_native_type':'datetime.datetime','iso8601':stamp.isoformat(),'fold':fold,'packed_hex':raw.hex()}
        elif named(value,'collections.Counter'):
            if value.kind!='REDUCE' or not isinstance(value.args,tuple) or len(value.args)!=1 or not isinstance(value.args[0],dict) or value.state is not None:
                raise ValueError('Unsupported native Counter serialization')
            result={'_atlas_native_type':'collections.Counter','values':child(value.args[0])}
        else:raise ValueError('Unsupported native value; no serialized callable was invoked')
        if compound and shared_ids and key in shared_ids:
            result={'_atlas_native_type':'shared_object','native_memo':shared_ids[key],'value':result}
        return result
    finally:
        if compound:ancestry.remove(key)


def frame_metadata(frame: Any, *, shared_ids=None):
    if not named(frame,'pandas.core.frame.DataFrame') or not isinstance(frame.state,dict):
        raise ValueError('Unsupported inert DataFrame metadata')
    manager=frame.state.get('_mgr')
    if not named(manager,'pandas.core.internals.managers.BlockManager') or not isinstance(manager.args,tuple) or len(manager.args)!=2:
        raise ValueError('Unsupported native DataFrame manager')
    blocks,axes=manager.args
    def meta(value):return literal(value,metadata=True,shared_ids=shared_ids)
    def array_meta(native):
        shape,_,order=array(native)
        reconstruct=named(native,'numpy.core.multiarray._reconstruct')
        data=native.state[4] if reconstruct else native.args[0]
        dtype=native.state[2] if reconstruct else native.args[1]
        return {'constructor':meta(native.symbol),'kind':native.kind,'shape':list(shape),'order':order,'dtype':meta(dtype),
          'state_version':native.state[0] if reconstruct else None,
          'reconstruction_args':meta(native.args) if reconstruct else None,
          'native_memo':(shared_ids or {}).get(id(native)),
          'buffer_type':type(data).__name__,'buffer_native_memo':(shared_ids or {}).get(id(data))}
    result={'representation':'Inert native DataFrame metadata v2; constructors are retained as data, never executed.',
            'frame_native_memo':(shared_ids or {}).get(id(frame)),
            'frame_class':meta(frame.symbol),'frame_kind':frame.kind,'frame_args':meta(frame.args),
            'frame_attributes':meta({k:v for k,v in frame.state.items() if k!='_mgr'}),
            'manager_native_memo':(shared_ids or {}).get(id(manager)),
            'manager_constructor':meta(manager.symbol),'manager_kind':manager.kind,
            'manager_args_structure':['blocks','axes'],'manager_state':meta(manager.state),'axes':[],'blocks':[]}
    for axis in axes:
        if not named(axis,'pandas.core.indexes.base._new_Index') or len(axis.args)!=2 or not isinstance(axis.args[1],dict):
            raise ValueError('Unsupported native DataFrame axis metadata')
        native=axis.args[1]['data'];shape,values,order=array(native)
        ameta=array_meta(native)
        result['axes'].append({'index_class':meta(axis.args[0]),'attributes':meta({k:v for k,v in axis.args[1].items() if k!='data'}),
          'constructor_native_memo':(shared_ids or {}).get(id(axis)),
          'constructor':meta(axis.symbol),'constructor_kind':axis.kind,'constructor_state':meta(axis.state),
          'shape':list(shape),'order':order,'dtype':ameta['dtype'],'array_metadata':ameta,'values':literal(values,shared_ids=shared_ids)})
    for block in blocks:
        native=block.args[0];ameta=array_meta(native);placements=block.args[1]
        placement_meta=array_meta(placements)
        result['blocks'].append({'shape':ameta['shape'],'order':ameta['order'],'dtype':ameta['dtype'],'placements':array(placements)[1],
          'placement_metadata':placement_meta,'constructor_native_memo':(shared_ids or {}).get(id(block)),
          'constructor':meta(block.symbol),'constructor_kind':block.kind,'constructor_state':meta(block.state),
          'array_metadata':ameta})
    return result


def expand_row(row):
    output=dict(row)
    other=row.get('_atlas_nonstring_columns')
    if other and other.get('encoding')=='literal-runs-v1':
        values=[]
        for item in other['runs']:
            count=item.get('count')
            if type(count) is not int or not 1<=count<=10000 or len(values)+count>10000:raise ValueError('Invalid native run length')
            values.extend([item['value']]*count)
        if len(values)!=len(other['labels']):raise ValueError('Native run population differs from its labels')
        output['_atlas_nonstring_columns']={'labels':other['labels'],'values':values,
          'representation':'Exact native integer-labelled DataFrame columns, in original column order.'}
    return output


def frame_rows(frame: Any, check=lambda: None, *, compact=False, shared_ids=None):
    if not named(frame, 'pandas.core.frame.DataFrame') or not isinstance(frame.state, dict):
        raise ValueError('FACTOID source is not the supported inert DataFrame layout')
    manager = frame.state.get('_mgr')
    if frame.kind not in {'REDUCE','NEWOBJ'} or frame.args!=():
        raise ValueError('Unsupported native DataFrame constructor kind or arguments')
    if not named(manager, 'pandas.core.internals.managers.BlockManager') or not isinstance(manager.args, tuple) or len(manager.args) != 2:
        raise ValueError('Unsupported native DataFrame manager')
    blocks, axes = manager.args
    if manager.kind!='REDUCE':raise ValueError('Unsupported native manager constructor kind')
    if not isinstance(blocks, tuple) or not isinstance(axes, list) or len(axes) != 2:
        raise ValueError('Unsupported native DataFrame blocks/axes')
    def axis(value):
        if (not named(value, 'pandas.core.indexes.base._new_Index') or len(value.args) != 2
                or not isinstance(value.args[1], dict) or 'data' not in value.args[1]):
            raise ValueError('Unsupported native DataFrame axis')
        if value.kind!='REDUCE':raise ValueError('Unsupported native axis constructor kind')
        shape, values, _ = array(value.args[1]['data'])
        if len(shape) != 1:raise ValueError('Native DataFrame axis is not one-dimensional')
        return values
    columns, indices = axis(axes[0]), axis(axes[1])
    if not columns or len(columns) > 10_000 or any(type(name) not in {str, int} for name in columns) or len(set(columns)) != len(columns):
        raise ValueError('Unsupported native DataFrame column labels')
    if any(isinstance(name, str) and name.startswith('_atlas_') for name in columns):
        raise ValueError('Native DataFrame collides with retained serialization provenance')
    if not 1 <= len(indices) <= 100_000:
        raise ValueError('Native DataFrame row count exceeds its bound')
    slots = {}
    for block in blocks:
        if not isinstance(block, Node) or not named(block.symbol, 'functools.partial'):
            raise ValueError('Unsupported native block constructor')
        partial = block.symbol
        if block.kind!='REDUCE' or partial.kind!='REDUCE':raise ValueError('Unsupported native block constructor kind')
        if (not isinstance(partial.state, tuple) or len(partial.state) != 4
                or not isinstance(partial.state[0], Symbol)
                or partial.state[0].module + '.' + partial.state[0].name != 'pandas.core.internals.blocks.new_block'
                or partial.state[1] != () or partial.state[2] != {'ndim': 2} or partial.state[3] is not None
                or not isinstance(block.args, tuple) or len(block.args) != 2):
            raise ValueError('Unsupported native block partial state')
        shape, values, order = array(block.args[0])
        place_shape, places, _ = array(block.args[1])
        if len(shape) != 2 or shape[1] != len(indices) or place_shape != (shape[0],):
            raise ValueError('Native block population or placement differs')
        for offset, column in enumerate(places):
            if type(column) is not int or not 0 <= column < len(columns) or column in slots:
                raise ValueError('Native block has overlapping/out-of-range column placement')
            slots[column] = (values, offset, shape[0], order)
    if set(slots) != set(range(len(columns))):
        raise ValueError('Native DataFrame has missing column blocks')
    for row, index in enumerate(indices):
        check()
        result = {'_atlas_dataframe_index': literal(index,shared_ids=shared_ids)}
        other_labels, other_values = [], []
        for column, name in enumerate(columns):
            values, offset, width, order = slots[column]
            position = offset * len(indices) + row if order == 'C' else row * width + offset
            value = literal(values[position],shared_ids=shared_ids)
            if type(name) is str:
                result[name] = value
            else:
                other_labels.append(name); other_values.append(value)
        if other_labels:
            result['_atlas_nonstring_columns'] = {'labels': other_labels, 'values': other_values,
                                                  'representation': 'Exact native integer-labelled DataFrame columns, in original column order.'}
        if compact and other_labels:
            runs=[];previous=None
            for native_value,value in zip([slots[column][0][slots[column][1]*len(indices)+row if slots[column][3]=='C' else row*slots[column][2]+slots[column][1]] for column,name in enumerate(columns) if type(name) is not str],other_values,strict=True):
                repeatable=native_value is None or type(native_value) in {str,int,bool,float,bytes} or isinstance(native_value,FloatBits)
                marker=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
                if repeatable and runs and marker==previous:runs[-1]['count']+=1
                else:runs.append({'count':1,'value':value})
                previous=marker
            original=result['_atlas_nonstring_columns']
            result['_atlas_nonstring_columns']={'labels':other_labels,'encoding':'literal-runs-v1','runs':runs,
                'representation':'Reversible runs over exact native typed values; native column order retained.'}
            if expand_row(result)['_atlas_nonstring_columns']!=original:raise ValueError('Native compact value round-trip differs')
        yield result


NATIVE_SHA256 = '42e975c9067c6a738e2ae85a1d18c80b90974ffe4af75e57fbde53588040dbbb'
NATIVE_BYTES = 369319718
MAX_OUTPUT_BYTES = 4_000_000_000


def _regular_open(path: Path, maximum: int):
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size>maximum:
            raise ValueError('Native conversion requires bounded regular files')
        return os.fdopen(descriptor,'rb')
    except BaseException:
        os.close(descriptor);raise


def _hash(path: Path, check=lambda: None) -> str:
    digest=hashlib.sha256()
    with _regular_open(path,MAX_OUTPUT_BYTES) as stream:
        for data in iter(lambda:stream.read(1<<20),b''):
            check();digest.update(data)
    check()
    return digest.hexdigest()


def _contract_hash() -> str:
    digest=hashlib.sha256()
    for path in [Path(__file__),Path(__file__).with_name('neutral_pickle.py')]:digest.update(path.read_bytes())
    return digest.hexdigest()


def _source_pin(source: Path, params: dict, check=lambda: None):
    expected=params.get('source_sha256',NATIVE_SHA256);size=params.get('source_bytes',NATIVE_BYTES)
    if source.is_symlink():raise ValueError('Native input cannot be a symlink')
    if type(size) is not int or not 1<=size<=400_000_000 or not isinstance(expected,str) or len(expected)!=64:
        raise ValueError('Invalid native source pin')
    if source.stat().st_size!=size or _hash(source,check)!=expected:
        raise ValueError('Native source differs from its whole-file pin')
    return expected,size


def _convert_in_process(params: dict, source: Path, output_dir: Path):
    import resource
    source_sha,size=_source_pin(source,params)
    contract_sha=_contract_hash()
    maximum=params.get('max_output_bytes',MAX_OUTPUT_BYTES)
    if type(maximum) is not int or not 1<=maximum<=MAX_OUTPUT_BYTES:raise ValueError('Invalid FACTOID output budget')
    shared_ids: dict[int,int]={}
    frame,syntax=parse_gzip(source,shared_ids=shared_ids)
    metadata=frame_metadata(frame,shared_ids=shared_ids)
    metadata['native_source_sha256']=source_sha
    metadata['object_graph_policy']='Every shared mutable/container object observed through native pickle memo references retains its native memo ID with expanded immutable values. Cycles refuse. Original serialization remains byte-identical and read-only.'
    metadata_bytes=json.dumps(metadata,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()+b'\n'
    if len(metadata_bytes)>2_000_000 or size+len(metadata_bytes)>maximum:
        raise ValueError('Native DataFrame metadata exceeds its bound')
    metadata_sha=hashlib.sha256(metadata_bytes).hexdigest()
    if params.get('metadata_sha256') and params['metadata_sha256']!=metadata_sha:
        raise ValueError('Native DataFrame metadata differs from its immutable pin')
    output_dir.mkdir()
    meta_path=output_dir/'native-frame-metadata.json';meta_path.write_bytes(metadata_bytes)
    original=output_dir/'native-original.gzip'
    with source.open('rb') as stream,original.open('xb') as target:shutil.copyfileobj(stream,target,1<<20)
    original.chmod(0o444)
    output=output_dir/'factoid-native-values.jsonl';digest=RowDigest();values_digest=RowDigest();written=size+len(metadata_bytes);maximum_record=0
    with output.open('xb') as stream:
        for row in frame_rows(frame,compact=True,shared_ids=shared_ids):
            # The inverse run representation is checked against native typed cells
            # before emission; keep a separate full-value digest as a contract.
            values_digest.add(expand_row(row))
            row['_atlas_frame_metadata_sha256']=metadata_sha
            data=(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
            written+=len(data);maximum_record=max(maximum_record,len(data))
            if len(data)>16_000_000:
                error=ValueError('FACTOID native record exceeds its per-record bound')
                setattr(error,'atlas_aggregate',{'record_bytes':len(data),'written_bytes':written,'completed_records':digest.count})
                raise error
            if written>maximum:
                error=ValueError('FACTOID native rows exceed total output budget')
                setattr(error,'atlas_aggregate',{'record_bytes':len(data),'written_bytes':written,'completed_records':digest.count})
                raise error
            stream.write(data);digest.add(row)
    if params.get('native_values_sha256') and params['native_values_sha256']!=values_digest.hexdigest():
        raise ValueError('Native DataFrame cell values differ from their immutable pin')
    _source_pin(source,params)
    if _hash(original)!=source_sha:raise ValueError('Retained original source differs from its pin')
    cells=digest.count*sum(len(block['placements']) for block in metadata['blocks'])
    limits={'address_space_bytes':resource.getrlimit(resource.RLIMIT_AS)[0],'cpu_seconds':resource.getrlimit(resource.RLIMIT_CPU)[0]}
    proof={'source_sha256':source_sha,'source_bytes':size,'metadata_sha256':metadata_sha,'row_count':digest.count,'native_cells_checked':cells,
       'rows_sha256':digest.hexdigest(),'native_values_sha256':values_digest.hexdigest(),'maximum_record_bytes':maximum_record,
       'syntax_receipt':syntax,'shared_container_memo_count':len(shared_ids),'resource_limits':limits,
       'executed_serialized_code':False,'reddit_hydration_requests':0,'scope':'Exact native user rows, full retained DataFrame metadata and original serialization. Reversible run encoding is checked per row. Historical paper membership and rights remain unverified.'}
    proof_path=output_dir/'native-conversion-proof.json'
    proof_bytes=(json.dumps(proof,indent=2)+'\n').encode()
    if len(proof_bytes)>100_000 or written+len(proof_bytes)>maximum:raise ValueError('Conversion proof exceeds output budget')
    proof_path.write_bytes(proof_bytes);written+=len(proof_bytes)
    derived=[{'path':str(path),'bytes':path.stat().st_size,'sha256':_hash(path),'kind':kind} for path,kind in [
        (meta_path,'native DataFrame metadata'),(original,'exact native serialization'),(proof_path,'native conversion proof')]]
    result={'path':str(output),'format':'jsonl','count':digest.count,'rows_sha256':digest.hexdigest(),'file_sha256':_hash(output),'columns':None,
       'metadata_sha256':metadata_sha,'native_values_sha256':values_digest.hexdigest(),'native_cells_checked':cells,'syntax_receipt':syntax,
       'resource_limits':limits,'maximum_record_bytes':maximum_record,'derived_sources':derived,
       'representation':'Author native user rows; source floats, datetimes, bytes, tuples and shared containers have explicit exact representations. Integer-labelled columns use reversible runs.',
       'adapter_config':{'native_metadata_path':str(meta_path),'native_metadata_sha256':metadata_sha,'native_original_path':str(original)}}
    if _contract_hash()!=contract_sha:raise ValueError('Converter code changed during native conversion')
    manifest={'contract_sha256':contract_sha,'source_sha256':source_sha,'source_bytes':size,'result':result}
    manifest_bytes=(json.dumps(manifest,indent=2)+'\n').encode()
    if len(manifest_bytes)>2_000_000 or written+len(manifest_bytes)>maximum:raise ValueError('Conversion manifest exceeds output budget')
    (output_dir/'conversion-result.json').write_bytes(manifest_bytes)
    if sum(path.stat().st_size for path in output_dir.iterdir())>maximum:raise ValueError('Complete conversion exceeds output budget')
    return result


def _launch_worker(request: Path, *, check=lambda: None, max_seconds=480):
    if not 0<max_seconds<=480:raise ValueError('Invalid isolated worker deadline')
    check();deadline=time.monotonic()+max_seconds
    process=subprocess.Popen([sys.executable,'-m','dataset_atlas.converters.factoid','--bounded-worker',str(request)],
       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=False)
    try:
        while process.poll() is None:
            check()
            if time.monotonic()>deadline:raise TimeoutError('FACTOID isolated conversion exceeded its deadline')
            time.sleep(0.05)
        check()
        if process.returncode:raise ValueError('FACTOID bounded worker refused its native layout, pins or resource budget; local failure receipt retained')
    finally:
        if process.poll() is None:
            # This fixed inert worker cannot launch source callables/children.
            # Inheriting the preparation group also makes an outer job stop kill
            # it; direct cancellation kills and reaps this exact child.
            try:process.kill()
            except ProcessLookupError:pass
        process.wait(timeout=5)


def _read_json(path,maximum):
    with _regular_open(path,maximum) as stream:return json.load(stream)


def _validate_cached(output_dir: Path, source_sha: str, size: int, params: dict, check=lambda: None):
    check();value=_read_json(output_dir/'conversion-result.json',2_000_000);result=value['result']
    if (value['contract_sha256'],value['source_sha256'],value['source_bytes'])!=(_contract_hash(),source_sha,size):
        raise ValueError('Retained FACTOID conversion differs from the native source/code contract')
    required={'native DataFrame metadata':'native-frame-metadata.json','exact native serialization':'native-original.gzip','native conversion proof':'native-conversion-proof.json'}
    derived=result['derived_sources']
    if not isinstance(derived,list) or len(derived)!=3 or {item['kind'] for item in derived}!=set(required):
        raise ValueError('Retained FACTOID conversion lacks required native derived roles')
    if result['path']!=str(output_dir/'factoid-native-values.jsonl') or result['format']!='jsonl':
        raise ValueError('Retained FACTOID rows path differs')
    entries=[{'path':result['path'],'sha256':result['file_sha256']},*derived]
    for item in entries:
        path=Path(item['path'])
        if path.parent!=output_dir or (item in derived and path.name!=required[item['kind']]) or _hash(path,check)!=item['sha256']:
            raise ValueError('Retained FACTOID conversion checksum differs')
        if item in derived and path.stat().st_size!=item['bytes']:raise ValueError('Retained derived size differs')
    metadata_path=output_dir/'native-frame-metadata.json';original=output_dir/'native-original.gzip'
    actual_metadata=_hash(metadata_path,check)
    if actual_metadata!=result['metadata_sha256'] or original.stat().st_size!=size or _hash(original,check)!=source_sha:
        raise ValueError('Retained native metadata or original source pin differs')
    if result['adapter_config']!={'native_metadata_path':str(metadata_path),'native_metadata_sha256':actual_metadata,'native_original_path':str(original)}:
        raise ValueError('Retained adapter native pointers differ')
    metadata=_read_json(metadata_path,2_000_000);proof=_read_json(output_dir/'native-conversion-proof.json',100_000)
    if metadata['native_source_sha256']!=source_sha:raise ValueError('Native metadata source pin differs')
    digest=RowDigest();values=RowDigest();maximum_record=0
    with _regular_open(Path(result['path']),MAX_OUTPUT_BYTES) as stream:
        while True:
            check();line=stream.readline(16_000_001)
            if not line:break
            if len(line)>16_000_000:raise ValueError('Cached native row exceeds its bound')
            row=json.loads(line)
            if not isinstance(row,dict) or row.get('_atlas_frame_metadata_sha256')!=actual_metadata:
                raise ValueError('Native row metadata reference differs')
            digest.add(row);row.pop('_atlas_frame_metadata_sha256');values.add(expand_row(row))
            maximum_record=max(maximum_record,len(line))
            if digest.count>100_000:raise ValueError('Cached native population exceeds its bound')
    if (digest.count,digest.hexdigest(),values.hexdigest(),maximum_record)!=(result['count'],result['rows_sha256'],result['native_values_sha256'],result['maximum_record_bytes']):
        raise ValueError('Retained FACTOID actual semantic rows differ from their pins')
    cells=digest.count*sum(len(block['placements']) for block in metadata['blocks'])
    if cells!=result['native_cells_checked']:raise ValueError('Retained native cell count differs')
    for key,actual in {'source_sha256':source_sha,'source_bytes':size,'metadata_sha256':actual_metadata,'row_count':digest.count,'native_cells_checked':cells,
          'rows_sha256':digest.hexdigest(),'native_values_sha256':values.hexdigest(),'maximum_record_bytes':maximum_record,'executed_serialized_code':False,'reddit_hydration_requests':0}.items():
        if proof.get(key)!=actual:raise ValueError('Retained native proof differs from actual output')
    for key in ['metadata_sha256','native_values_sha256']:
        if params.get(key) and params[key]!=result[key]:raise ValueError('Retained FACTOID semantic metadata/value pin differs')
    if any(p.is_symlink() or not p.is_file() for p in output_dir.iterdir()) or sum(path.stat().st_size for path in output_dir.iterdir())>params.get('max_output_bytes',MAX_OUTPUT_BYTES):
        raise ValueError('Retained FACTOID conversion exceeds its output budget')
    check();return result


def _verified_cached(output_dir: Path, source_sha: str, size: int, params: dict, check):
    # Native-sized validation runs under the same AS/CPU/wall limits as conversion.
    if any(not isinstance(params.get(key),str) or len(params[key])!=64 for key in ['metadata_sha256','native_values_sha256']):
        raise ValueError('Cached FACTOID validation requires trusted immutable semantic pins')
    with tempfile.TemporaryDirectory(prefix='.factoid-cache-check-',dir=output_dir.parent) as temporary:
        request=Path(temporary)/'request.json'
        request.write_text(json.dumps({'mode':'validate','output_dir':str(output_dir),'source_sha256':source_sha,'source_bytes':size,'params':params}))
        _launch_worker(request,check=check)
        result=_read_json(Path(temporary)/'validated-result.json',2_000_000)
    check();result['path']=Path(result['path']);return result


@converter('factoid_dataframe')
def convert_factoid(params, inputs, output_dir, check=lambda: None):
    source=Path(inputs['native']);output_dir=Path(output_dir).absolute()
    if output_dir.is_symlink():raise ValueError('FACTOID output directory cannot be a symlink')
    source_sha,size=_source_pin(source,params,check)
    if output_dir.exists():return _verified_cached(output_dir,source_sha,size,params,check)
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.factoid-worker-',dir=output_dir.parent) as temporary:
        folder=Path(temporary);stage=folder/'converted';request=folder/'request.json'
        request.write_text(json.dumps({'source':str(source.absolute()),'output_dir':str(stage),'params':params}))
        try:_launch_worker(request,check=check)
        except BaseException:
            failure=folder/'failure.json'
            if failure.is_file() and failure.stat().st_size<10000:
                target=output_dir.parent/(output_dir.name+'-failure.json')
                if not target.exists():shutil.copyfile(failure,target)
            raise
        manifest=json.loads((stage/'conversion-result.json').read_text())
        def relocate(value):
            if isinstance(value,str) and value.startswith(str(stage)+'/'):return str(output_dir/Path(value).relative_to(stage))
            if isinstance(value,dict):return {k:relocate(v) for k,v in value.items()}
            if isinstance(value,list):return [relocate(v) for v in value]
            return value
        (stage/'conversion-result.json').write_text(json.dumps(relocate(manifest),indent=2)+'\n')
        check();stage.rename(output_dir)
    verified_params={**params,**{key:manifest['result'][key] for key in ['metadata_sha256','native_values_sha256']}}
    return _verified_cached(output_dir,source_sha,size,verified_params,check)


def _main():
    import resource
    if len(sys.argv)!=3 or sys.argv[1]!='--bounded-worker':raise ValueError('Internal bounded-worker invocation required')
    request=Path(sys.argv[2])
    if request.is_symlink() or request.stat().st_size>64000:raise ValueError('Worker request exceeds its bound')
    config=json.loads(request.read_text())
    resource.setrlimit(resource.RLIMIT_AS,(8_000_000_000,8_000_000_000))
    resource.setrlimit(resource.RLIMIT_CPU,(360,370))
    resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_OUTPUT_BYTES,MAX_OUTPUT_BYTES))
    try:
        if config.get('mode')=='validate':
            validated=_validate_cached(Path(config['output_dir']),config['source_sha256'],config['source_bytes'],config['params'])
            data=(json.dumps(validated,indent=2)+'\n').encode()
            if len(data)>2_000_000:raise ValueError('Validated cache result exceeds its bound')
            (request.parent/'validated-result.json').write_bytes(data)
        else:_convert_in_process(config['params'],Path(config['source']),Path(config['output_dir']))
    except BaseException as error:
        import ast
        import traceback
        # Report only trusted converter locations and literal guard messages.
        # Exception text and locals may contain native values and stay private.
        locations=[];guard_message=None
        for location in traceback.extract_tb(error.__traceback__):
            path=Path(location.filename)
            if path.parent==Path(__file__).parent and path.name in {'factoid.py','neutral_pickle.py'}:
                locations.append({'module':path.stem,'function':location.name,'line':location.lineno})
                for entry in ast.walk(ast.parse(path.read_text())):
                    if isinstance(entry,ast.Raise) and entry.lineno==location.lineno and isinstance(entry.exc,ast.Call) and entry.exc.args:
                        first=entry.exc.args[0]
                        if isinstance(first,ast.Constant) and isinstance(first.value,str):guard_message=first.value
        (request.parent/'failure.json').write_text(json.dumps({'status':'refused','error_type':type(error).__name__,
          'trusted_locations':locations,'trusted_guard':guard_message,
          'aggregate_counts':getattr(error,'atlas_aggregate',None),
          'message':'Native layout, source pin or isolated resource bound refused. No serialized code was executed.'})+'\n')
        raise SystemExit(1)


if __name__=='__main__':_main()
