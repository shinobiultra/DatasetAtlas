import hashlib
import json

import pytest

from dataset_atlas.adapters.inventory_variants import InventoryVariantsAdapter
from dataset_atlas.models import Dataset


def test_inventory_joins_scale_specific_reference_and_low_resolution_files(tmp_path):
    entries = {f'X{scale}/001_{role}.png': {'bytes': 10, 'git_blob_sha1': 'a'*40}
               for scale in [2, 3] for role in ['HR', 'LR']}
    payload = json.dumps({'files': entries}).encode()
    path = tmp_path/'inventory.json'
    path.write_bytes(payload)
    config = {'annotations': [], 'media_inventory_path': str(path), 'media_inventory_sha256': hashlib.sha256(payload).hexdigest(),
              'member_regex': r'X(?P<scale>[23])/(?P<image_id>\d{3})_(?P<role>HR|LR)\.png',
              'variant_template': '{scale}_{role}', 'variant_note': 'Fixture variants', 'expected_variants': ['2_HR', '2_LR', '3_HR', '3_LR']}
    dataset = Dataset(id='variants', name='Fixture', adapter='inventory_variants', adapter_config=config)
    adapter = InventoryVariantsAdapter(dataset)
    rows = adapter.iter_records(adapter.prepare(adapter.plan(10, 100000))).records
    assert len(rows) == 1 and len(rows[0].assets) == 4
    assert [a.metadata['downscale_factor'] for a in rows[0].assets] == [2, 2, 3, 3]
    assert adapter.validate_media(100000)['referenced_images'] == 4
    dataset.adapter_config['expected_variants'].append('4_HR')
    with pytest.raises(ValueError, match='incomplete variant set'):
        InventoryVariantsAdapter(dataset)._rows()
