import datetime
import gzip
import os
from pathlib import Path
import pickle
import struct
import pytest
from dataset_atlas.converters.neutral_pickle import parse_gzip, Node, Symbol
from dataset_atlas.converters.factoid import array, literal, frame_rows


def node(name, args, state=None):
    module, name = name.rsplit('.', 1)
    value = Node(Symbol(module, name), args, 'REDUCE')
    value.state = state
    return value


def ndarray(shape, values, dtype='O8', order='C'):
    dt = node('numpy.dtype', (dtype,), (3, '<' if dtype != 'O8' else '|', None))
    if dtype == 'O8':
        return node('numpy.core.multiarray._reconstruct', (), (1, shape, dt, order == 'F', values))
    formats = {'i8': 'q', 'f8': 'd'}
    payload = b''.join(struct.pack('<' + formats[dtype], value) for value in values)
    return node('numpy.core.numeric._frombuffer', (payload, dt, shape, order))


def frame(order='C'):
    columns = ['user_id', 'documents', 'source_label']
    values = ['generated-a', 'generated-b', ('generated post', 1), ('another generated post', 2)]
    if order == 'F':values = [values[0], values[2], values[1], values[3]]
    def block(data, placement):
        fn = Symbol('pandas.core.internals.blocks', 'new_block')
        partial = node('functools.partial', (fn,), (fn, (), {'ndim': 2}, None))
        return Node(partial, (data, ndarray((len(placement),), placement, 'i8')), 'REDUCE')
    blocks = (block(ndarray((2, 2), values, order=order), [0, 1]),
              block(ndarray((1, 2), [7, 9], 'i8'), [2]))
    axes = [node('pandas.core.indexes.base._new_Index', (Symbol('pandas.core.indexes.base', 'Index'), {'data': ndarray((3,), columns), 'name': None})),
            node('pandas.core.indexes.base._new_Index', (Symbol('pandas.core.indexes.numeric', 'Int64Index'), {'data': ndarray((2,), [10, 42], 'i8'), 'name': None}))]
    manager = node('pandas.core.internals.managers.BlockManager', (blocks, axes))
    return node('pandas.core.frame.DataFrame', (), {'_mgr': manager})


def test_pickle_callable_is_inert_and_cannot_write_a_marker(tmp_path):
    marker = tmp_path / 'must-not-exist'
    class GeneratedInstructions:
        def __reduce__(self):
            return os.system, ('touch ' + str(marker),)
    path = tmp_path / 'generated.gzip'
    path.write_bytes(gzip.compress(pickle.dumps(GeneratedInstructions(), protocol=5)))
    parsed, receipt = parse_gzip(path)
    assert isinstance(parsed, Node) and 'posix.system' in receipt['symbols']
    assert not marker.exists()
    with pytest.raises(ValueError, match='Unsupported native value'):
        literal(parsed)
    assert not marker.exists()


def test_primitives_and_shared_container_syntax_are_preserved(tmp_path):
    shared = ['generated', None, True, b'bytes']
    value = {'first': shared, 'second': shared, 'tuple': (3, 1.5)}
    path = tmp_path / 'primitive.gzip'
    path.write_bytes(gzip.compress(pickle.dumps(value, protocol=5)))
    parsed, _ = parse_gzip(path)
    assert parsed == value and parsed['first'] is parsed['second']


def test_trailing_pickle_stream_and_cancel_are_refused(tmp_path):
    path = tmp_path / 'extra.gzip'
    path.write_bytes(gzip.compress(pickle.dumps(1) + b'extra'))
    with pytest.raises(ValueError, match='terminator'):
        parse_gzip(path)
    path.write_bytes(gzip.compress(pickle.dumps(list(range(20000)))))
    def cancel():raise TimeoutError('synthetic cancellation')
    with pytest.raises(TimeoutError):parse_gzip(path, cancel)


