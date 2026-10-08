import io
import pytest
from dataset_atlas.storage.parallel_ranges import ParallelRangeReader


@pytest.mark.parametrize('connections',[1,4,8])
def test_parallel_native_ranges_are_disjoint_ordered_and_budgeted(connections):
    data=bytes(range(256))*32768;calls=[]
    class Reader(io.BytesIO):
        def __init__(self,*args,**kwargs):super().__init__(data);self.bytes_fetched=0
        def read(self,size=-1):
            start=self.tell();value=super().read(size);calls.append((start,len(value)));self.bytes_fetched+=len(value);return value
    with ParallelRangeReader('https://fixture.invalid/native',size=len(data),etag='"fixture"',allowed_hosts=['fixture.invalid'],
            byte_budget=len(data)+10,reader_factory=Reader,connections=connections) as reader:
        assert reader.read(len(data))==data and reader.bytes_fetched==len(data)
        chunk=len(data)//connections
        assert sorted(calls)==[(offset,chunk) for offset in range(0,len(data),chunk)]
        reader.seek(0);assert reader.read(10)==data[:10]
        before=list(calls)
        with pytest.raises(ValueError,match='aggregate byte budget'):reader.read(1)
        assert calls==before


def test_failed_parallel_native_reads_do_not_refund_budget():
    class Reader(io.BytesIO):
        def __init__(self,*args,**kwargs):super().__init__(b'x'*(4<<20));self.bytes_fetched=0
        def read(self,size=-1):raise ValueError('Source ETag changed')
    with ParallelRangeReader('https://fixture.invalid/native',size=4<<20,etag='"fixture"',allowed_hosts=['fixture.invalid'],
            byte_budget=4<<20,reader_factory=Reader) as reader:
        with pytest.raises(ValueError,match='ETag changed'):reader.read(4<<20)
        with pytest.raises(ValueError,match='aggregate byte budget'):reader.read(1)
