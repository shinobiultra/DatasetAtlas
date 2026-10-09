import csv
import json

import pytest

from dataset_atlas.converters.open_images import open_images_validation


def fixture(tmp_path):
    inputs = {}
    values = {
        'images': 'ImageID,OriginalURL,Rotation\n0000000000000000,https://example.org/a,0\n0000000000000001,https://example.org/b,\n',
        'class_names': '/m/fixture,Fixture class\n/m/second,Second fixture\n',
        'human_labels': 'ImageID,Source,LabelName,Confidence\n0000000000000000,fixture,/m/fixture,1\n0000000000000000,fixture,/m/second,0\n',
        'boxes': 'ImageID,LabelName,XMin,XMax\n0000000000000000,/m/fixture,0.0100,0.90\n',
        'relationships': 'ImageID,LabelName1,LabelName2,RelationLabel\n0000000000000000,/m/fixture,/m/second,is\n',
        'segmentations': 'ImageID,LabelName,MaskPath\n0000000000000000,/m/fixture,0/fixture.png\n',
    }
    for key, value in values.items():
        path = tmp_path / (key + '.csv')
        path.write_text(value)
        inputs[key] = path
    return inputs


def test_preserves_all_rows_negative_labels_precision_and_empty_metadata(tmp_path):
    inputs = fixture(tmp_path)
    result = open_images_validation({'images': 2}, inputs, tmp_path / 'out', lambda: None)
    rows = [json.loads(line) for line in result['path'].read_text().splitlines()]
    assert result['native_scope_counts'] == {'images': 2, 'class_descriptions': 2, 'unlisted_class_or_attribute_ids': 0, 'human_labels': 2,
                                            'boxes': 1, 'relationships': 1, 'segmentations': 1}
    assert rows[0]['positive_image_labels'] == ['/m/fixture']
    assert rows[0]['negative_image_labels'] == ['/m/second']
    assert rows[0]['boxes'][0]['native']['XMin'] == '0.0100'
    assert rows[0]['human_labels'][1]['source_annotation_row'] == 1
    assert rows[1]['human_labels'] == [] and rows[1]['native_image_metadata']['Rotation'] == ''
    assert rows[1]['media_ref'] == 'validation/0000000000000001.jpg'
    assert set(rows[0]['native_table_sha256']) == set(inputs)
    for key in ('human_labels', 'boxes', 'relationships', 'segmentations'):
        with inputs[key].open() as stream:
            native = list(csv.DictReader(stream))
        assert [row['native'] for image in rows for row in image[key]] == native


@pytest.mark.parametrize('kind', ['duplicate_image', 'missing_image', 'missing_class', 'malformed_row', 'wrong_count', 'row_cap'])
def test_rejects_invalid_native_joins_shapes_and_bounds(tmp_path, kind):
    inputs = fixture(tmp_path)
    params = {'images': 2}
    if kind == 'duplicate_image':
        inputs['images'].write_text(inputs['images'].read_text().replace('0000000000000001', '0000000000000000'))
    elif kind == 'missing_image':
        inputs['boxes'].write_text(inputs['boxes'].read_text().replace('0000000000000000', 'ffffffffffffffff'))
    elif kind == 'missing_class':
        inputs['boxes'].write_text(inputs['boxes'].read_text().replace('/m/fixture', '/m/missing'))
    elif kind == 'malformed_row':
        inputs['boxes'].write_text(inputs['boxes'].read_text().replace('0.0100,0.90', '0.0100,0.90,unexpected'))
    elif kind == 'wrong_count':
        params['images'] = 3
    else:
        params['max_annotation_rows'] = 1
    with pytest.raises(ValueError):
        open_images_validation(params, inputs, tmp_path / 'out', lambda: None)


def test_explicit_preservation_keeps_unlisted_native_labels_without_inventing_names(tmp_path):
    inputs = fixture(tmp_path)
    inputs['boxes'].write_text(inputs['boxes'].read_text().replace('/m/fixture', '/m/unlisted'))
    result = open_images_validation({'images': 2, 'preserve_unlisted_native_classes': True}, inputs, tmp_path / 'out', lambda: None)
    row = json.loads(result['path'].read_text().splitlines()[0])
    assert row['boxes'][0]['native']['LabelName'] == '/m/unlisted'
    assert row['native_class_descriptions']['/m/unlisted'] is None
    assert result['native_scope_counts']['unlisted_class_or_attribute_ids'] == 1
