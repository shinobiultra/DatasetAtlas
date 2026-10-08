import json
import zipfile

import pyarrow.parquet as pq
import pytest

from dataset_atlas.converters.celeba import celeba_native


def native_fixture(tmp_path):
    """Synthetic native file shapes; these records never enter published coverage."""
    inputs = {}
    values = {
        'attributes': '2\nSmiling Male\n000002.jpg -1 1\n000001.jpg 1 -1\n',
        'bbox': '2\nimage_id x_1 y_1 width height\n000001.jpg 10 20 30 40\n000002.jpg 11 21 31 41\n',
        'landmarks_align': '2\nlefteye_x lefteye_y righteye_x righteye_y nose_x nose_y leftmouth_x leftmouth_y rightmouth_x rightmouth_y\n000001.jpg 1 2 3 4 5 6 7 8 9 10\n000002.jpg 11 12 13 14 15 16 17 18 19 20\n',
        'partitions': '000001.jpg 2\n000002.jpg 0\n',
    }
    for key, value in values.items():
        inputs[key] = tmp_path / (key + '.txt')
        inputs[key].write_text(value)
    inputs['media_archive'] = tmp_path / 'images.zip'
    with zipfile.ZipFile(inputs['media_archive'], 'w') as archive:
        archive.writestr('img_align_celeba/000001.jpg', b'synthetic-fixture-one')
        archive.writestr('img_align_celeba/000002.jpg', b'synthetic-fixture-two')
    return inputs


def convert(tmp_path, inputs):
    return celeba_native({'attribute_count': 2}, inputs, tmp_path / 'converted', lambda: None)


def test_filename_join_keeps_signed_attributes_split_and_original_geometry(tmp_path):
    inputs = native_fixture(tmp_path)
    result = convert(tmp_path, inputs)
    rows = pq.read_table(result['path']).to_pylist()
    assert result['count'] == 2
    # Annotation file order differs from geometry and ZIP order: join by native filename.
    assert [row['filename'] for row in rows] == ['000002.jpg', '000001.jpg']
    assert [(row['attr_Smiling'], row['attr_Male']) for row in rows] == [(-1, 1), (1, -1)]
    assert [(row['native_partition'], row['split']) for row in rows] == [(0, 'train'), (2, 'test')]
    assert rows[0]['native_bbox'] == [11, 21, 31, 41]
    assert rows[1]['native_aligned_landmarks'] == list(range(1, 11))
    assert 'not the aligned crop' in rows[0]['bbox_coordinate_reference']
    assert 'were not acquired' in rows[0]['identity_availability']
    assert 'identity' not in rows[0]
    assert json.loads(rows[0]['native_table_rows_json'])['attributes'] == '000002.jpg -1 1'
    assert len(json.loads(rows[0]['native_table_sha256_json'])) == 4
    assert json.loads(rows[0]['native_table_headers_json'])['bbox'] == ['2', 'image_id x_1 y_1 width height']
    assert result['adapter_config']['mapping'] == {'id': 'source_id', 'media': 'media_ref'}
    assert len(result['adapter_config']['media_archive_sha256']) == 64


@pytest.mark.parametrize(('key', 'replacement', 'message'), [
    ('partitions', '000001.jpg 2\n000003.jpg 0\n', 'filename joins differ'),
    ('partitions', '000001.jpg 2\n000002.jpg 3\n', 'partition code changed'),
    ('attributes', '2\nSmiling Male\n000002.jpg 0 1\n000001.jpg 1 -1\n', 'signed attribute label changed'),
    ('attributes', '3\nSmiling Male\n000002.jpg -1 1\n000001.jpg 1 -1\n', 'declared table count differs'),
    ('attributes', '2\nSmiling Male\n000002.jpg -1 1\n000002.jpg 1 -1\n', 'Duplicate native CelebA filename'),
    ('attributes', '2\nSmiling Male\n../one.jpg -1 1\n000001.jpg 1 -1\n', 'row shape changed'),
])
def test_changed_native_table_membership_and_codes_fail_closed(tmp_path, key, replacement, message):
    inputs = native_fixture(tmp_path)
    inputs[key].write_text(replacement)
    with pytest.raises(ValueError, match=message):
        convert(tmp_path, inputs)


@pytest.mark.parametrize('member', ['img_align_celeba/000003.jpg', '../000002.jpg'])
def test_archive_membership_must_match_exact_native_filenames(tmp_path, member):
    inputs = native_fixture(tmp_path)
    with zipfile.ZipFile(inputs['media_archive'], 'w') as archive:
        archive.writestr('img_align_celeba/000001.jpg', b'fixture')
        archive.writestr(member, b'fixture')
    with pytest.raises(ValueError, match='memberships differ|unsafe native'):
        convert(tmp_path, inputs)


def test_archive_symlink_is_rejected(tmp_path):
    inputs = native_fixture(tmp_path)
    member = zipfile.ZipInfo('img_align_celeba/000002.jpg')
    member.create_system = 3
    member.external_attr = 0o120777 << 16
    with zipfile.ZipFile(inputs['media_archive'], 'w') as archive:
        archive.writestr('img_align_celeba/000001.jpg', b'fixture')
        archive.writestr(member, b'outside')
    with pytest.raises(ValueError, match='unsafe native'):
        convert(tmp_path, inputs)
