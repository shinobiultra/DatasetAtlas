"""IllusionBench converter on synthetic entries: nested source fields stay intact and malformed entries are refused."""
import json
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS
from dataset_atlas.converters import visual_illusions  # noqa: F401  (registers the converter)


def entry(name, questions=None, **extra):
    return {'image_property': {'image_name': name, 'Difficult Level': 1, 'Category': 'B', 'Description': 'A synthetic description.'},
            'qa_data': questions if questions is not None else [{'Question': 'Is it red?', 'Question Type': 'TF', 'Correct Answer': 'True'},
                                                               {'Question': 'Pick one. i. a ii. b', 'Question Type': 'select', 'Correct Answer': 'i. a'}], **extra}


def run(entries, tmp_path, **params):
    path = tmp_path / 'props.json'
    path.write_text(json.dumps(entries))
    result = CONVERTERS['illusionbench_properties'](params, {'properties': path}, tmp_path / 'out', lambda: None)
    return result, [json.loads(line) for line in Path(result['path']).read_text().splitlines()]


def test_nested_source_fields_are_kept_and_the_archive_member_is_added(tmp_path):
    result, rows = run([entry('10011001.png'), entry('7.png', questions=[])], tmp_path)
    assert result['count'] == 2 and rows[0]['media_member'] == 'IllusionDataset/10011001.png' and rows[0]['question_count'] == 2
    assert rows[0]['image_property']['Difficult Level'] == 1 and rows[0]['qa_data'][1]['Question Type'] == 'select'
    assert rows[1]['question_count'] == 0 and rows[1]['qa_data'] == []  # an entry without questions stays a record


def test_repeated_images_unknown_keys_and_unknown_question_types_are_refused(tmp_path):
    with pytest.raises(ValueError, match='repeats image'):
        run([entry('a.png'), entry('a.png')], tmp_path)
    sub = tmp_path / 'k'
    sub.mkdir()
    with pytest.raises(ValueError, match='Unexpected IllusionBench entry keys'):
        run([entry('a.png', surprise=1)], sub)
    sub2 = tmp_path / 'q'
    sub2.mkdir()
    with pytest.raises(ValueError, match='unknown question type'):
        run([entry('a.png', questions=[{'Question': 'x', 'Question Type': 'essay', 'Correct Answer': 'y'}])], sub2)
    sub3 = tmp_path / 'n'
    sub3.mkdir()
    with pytest.raises(ValueError, match='Unexpected IllusionBench image name'):
        run([entry('../a.png')], sub3)
