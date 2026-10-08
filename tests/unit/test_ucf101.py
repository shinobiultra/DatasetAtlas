import hashlib,json,zipfile
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.ucf101 import UCF101Adapter
from dataset_atlas.adapters.structured_collection import _LocalArchive


def fixture_adapter(tmp_path, *, invalid_class=False, duplicate=False):
    annotation=tmp_path/'recognition.zip';videos=tmp_path/'videos.zip'
    with zipfile.ZipFile(annotation,'w') as z:
        z.writestr('splits/classInd.txt','1 Running\n2 Walking\n')
        for fold in range(1,4):
            train='Running/v1.avi '+('2' if invalid_class else '1')+'\n'
            z.writestr(f'splits/trainlist{fold:02d}.txt',train)
            z.writestr(f'splits/testlist{fold:02d}.txt',('Running/v1.avi' if duplicate else 'Walking/v2.avi')+'\n')
    with zipfile.ZipFile(videos,'w') as z:
        for member in ['Running/v1.avi','Walking/v2.avi']:z.writestr('UCF-101/'+member,b'fixture')
    with zipfile.ZipFile(videos) as z:
        inventory=[[i.filename,i.file_size,i.compress_size,i.CRC,i.compress_type,i.header_offset] for i in z.infolist()]
    digest=hashlib.sha256(json.dumps(inventory,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    d=Dataset(id='ucf-fixture',name='Fixture',adapter='ucf101',adapter_config={'annotations':[],
        'recognition_path':str(annotation),'remote_archives':{'videos':{'etag':'"fixture"'}},'video_prefix':'UCF-101/',
        'expected_count':2,'expected_classes':2,'directory_members_sha256':digest,'mapping':{'media_modality':'video'}})
    a=UCF101Adapter(d);a._remote=lambda key,budget:_LocalArchive(videos,budget)
    return a


def test_native_three_fold_rows_and_video_members_join_without_changing_meaning(tmp_path):
    a=fixture_adapter(tmp_path);proof=a.validate_media(100000)
    records=a.iter_records(a.prepare(a.plan(10,100000))).records
    assert proof['referenced_videos']==2 and len(records)==2
    assert records[0].source['native_class']=='Running'
    assert [records[0].source[f'split_{fold}'] for fold in range(1,4)]==['train']*3
    assert len(records[0].source['native_split_rows'])==3
    assert records[0].source['native_split_rows'][0]['native_line']=='Running/v1.avi 1'
    assert records[0].assets[0].modality=='video' and records[0].assets[0].metadata['source_format']=='AVI'
    a.config['directory_members_sha256']='0'*64
    with pytest.raises(ValueError,match='directory and recognition'):a.validate_media(100000)


@pytest.mark.parametrize('invalid_class,duplicate',[(True,False),(False,True)])
def test_native_split_errors_fail_before_activation(tmp_path,invalid_class,duplicate):
    a=fixture_adapter(tmp_path,invalid_class=invalid_class,duplicate=duplicate)
    with pytest.raises(ValueError,match='class disagrees|Duplicate or invalid'):a._rows()


def test_avi_display_checks_exact_decoded_frame_parity_and_keeps_original(tmp_path):
    import shutil,subprocess
    from dataset_atlas.storage.video import verify_avi,browser_video_render
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg unavailable')
    path=tmp_path/'fixture.avi'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=32x24:rate=5:duration=1',
        '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','mpeg4','-c:a','libmp3lame','-threads','1',str(path)],
        check=True,timeout=20,capture_output=True)
    native=path.read_bytes();assert verify_avi(native)['format']['format_name']=='avi'
    display,proof=browser_video_render(native)
    assert native==path.read_bytes() and display[4:8]==b'ftyp'
    assert proof['frames_verified']==5 and proof['original_sha256']==hashlib.sha256(native).hexdigest()
    with pytest.raises(ValueError,match='bounds'):browser_video_render(native,max_output_bytes=100)


def test_forged_avi_frame_headers_cannot_hide_actual_decode_bounds(tmp_path):
    import shutil,subprocess,struct
    from dataset_atlas.storage.video import verify_avi
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg unavailable')
    path=tmp_path/'forged.avi'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:size=16x16:rate=1000',
        '-frames:v','10001','-c:v','mpeg4','-threads','1',str(path)],check=True,timeout=20,capture_output=True)
    data=bytearray(path.read_bytes())
    struct.pack_into('<I',data,data.index(b'avih')+8+16,1)
    struct.pack_into('<I',data,data.index(b'strh')+8+32,1)
    with pytest.raises(ValueError,match='actual decoded-frame'):verify_avi(bytes(data))


def test_decoder_cancellation_reaps_process_group(tmp_path):
    import sys,threading,time
    from dataset_atlas.storage.video import _bounded
    event=threading.Event();timer=threading.Timer(.1,event.set);timer.start()
    def check():
        if event.is_set():raise InterruptedError('synthetic cancellation')
    start=time.monotonic()
    with pytest.raises(InterruptedError):
        _bounded([sys.executable,'-c','import time; time.sleep(10)'],deadline=time.monotonic()+5,cancel=check)
    timer.join();assert time.monotonic()-start<1
    with pytest.raises(ValueError,match='output/decode bounds'):
        _bounded([sys.executable,'-c','import sys;sys.stdout.write("x"*100000)'],deadline=time.monotonic()+5,stdout_limit=100)


def test_cancellation_after_pipe_eof_does_not_leave_child_running(tmp_path):
    import sys,time,threading
    from dataset_atlas.storage.video import _bounded
    marker=tmp_path/'must-not-exist';event=threading.Event();timer=threading.Timer(.1,event.set);timer.start()
    def check():
        if event.is_set():raise InterruptedError('synthetic cancellation')
    command=[sys.executable,'-c','import os,time,pathlib,sys;os.close(1);os.close(2);time.sleep(.5);pathlib.Path(sys.argv[1]).touch()',str(marker)]
    start=time.monotonic()
    with pytest.raises(InterruptedError):_bounded(command,deadline=time.monotonic()+5,cancel=check)
    timer.join();assert time.monotonic()-start<.5 and not marker.exists()


def test_deadline_kills_pipe_holding_descendant_after_leader_exits(tmp_path):
    import sys,time
    from dataset_atlas.storage.video import _bounded
    marker=tmp_path/'descendant-must-not-write'
    child='import time,pathlib,sys;time.sleep(.5);pathlib.Path(sys.argv[1]).touch()'
    parent='import subprocess,sys;subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]])'
    with pytest.raises(ValueError,match='time bounds'):
        _bounded([sys.executable,'-c',parent,child,str(marker)],deadline=time.monotonic()+.15)
    time.sleep(.55)
    assert not marker.exists()