@pytest.mark.parametrize('order', ['C', 'F'])
def test_native_block_placement_and_storage_order_keep_values(order):
    rows = list(frame_rows(frame(order)))
    assert [r['_atlas_dataframe_index'] for r in rows] == [10, 42]
    assert [r['user_id'] for r in rows] == ['generated-a', 'generated-b']
    assert [r['source_label'] for r in rows] == [7, 9]
    assert rows[0]['documents'] == {'_atlas_native_type': 'tuple', 'values': ['generated post', 1]}


def test_overlapping_column_placement_cannot_be_accepted():
    value = frame()
    manager = value.state['_mgr']
    manager.args[0][1].args = (manager.args[0][1].args[0], ndarray((1,), [0], 'i8'))
    with pytest.raises(ValueError, match='overlapping'):
        list(frame_rows(value))


def test_numeric_byte_lengths_and_unknown_dtype_fail_closed():
    value = ndarray((2,), [1, 2], 'i8')
    value.args = (b'bad', *value.args[1:])
    with pytest.raises(ValueError, match='byte length'):array(value)
    value = ndarray((1,), [1], 'i8')
    value.args[1].args = ('unrecognized',)
    with pytest.raises(ValueError, match='Unsupported native binary'):array(value)


def test_datetime_and_nonfinite_float_have_explicit_lossless_envelopes():
    timestamp = datetime.datetime(2020, 5, 6, 7, 8, 9, 123456, fold=1)
    packed = b'\x07\xe4\x85\x06\x07\x08\x09\x01\xe2\x40'
    result = literal(node('datetime.datetime', (packed,)))
    assert result['iso8601'] == timestamp.isoformat() and result['fold'] == 1 and result['packed_hex'] == packed.hex()
    nan = struct.unpack('>d', bytes.fromhex('7ff8000000000012'))[0]
    assert literal(nan)['ieee754_hex'] == '7ff8000000000012'


def test_unknown_native_constructor_and_value_nesting_are_refused():
    with pytest.raises(ValueError):literal(node('unknown.constructor', ('generated',)))
    value = None
    for _ in range(66):value = [value]
    with pytest.raises(ValueError, match='nesting'):literal(value)


def test_native_integer_column_labels_are_preserved_without_renaming():
    value = frame()
    columns = value.state['_mgr'].args[1][0].args[1]['data']
    columns.state[4][2] = 4150
    rows = list(frame_rows(value))
    assert 'source_label' not in rows[0]
    assert rows[0]['_atlas_nonstring_columns']['labels'] == [4150]
    assert rows[0]['_atlas_nonstring_columns']['values'] == [7]
    assert rows[1]['_atlas_nonstring_columns']['values'] == [9]


@pytest.mark.parametrize('payload', [b'\x85.', b'a.', b's.', b'\x93.', b'R.', b'0.', b'2.', b'b.'])
def test_malformed_stack_arity_is_refused(tmp_path, payload):
    path = tmp_path / 'malformed.gzip'
    path.write_bytes(gzip.compress(payload))
    with pytest.raises(ValueError, match='stack underflow'):
        parse_gzip(path)


def test_immediate_cancellation_and_reserved_dictionary_are_preserved(tmp_path):
    path = tmp_path / 'small.gzip'
    path.write_bytes(gzip.compress(b'N.'))
    def cancel(): raise TimeoutError('generated cancellation')
    with pytest.raises(TimeoutError): parse_gzip(path, cancel)
    native = {'_atlas_native_type': 'bytes', 'hex': '78'}
    assert literal(b'x') != literal(native)
    assert literal(native)['_atlas_native_type'] == 'mapping'


def test_frame_metadata_keeps_axis_classes_names_dtype_and_frame_attrs():
    import dataset_atlas.converters.factoid as module
    assert callable(getattr(module, 'frame_metadata', None))
    value=frame('F')
    value.state.update(_metadata=['generated_attribute'], attrs={'generated_attribute': ('keep', 3)}, _flags={'allows_duplicate_labels': False})
    value.state['_mgr'].args[1][1].args[1]['name']='generated native index'
    meta=module.frame_metadata(value)
    assert meta['axes'][1]['attributes']['name']=='generated native index'
    assert meta['axes'][1]['index_class']['name']=='Int64Index'
    assert meta['blocks'][0]['order']=='F'
    assert meta['blocks'][1]['dtype']['args']['values'][0]=='i8'
    assert meta['frame_attributes']['attrs']['generated_attribute']=={'_atlas_native_type':'tuple','values':['keep',3]}
    assert meta['frame_attributes']['_flags']['allows_duplicate_labels'] is False


