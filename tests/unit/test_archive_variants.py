import zipfile

import pytest

from dataset_atlas.adapters.archive_variants import ArchiveVariantsAdapter
from dataset_atlas.adapters.structured_collection import _LocalArchive
from dataset_atlas.models import Dataset


def test_archive_member_ids_join_native_hr_and_lr_without_fabricating_images(tmp_path):
    archives = {}
    paths = {}
    for variant in ['HR', 'LR']:
        path = tmp_path/(variant+'.zip')
        with zipfile.ZipFile(path, 'w') as z:
            for identity in ['0001', '0002']:
                z.writestr(f'{variant}/{identity}.png', b'fixture')
        paths[variant] = path
        archives[variant] = {'member_regex': variant+r'/(?P<image_id>\d{4})\.png', 'split': 'train',
                             'variant': variant, 'role': variant, 'expected_count': 2, 'etag': '"fixture"'}
    dataset = Dataset(id='variants', name='Fixture', adapter='archive_variants', adapter_config={
        'annotations': [], 'remote_archives': archives, 'expected_variants': ['HR', 'LR']})
    adapter = ArchiveVariantsAdapter(dataset)
    adapter._remote = lambda key, budget: _LocalArchive(paths[key], budget)
    rows = adapter.iter_records(adapter.prepare(adapter.plan(10, 100000))).records
    assert len(rows) == 2 and [a.metadata['condition'] for a in rows[0].assets] == ['HR', 'LR']
    assert rows[0].source['native_id'] == '0001'
    assert adapter.validate_media(100000)['referenced_images'] == 4
    dataset.adapter_config['remote_archives']['LR']['expected_count'] = 3
    other = ArchiveVariantsAdapter(dataset)
    other._remote = adapter._remote
    with pytest.raises(ValueError, match='population differs'):
        other._rows()


def test_native_folder_labels_remain_filterable_and_cannot_overwrite_identity(tmp_path):
    path = tmp_path/'images.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('images/n00000001/example.JPEG', b'fixture')
    spec = {'member_regex': r'images/(?P<image_id>(?P<class_id>n\d{8})/[^/]+)\.JPEG',
            'split': 'train', 'variant': 'original', 'role': 'original', 'expected_count': 1,
            'source_fields': {'class_id': '{class_id}'}, 'etag': '"fixture"'}
    d = Dataset(id='folders', name='Fixture', adapter='archive_variants', adapter_config={
        'annotations': [], 'remote_archives': {'images': spec}, 'expected_variants': ['original']})
    adapter = ArchiveVariantsAdapter(d)
    adapter._remote = lambda key, budget: _LocalArchive(path, budget)
    row = adapter.iter_records(adapter.prepare(adapter.plan(10, 100000))).records[0]
    assert row.source['class_id'] == 'n00000001'
    assert row.source['native_id'] == 'n00000001/example'
    for field in ['split', '_atlas_media_refs', 'native_id']:
        d.adapter_config['remote_archives']['images']['source_fields'] = {field: 'changed'}
        invalid = ArchiveVariantsAdapter(d)
        invalid._remote = adapter._remote
        with pytest.raises(ValueError, match='reserved'):
            invalid._rows()


def test_media_reads_need_only_their_own_archive_even_when_another_archive_is_gone(tmp_path):
    """Regression: a publisher moved DIV2K's validation archive and every media read failed, because each read re-opened all 22 archives."""
    import io
    from PIL import Image
    stream = io.BytesIO()
    Image.new('RGB', (4, 3), (9, 8, 7)).save(stream, format='PNG')
    native = stream.getvalue()
    good = tmp_path/'HR.zip'
    with zipfile.ZipFile(good, 'w') as z:
        z.writestr('HR/0001.png', native)
    specs = {key: {'member_regex': key+r'/(?P<image_id>\d{4})\.png', 'split': 'train', 'variant': key, 'role': key, 'expected_count': 1, 'etag': '"fixture"'}
             for key in ('HR', 'LR')}
    dataset = Dataset(id='moved', name='Fixture', adapter='archive_variants', adapter_config={
        'annotations': [], 'remote_archives': specs, 'expected_variants': ['HR', 'LR']})
    opened = []

    def remote(key, budget):
        opened.append(key)
        if key == 'LR':
            raise ValueError('Range source requires HTTP 206; received 404')
        return _LocalArchive(good, budget)

    adapter = ArchiveVariantsAdapter(dataset)
    adapter._remote = remote
    with pytest.raises(ValueError, match='received 404'):
        adapter.prepare(adapter.plan(10, 100000))  # preparation still validates the whole release and refuses a missing archive
    opened.clear()
    source = adapter.prepare_media(adapter.plan(10, 100000))
    assert opened == []  # no archive directory is opened just to start a media read
    handle = adapter.resolve_asset(source, 'zip/HR/HR/0001.png')
    assert handle.data == native and opened == ['HR']


def test_selected_native_subtree_pins_all_members_and_explicit_exclusions(tmp_path):
    import hashlib,json
    path=tmp_path/'bundle.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('states/images/rough_rock/1.jpg',b'fixture')
        z.writestr('states/images/readme.txt',b'passive metadata')
        z.writestr('other/images/1.jpg',b'excluded fixture')
    with zipfile.ZipFile(path) as z:
        inventory=[[i.filename,i.file_size,i.compress_size,i.CRC,i.compress_type,i.header_offset] for i in z.infolist()]
    digest=hashlib.sha256(json.dumps(inventory,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    spec={'member_regex':r'states/images/(?P<image_id>(?P<pair>[^/]+)/[^/]+)\.jpg','split':'mirror','variant':'source','role':'mirror_source','expected_count':1,'etag':'"fixture"',
          'selected_prefix':'states/images/','ignored_members':['states/images/readme.txt'],'expected_excluded_members':1,'directory_members_sha256':digest,
          'source_fields':{'native_pair':'{pair}'}}
    d=Dataset(id='states',name='Fixture',adapter='archive_variants',adapter_config={'annotations':[],'remote_archives':{'images':spec},'expected_variants':['source']})
    a=ArchiveVariantsAdapter(d);a._remote=lambda key,budget:_LocalArchive(path,budget)
    records=a.iter_records(a.prepare(a.plan(10,100000))).records
    assert len(records)==1 and records[0].source['native_pair']=='rough_rock'
    spec['expected_excluded_members']=0
    other=ArchiveVariantsAdapter(d);other._remote=a._remote
    with pytest.raises(ValueError,match='Excluded archive population'):other._rows()
    spec['expected_excluded_members']=1;spec['directory_members_sha256']='0'*64
    other=ArchiveVariantsAdapter(d);other._remote=a._remote
    with pytest.raises(ValueError,match='fingerprint changed'):other._rows()
