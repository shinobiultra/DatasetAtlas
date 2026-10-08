"""Synthetic native-table joins and bounded RAR stream contracts; no real coverage."""
import io,json,sys,tempfile,time,zlib
from types import SimpleNamespace
import zipfile

from PIL import Image
import pytest

from dataset_atlas.converters import tid2013


def bmp():
    stream=io.BytesIO();Image.new('RGB',(4,3),(10,40,90)).save(stream,'BMP');return stream.getvalue()


def files():
    image=bmp()
    return [('reference_images/I01.BMP',image),('distorted_images/i01_01_1.bmp',image),('distorted_images/i01_01_2.bmp',image),
        ('mos_with_names.txt',b'1.25 i01_01_1.bmp\r\n2.50 i01_01_2.bmp\r\n'),('mos.txt',b'1.25\n2.50\n'),
        ('mos_std.txt',b'0.25\n0.50\n'),('metrics_values/fixture.txt',b'NaN\n3.5\n')]


def test_native_bmp_bytes_score_lines_missing_metrics_and_reference_joins_are_preserved(tmp_path,monkeypatch):
    source=tmp_path/'source.rar';source.write_bytes(b'synthetic archive header')
    monkeypatch.setattr(tid2013,'_members',lambda *_:iter(files()))
    result=tid2013.tid2013_native({'reference_count':1,'distorted_count':2},{'archive_path':source},tmp_path/'out',lambda:None)
    rows=[json.loads(line) for line in result['path'].read_text().splitlines()]
    assert [row['mos'] for row in rows]==[1.25,2.5]
    assert rows[0]['native_table_rows']['mos_with_names.txt']['line']=='1.25 i01_01_1.bmp\r\n'
    assert rows[0]['native_metric_values']['metrics_values/fixture.txt'] is None
    assert rows[0]['reference_index']==1 and rows[0]['distortion_type_index']==1 and rows[0]['distortion_level_index']==1
    with zipfile.ZipFile(result['adapter_config']['native_media_archive_path']) as archive:
        assert {name:archive.read(name) for name,_ in files()}==dict(files())


def test_mos_tables_that_disagree_or_name_missing_images_are_refused(tmp_path,monkeypatch):
    source=tmp_path/'source.rar';source.write_bytes(b'synthetic archive header')
    native=dict(files());native['mos.txt']=b'9.25\n2.50\n'
    monkeypatch.setattr(tid2013,'_members',lambda *_:iter(native.items()))
    with pytest.raises(ValueError,match='MOS tables disagree'):
        tid2013.tid2013_native({'reference_count':1,'distorted_count':2},{'archive_path':source},tmp_path/'out',lambda:None)


@pytest.mark.parametrize('defect',['none','crc','unsafe_path','expansion'])
def test_rar_metadata_and_stream_crc_are_checked_before_native_members_are_returned(tmp_path,monkeypatch,defect):
    data=bmp();entry=SimpleNamespace(filename='../escape.bmp' if defect=='unsafe_path' else 'one.bmp',file_size=len(data),
        CRC=zlib.crc32(data)^(1 if defect=='crc' else 0),isdir=lambda:False,is_symlink=lambda:False,needs_password=lambda:False,file_redir=None)
    class Archive:
        def __init__(self,_):pass
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def infolist(self):return [entry]
    class Process:
        stdout=tempfile.TemporaryFile()
        stdout.write(data);stdout.seek(0)
        returncode=0
        def wait(self,timeout):return 0
        def poll(self):return 0
    commands=[]
    def launch(command,**kwargs):commands.append(command);assert kwargs['stderr']==tid2013.subprocess.DEVNULL;return Process()
    monkeypatch.setitem(sys.modules,'rarfile',SimpleNamespace(RarFile=Archive));monkeypatch.setattr(tid2013.shutil,'which',lambda _:'7zip-fixture')
    monkeypatch.setattr(tid2013.subprocess,'Popen',launch)
    if defect=='none':
        assert list(tid2013._members(tmp_path/'source.rar',lambda:None,100000))==[('one.bmp',data)]
        assert commands[0][1]=='x' and '-so' in commands[0] and '--' in commands[0] and '-mmt=1' in commands[0]
    else:
        with pytest.raises(ValueError):list(tid2013._members(tmp_path/'source.rar',lambda:None,1 if defect=='expansion' else 100000))
        if defect in {'unsafe_path','expansion'}:assert not commands


@pytest.mark.parametrize('tail',[False,True])
def test_stalled_decoder_cancellation_kills_reaps_and_closes_child(tmp_path,monkeypatch,tail):
    data=b'generated fixture bytes'
    entry=SimpleNamespace(filename='one.txt',file_size=len(data),CRC=zlib.crc32(data),isdir=lambda:False,
        is_symlink=lambda:False,needs_password=lambda:False,file_redir=None)
    class Archive:
        def __init__(self,_):pass
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def infolist(self):return [entry]
    monkeypatch.setitem(sys.modules,'rarfile',SimpleNamespace(RarFile=Archive))
    monkeypatch.setattr(tid2013.shutil,'which',lambda _:'generated-decoder')
    launch=tid2013.subprocess.Popen;children=[]
    def child(*_,**kwargs):
        script=('import sys,time;sys.stdout.buffer.write('+repr(data)+');sys.stdout.flush();time.sleep(10)' if tail else 'import time;time.sleep(10)')
        process=launch([sys.executable,'-c',script],**kwargs);children.append(process);return process
    monkeypatch.setattr(tid2013.subprocess,'Popen',child)
    started=time.monotonic()
    def check():
        if time.monotonic()-started>0.2:raise InterruptedError('generated cancellation')
    with pytest.raises(InterruptedError):list(tid2013._members(tmp_path/'fixture.rar',check,100000))
    assert time.monotonic()-started<2
    assert len(children)==1 and children[0].poll() is not None and children[0].stdout.closed