def test_compact_integer_columns_expand_to_exact_native_float_payloads():
    import dataset_atlas.converters.factoid as module
    assert callable(getattr(module, 'expand_row', None))
    value=frame()
    value.state['_mgr'].args[1][0].args[1]['data'].state[4][2]=4150
    raw=bytes.fromhex('7ff8000000000012')
    number=struct.unpack('>d',raw)[0]
    value.state['_mgr'].args[0][1].args=(ndarray((1,2),[number,-0.0],'f8'),ndarray((1,),[2],'i8'))
    compact=list(module.frame_rows(value, compact=True))
    expanded=[module.expand_row(row) for row in compact]
    assert expanded[0]['_atlas_nonstring_columns']['values']==[{'_atlas_native_type':'float64','ieee754_hex':raw.hex()}]
    assert struct.pack('>d',expanded[1]['_atlas_nonstring_columns']['values'][0]).hex()=='8000000000000000'


def test_shared_objects_keep_native_memo_identity_and_cycles_refuse():
    import inspect
    assert 'shared_ids' in inspect.signature(literal).parameters
    shared=['generated immutable value']
    encoded=literal([shared,shared],shared_ids={id(shared):37})
    assert encoded[0]['native_memo']==encoded[1]['native_memo']==37
    assert encoded[0]['value']==encoded[1]['value']==shared
    cyclic=[];cyclic.append(cyclic)
    with pytest.raises(ValueError,match='cycle'):literal(cyclic)


def test_float32_signalling_nan_bits_are_not_changed_by_float64_conversion():
    dt=node('numpy.dtype',('f4',),(3,'<',None))
    data=node('numpy.core.numeric._frombuffer',(bytes.fromhex('0100807f'),dt,(1,),'C'))
    value=array(data)[1][0]
    encoded=literal(value)
    assert isinstance(encoded,dict) and encoded.get('_atlas_native_type')=='float32'
    assert encoded['ieee754_hex']=='7f800001'


def test_neutral_parser_reports_only_actual_memo_shared_containers(tmp_path):
    import inspect
    assert 'shared_ids' in inspect.signature(parse_gzip).parameters
    shared=['generated'];value=[shared,shared]
    path=tmp_path/'aliases.gzip';path.write_bytes(gzip.compress(pickle.dumps(value,protocol=5)))
    ids={};parsed,_=parse_gzip(path,shared_ids=ids)
    assert parsed[0] is parsed[1] and id(parsed[0]) in ids


def generated_pickle(value):
    if isinstance(value,Symbol):return b'c'+value.module.encode()+b'\n'+value.name.encode()+b'\n'
    if isinstance(value,Node):
        encoded=generated_pickle(value.symbol)+generated_pickle(value.args)+b'R'
        return encoded+(generated_pickle(value.state)+b'b' if value.state is not None else b'')
    if value is None:return b'N'
    if type(value) is bool:return b'\x88' if value else b'\x89'
    if type(value) is int:return b'J'+struct.pack('<i',value)
    if type(value) is float:return b'G'+struct.pack('>d',value)
    if type(value) is bytes:return b'B'+struct.pack('<I',len(value))+value
    if type(value) is str:
        data=value.encode();return b'X'+struct.pack('<I',len(data))+data
    if type(value) is tuple:return b'('+b''.join(generated_pickle(v) for v in value)+b't'
    if type(value) is list:return b']('+b''.join(generated_pickle(v) for v in value)+b'e'
    if type(value) is dict:return b'}('+b''.join(generated_pickle(k)+generated_pickle(v) for k,v in value.items())+b'u'
    raise AssertionError('Unsupported generated fixture')


