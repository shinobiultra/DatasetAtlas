import io
import zipfile

import numpy as np
import pytest
from scipy.io import savemat

from dataset_atlas.adapters.sun397 import SUN397Adapter
from dataset_atlas.models import Dataset


def fixture(tmp_path, corrupt=False):
    classes = ['/a/abbey', '/b/bedroom']
    images = tmp_path / 'images.zip'
    partitions = tmp_path / 'partitions.zip'
    splits = np.empty((1, 2), dtype=object)
    with zipfile.ZipFile(images, 'w') as z:
        z.writestr('SUN397/ClassName.txt', '\n'.join(classes))
        for c in classes:
            for name in ['one.jpg', 'two.jpg', 'tri.jpg']:
                z.writestr('SUN397' + c + '/' + name, b'fixture')
    with zipfile.ZipFile(partitions, 'w') as z:
        z.writestr('ClassName.txt', '\n'.join(classes))
        for fold in range(2):
            tables = np.empty((1, 2), dtype=[('ClassName', object), ('Training', object), ('Testing', object)])
            for i, c in enumerate(classes):
                tables[0, i] = (c, np.array(['one.jpg']), np.array(['two.jpg', 'tri.jpg']))
            splits[0, fold] = tables
            z.writestr(f'Training_{fold+1:02}.txt', '\n'.join(c+'/one.jpg' for c in classes))
            z.writestr(f'Testing_{fold+1:02}.txt', '\n'.join(c+('/missing.jpg' if corrupt else '/two.jpg') for c in classes))
        data = io.BytesIO()
        savemat(data, {'split': splits})
        z.writestr('split10.mat', data.getvalue())
    return SUN397Adapter(Dataset(id='sun397', name='Fixture', release='r', snapshot_id='s', adapter='sun397',
        adapter_config={'path': str(images), 'partitions_path': str(partitions), 'dataset_kind': 'sun397', 'fold_count': 2, 'class_count': 2}))


def test_native_text_evaluation_subset_is_distinct_from_matlab_complement(tmp_path):
    adapter = fixture(tmp_path)
    rows = {r['image_id']: r for r in adapter._rows()}
    assert len(rows) == 6
    assert rows['/a/abbey/one.jpg']['text_training_folds'] == [1, 2]
    assert rows['/a/abbey/two.jpg']['text_testing_folds'] == [1, 2]
    assert rows['/a/abbey/tri.jpg']['text_testing_folds'] == []
    assert rows['/a/abbey/tri.jpg']['matlab_testing_folds'] == [1, 2]
    record = adapter.iter_records(adapter.prepare(adapter.plan(10, 100000))).records[0]
    assert record.assets[0].uri.startswith('SUN397/')


def test_partition_referencing_missing_native_image_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='missing images'):
        fixture(tmp_path, corrupt=True)._rows()
