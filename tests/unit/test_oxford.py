import io
import tarfile
from dataset_atlas.adapters.oxford import OxfordArchiveAdapter
from dataset_atlas.models import Dataset


def archive(path, members):
    with tarfile.open(path,'w:gz') as output:
        for name,data in members.items():
            item=tarfile.TarInfo(name);item.size=len(data);output.addfile(item,io.BytesIO(data))


def test_pets_preserves_annotation_labels_splits_and_last_record(tmp_path):
    path=tmp_path/'images.tar.gz';annotations=tmp_path/'annotations.tar.gz'
    archive(path,{'images/cat_1.jpg':b'fixture','images/dog_2.jpg':b'fixture'})
    archive(annotations,{'annotations/trainval.txt':b'cat_1 1 1 1\n','annotations/test.txt':b'dog_2 2 2 1\n'})
    dataset=Dataset(id='pets',name='Pets',release='r',snapshot_id='s',adapter='oxford_archive',
        adapter_config={'path':str(path),'annotations_archive':str(annotations),'dataset_kind':'pets'})
    adapter=OxfordArchiveAdapter(dataset);source=adapter.prepare(adapter.plan(10,10000))
    rows=adapter.iter_records(source).records
    assert len(rows)==2 and rows[1].source['split']=='test'
    assert rows[0].source['species_id']==1 and rows[1].source['breed']=='dog'
    assert adapter.resolve_asset(source,rows[1].assets[0].uri).data==b'fixture'


def test_dtd_preserves_all_ten_partitions(tmp_path):
    path=tmp_path/'dtd.tar.gz';members={'dtd/images/striped/1.jpg':b'image'}
    for i in range(1,11):
        for split in ('train','val','test'):members[f'dtd/labels/{split}{i}.txt']=b'striped/1.jpg\n' if split=='test' else b''
    archive(path,members)
    dataset=Dataset(id='dtd',name='DTD',release='r',snapshot_id='s',adapter='oxford_archive',adapter_config={'path':str(path),'dataset_kind':'dtd'})
    adapter=OxfordArchiveAdapter(dataset);source=adapter.prepare(adapter.plan(10,10000))
    row=adapter.iter_records(source).records[0]
    assert row.source['label']=='striped' and all(row.source[f'split_{i}']=='test' for i in range(1,11))


def test_decoded_media_cache_retains_original_bytes(tmp_path,monkeypatch):
    from dataset_atlas.adapters.core import resolve_dataset_asset,DirectoryArchiveAdapter
    path=tmp_path/'images.tar.gz';archive(path,{'image.jpg':b'exact original fixture bytes'})
    dataset=Dataset(id='cache-test',name='Cache test',release='r',snapshot_id='s',adapter='archive',adapter_config={'path':str(path)})
    first=resolve_dataset_asset(dataset,'image.jpg',cache_root=tmp_path/'cache')
    def no_archive(*args,**kwargs):raise AssertionError('Archive was read again')
    monkeypatch.setattr(DirectoryArchiveAdapter,'resolve_asset',no_archive)
    second=resolve_dataset_asset(dataset,'image.jpg',cache_root=tmp_path/'cache')
    assert second==first
    import pytest
    with pytest.raises(ValueError,match='byte budget'):resolve_dataset_asset(dataset,'image.jpg',max_bytes=1,cache_root=tmp_path/'cache')