def generated_worker_source(tmp_path):
    import hashlib
    source=tmp_path/'generated-native.gzip'
    source.write_bytes(gzip.compress(b'\x80\x04'+generated_pickle(frame())+b'.'))
    return source,{'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_bytes':source.stat().st_size,'max_output_bytes':1_000_000}


def test_conversion_worker_retains_original_metadata_and_exact_records(tmp_path):
    import json
    import dataset_atlas.converters.factoid as module
    assert callable(getattr(module,'_launch_worker',None))
    source,params=generated_worker_source(tmp_path)
    result=module.convert_factoid(params,{'native':source},tmp_path/'converted')
    assert result['count']==2 and result['native_cells_checked']==6
    assert result['resource_limits']['address_space_bytes']==8_000_000_000
    original=next(item for item in result['derived_sources'] if item['kind']=='exact native serialization')
    assert Path(original['path']).read_bytes()==source.read_bytes()
    rows=[json.loads(line) for line in result['path'].read_text().splitlines()]
    assert rows[0]['user_id']=='generated-a' and rows[1]['source_label']==9
    assert rows[0]['_atlas_frame_metadata_sha256']==result['metadata_sha256']
    strict={**params,'metadata_sha256':result['metadata_sha256'],'native_values_sha256':result['native_values_sha256']}
    assert module.convert_factoid(strict,{'native':source},tmp_path/'converted')['rows_sha256']==result['rows_sha256']


def test_source_pin_mismatch_and_output_alias_cannot_modify_native(tmp_path):
    import dataset_atlas.converters.factoid as module
    assert callable(getattr(module,'_launch_worker',None))
    source,params=generated_worker_source(tmp_path);original=source.read_bytes()
    with pytest.raises(ValueError,match='pin'):module.convert_factoid({**params,'source_sha256':'0'*64},{'native':source},tmp_path/'bad')
    assert source.read_bytes()==original and not (tmp_path/'bad').exists()
    output=tmp_path/'linked';output.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):module.convert_factoid(params,{'native':source},output)
    assert source.read_bytes()==original


def test_cancelled_conversion_kills_and_reaps_actual_child(tmp_path,monkeypatch):
    import dataset_atlas.converters.factoid as module
    assert callable(getattr(module,'_launch_worker',None))
    source,params=generated_worker_source(tmp_path);original=module.subprocess.Popen;children=[]
    def capture(*args,**kwargs):
        child=original(*args,**kwargs);children.append(child);return child
    monkeypatch.setattr(module.subprocess,'Popen',capture)
    calls=0
    def cancel():
        nonlocal calls
        calls+=1
        if children:raise TimeoutError('generated cancellation')
    with pytest.raises(TimeoutError):module.convert_factoid(params,{'native':source},tmp_path/'cancelled',cancel)
    assert children and all(child.poll() is not None for child in children)
    assert not (tmp_path/'cancelled').exists()


def test_bytearray_keeps_mutable_type_and_actual_shared_identity(tmp_path):
    shared=bytearray(b'generated');path=tmp_path/'bytearray.gzip'
    path.write_bytes(gzip.compress(pickle.dumps([shared,shared],protocol=5)))
    ids={};parsed,_=parse_gzip(path,shared_ids=ids)
    assert type(parsed[0]) is bytearray and parsed[0] is parsed[1]
    encoded=literal(parsed,shared_ids=ids)
    assert encoded[0]['native_memo']==encoded[1]['native_memo']
    assert encoded[0]['value']=={'_atlas_native_type':'bytearray','hex':shared.hex()}


def test_memo_slot_reuse_refuses_ambiguous_shared_identity(tmp_path):
    path=tmp_path/'reuse.gzip';path.write_bytes(gzip.compress(b'](]q\x00h\x00]q\x00h\x00e.'))
    with pytest.raises(ValueError,match='reuse'):parse_gzip(path,shared_ids={})


