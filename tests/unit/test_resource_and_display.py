import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image
from dataset_atlas.storage.display import safe_view
from dataset_atlas.jobs.limits import limits
import pytest


def test_safe_view_preserves_original_and_dimensions():
    image=Image.new('RGB',(100,80),'red')
    for x in range(50):
        for y in range(40):image.putpixel((x,y),(0,0,255))
    stream=io.BytesIO();image.save(stream,format='PNG');original=stream.getvalue()
    digest=hashlib.sha256(original).hexdigest()
    derived=safe_view(original)
    assert derived!=original and hashlib.sha256(original).hexdigest()==digest
    with Image.open(io.BytesIO(derived)) as result:assert result.size==(100,80)


@pytest.mark.parametrize('key,value',[('max_rss_bytes',0),('max_cpu_seconds',True),('max_wall_seconds',.1)])
def test_invalid_resource_limits(key,value):
    with pytest.raises(ValueError):limits({key:value})


@pytest.mark.parametrize('config,code,resource',[
    ({'max_rss_bytes':1},'import time; time.sleep(10)','max_rss_bytes'),
    ({'max_wall_seconds':1},'import time; time.sleep(10)','max_wall_seconds'),
    ({'max_cpu_seconds':1},'while True: pass','max_cpu_seconds'),
])
def test_real_worker_limits_terminate_and_leave_receipt(tmp_path,config,code,resource):
    script='from dataset_atlas.jobs.limits import install\ninstall('+repr(config)+','+repr(str(tmp_path))+')\n'+code
    process=subprocess.run([sys.executable,'-c',script],start_new_session=True,timeout=6)
    assert process.returncode!=0
    receipt=json.loads((tmp_path/'resource-error.receipt').read_text())
    assert receipt['resource']==resource and receipt['type']=='ResourceLimitExceeded'


def test_kernel_memory_cap_when_user_cgroups_are_available():
    from dataset_atlas.jobs.limits import cgroup_available,worker_command
    if not cgroup_available():pytest.skip('User cgroup delegation unavailable; watchdog tested separately')
    command=worker_command([sys.executable,'-c',"value=bytearray(256*1024*1024); value[::4096]=b'x'*(len(value)//4096)"],{'max_rss_bytes':64*1024*1024})
    result=subprocess.run(command,capture_output=True,start_new_session=True,timeout=10)
    assert result.returncode!=0,'Allocation unexpectedly exceeded kernel cgroup memory limit'
