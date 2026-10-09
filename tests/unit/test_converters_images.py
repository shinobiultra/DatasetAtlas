"""Numeric image arrays become lossless PNGs, verified by decoding them back, in the documented class round-robin order."""
import numpy as np
import pytest
from PIL import Image

from dataset_atlas.converters import CONVERTERS, digest_existing, images  # noqa: F401

PARAMS = {'count': 6, 'image_shape': [2, 2, 3], 'release_variant': 'v6', 'class_names': ['a', 'b', 'c']}


def arrays(tmp_path, labels=(0, 0, 1, 1, 2, 2)):
    data = np.arange(6 * 2 * 2 * 3, dtype=np.uint8).reshape(6, 2, 2, 3)
    np.save(tmp_path / 'data.npy', data)
    np.save(tmp_path / 'labels.npy', np.array(labels, dtype=np.int32))
    return {'data_npy': tmp_path / 'data.npy', 'labels_npy': tmp_path / 'labels.npy'}, data


def test_rows_follow_a_class_round_robin_but_keep_the_original_row_index_as_identity(tmp_path):
    inputs, data = arrays(tmp_path)
    result = CONVERTERS['npy_images_round_robin'](PARAMS, inputs, tmp_path / 'out', lambda: None)
    import pyarrow.parquet as pq
    rows = pq.read_table(result['path']).to_pylist()
    assert [r['source_index'] for r in rows] == [0, 2, 4, 1, 3, 5]  # class a, b, c, then the second of each
    assert [r['class_name'] for r in rows[:3]] == ['a', 'b', 'c']
    assert rows[0]['source_id'] == '0' and rows[1]['image'] == '0002.png' and isinstance(rows[0]['label'], int)
    assert digest_existing(result['path'], 'parquet')['rows_sha256'] == result['rows_sha256']
    assert np.array_equal(np.asarray(Image.open(result['media_dir'] / '0004.png')), data[4])


def test_wrong_shape_or_unbalanced_classes_are_refused(tmp_path):
    inputs, _ = arrays(tmp_path, labels=(0, 0, 0, 1, 2, 2))
    with pytest.raises(ValueError, match='class counts'):
        CONVERTERS['npy_images_round_robin'](PARAMS, inputs, tmp_path / 'o1', lambda: None)
    inputs, _ = arrays(tmp_path)
    with pytest.raises(ValueError, match='shape or dtype'):
        CONVERTERS['npy_images_round_robin']({**PARAMS, 'image_shape': [3, 3, 3]}, inputs, tmp_path / 'o2', lambda: None)


def test_pickled_arrays_are_never_loaded(tmp_path):
    np.save(tmp_path / 'data.npy', np.array([{'x': 1}], dtype=object), allow_pickle=True)
    np.save(tmp_path / 'labels.npy', np.array([0], dtype=np.int32))
    with pytest.raises(ValueError, match='pickle'):
        CONVERTERS['npy_images_round_robin'](PARAMS, {'data_npy': tmp_path / 'data.npy', 'labels_npy': tmp_path / 'labels.npy'}, tmp_path / 'o', lambda: None)