def test_constructor_kinds_and_placement_metadata_are_distinguished():
    from dataset_atlas.converters.factoid import frame_metadata
    value=frame();before=frame_metadata(value)
    value.kind='NEWOBJ'
    assert before!=frame_metadata(value)
    meta=frame_metadata(value)
    assert meta['frame_kind']=='NEWOBJ'
    assert meta['manager_kind']==meta['axes'][0]['constructor_kind']=='REDUCE'
    assert meta['blocks'][0]['constructor_kind']==meta['blocks'][0]['placement_metadata']['kind']=='REDUCE'



def test_unrecognized_binary_array_build_state_is_refused():
    value=ndarray((1,),[7],'i8');value.state={'generated_unrecognized_state':'keep'}
    with pytest.raises(ValueError,match='state'):array(value)


def test_cached_semantic_pins_reject_rewritten_rows(tmp_path):
    import hashlib,json
    from dataset_atlas.converters import digest_existing
    from dataset_atlas.converters import factoid as module
    source,params=generated_worker_source(tmp_path);directory=tmp_path/'converted'
    result=module.convert_factoid(params,{'native':source},directory)
    strict={**params,'metadata_sha256':result['metadata_sha256'],'native_values_sha256':result['native_values_sha256']}
    target=result['path'];rows=[json.loads(line) for line in target.read_text().splitlines()]
    rows[0]['user_id']='generated-rewritten'
    target.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
    receipt=directory/'conversion-result.json';manifest=json.loads(receipt.read_text())
    manifest['result']['file_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    manifest['result'].update(digest_existing(target,'jsonl'));receipt.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):module.convert_factoid(strict,{'native':source},directory)


def test_cached_missing_required_derived_files_are_refused(tmp_path):
    import json
    from dataset_atlas.converters import factoid as module
    source,params=generated_worker_source(tmp_path);directory=tmp_path/'converted'
    result=module.convert_factoid(params,{'native':source},directory)
    params={**params,'metadata_sha256':result['metadata_sha256'],'native_values_sha256':result['native_values_sha256']}
    receipt=directory/'conversion-result.json';manifest=json.loads(receipt.read_text())
    manifest['result']['derived_sources']=[];receipt.write_text(json.dumps(manifest))
    for entry in result['derived_sources']:
        path=Path(entry['path']);path.chmod(0o644);path.unlink()
    with pytest.raises(ValueError):module.convert_factoid(params,{'native':source},directory)


def test_cached_fifo_is_refused_without_opening_it(tmp_path):
    from dataset_atlas.converters import factoid as module
    source,params=generated_worker_source(tmp_path);directory=tmp_path/'converted'
    result=module.convert_factoid(params,{'native':source},directory)
    params={**params,'metadata_sha256':result['metadata_sha256'],'native_values_sha256':result['native_values_sha256']}
    target=result['path'];target.unlink();os.mkfifo(target)
    # Existing code blocks on the FIFO, so the external alarm is a regression guard.
    import signal
    def alarm(*args):raise TimeoutError('generated external alarm')
    previous=signal.signal(signal.SIGALRM,alarm);signal.alarm(2)
    try:
        with pytest.raises(ValueError):module.convert_factoid(params,{'native':source},directory)
    finally:signal.alarm(0);signal.signal(signal.SIGALRM,previous)


def test_cached_validation_is_cancelled_and_child_reaped(tmp_path,monkeypatch):
    from dataset_atlas.converters import factoid as module
    source,params=generated_worker_source(tmp_path);directory=tmp_path/'converted'
    result=module.convert_factoid(params,{'native':source},directory)
    params={**params,'metadata_sha256':result['metadata_sha256'],'native_values_sha256':result['native_values_sha256']}
    original=module.subprocess.Popen;children=[]
    def capture(*args,**kwargs):
        child=original(*args,**kwargs);children.append(child);return child
    monkeypatch.setattr(module.subprocess,'Popen',capture)
    def cancel():
        if children:raise TimeoutError('generated cache cancellation')
    with pytest.raises(TimeoutError):module.convert_factoid(params,{'native':source},directory,cancel)
    assert children and all(child.poll() is not None for child in children)


def test_cached_native_source_alone_cannot_attest_rewritten_semantics(tmp_path):
    from dataset_atlas.converters import factoid as module
    source,params=generated_worker_source(tmp_path);directory=tmp_path/'converted'
    module.convert_factoid(params,{'native':source},directory)
    with pytest.raises(ValueError,match='trusted immutable semantic pins'):
        module.convert_factoid(params,{'native':source},directory)


def test_cached_parent_returns_only_privately_validated_result(tmp_path,monkeypatch):
    import json
    from dataset_atlas.converters import factoid as module
    source,params=generated_worker_source(tmp_path);directory=tmp_path/'converted'
    result=module.convert_factoid(params,{'native':source},directory)
    params={**params,'metadata_sha256':result['metadata_sha256'],'native_values_sha256':result['native_values_sha256']}
    launch=module._launch_worker
    def mutate_after_validation(*args,**kwargs):
        launch(*args,**kwargs)
        receipt=directory/'conversion-result.json';manifest=json.loads(receipt.read_text())
        manifest['result'].update(path=str(directory/'generated-missing.jsonl'),count=12345,native_values_sha256='0'*64)
        receipt.write_text(json.dumps(manifest))
    monkeypatch.setattr(module,'_launch_worker',mutate_after_validation)
    actual=module.convert_factoid(params,{'native':source},directory)
    assert actual['path']==result['path'] and actual['count']==2 and actual['native_values_sha256']==result['native_values_sha256']


def test_native_array_object_alias_is_retained_in_frame_metadata():
    from dataset_atlas.converters.factoid import frame_metadata
    value=frame();native=value.state['_mgr'].args[0][0].args[0]
    metadata=frame_metadata(value,shared_ids={id(native):734})
    assert metadata['blocks'][0]['array_metadata']['native_memo']==734


def test_counter_newobj_is_not_reinterpreted_as_reduce_counts():
    value=node('collections.Counter',({'generated':4},));value.kind='NEWOBJ'
    with pytest.raises(ValueError,match='Counter'):literal(value)


def test_binary_constructor_newobj_is_refused_instead_of_reinterpreted():
    value=ndarray((1,),[7],'i8');value.kind='NEWOBJ'
    with pytest.raises(ValueError,match='constructor'):array(value)


def test_outer_preparation_process_group_stop_includes_inert_worker(tmp_path):
    import signal,subprocess,sys,time
    pid_file=tmp_path/'generated-child.pid'
    script=tmp_path/'generated-parent.py'
    script.write_text("import subprocess,sys\nfrom pathlib import Path\nfrom dataset_atlas.converters import factoid as f\noriginal=subprocess.Popen\ndef spawn(*args,**kwargs):\n child=original([sys.executable,'-c','import time; time.sleep(60)'],**kwargs)\n Path("+repr(str(pid_file))+").write_text(str(child.pid))\n return child\nf.subprocess.Popen=spawn\nf._launch_worker(Path('generated-unused-request'))\n")
    parent=subprocess.Popen([sys.executable,str(script)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    child=None
    def alive(pid):
        path=Path('/proc')/str(pid)/'stat'
        try:return path.read_text().split(') ')[1].split()[0]!='Z'
        except (FileNotFoundError,ProcessLookupError):return False  # a process that exits mid-read raises ESRCH
    try:
        deadline=time.monotonic()+5
        while not pid_file.exists() and time.monotonic()<deadline:time.sleep(.01)
        assert pid_file.exists();child=int(pid_file.read_text())
        os.killpg(parent.pid,signal.SIGKILL);parent.wait(timeout=3)
        deadline=time.monotonic()+1
        while alive(child) and time.monotonic()<deadline:time.sleep(.01)
        assert not alive(child),'Inert child survived the preparation process-group stop'
    finally:
        if parent.poll() is None:os.killpg(parent.pid,signal.SIGKILL);parent.wait(timeout=3)
        if child and alive(child):os.kill(child,signal.SIGKILL)
