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
