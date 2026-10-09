"""OASIS converter on a synthetic archive: every row links its archive image, and a broken join stops the conversion."""
import io
import json
import zipfile
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS
from dataset_atlas.converters import collections  # noqa: F401  (registers the converter)

HEADER = ',Theme,Category,Source,Valence_mean\n'


def archive(tmp_path, themes, images=None):
    images = themes if images is None else images
    rows = ''.join(f'I{n},{theme},Scene,Synthetic,3.5\n' for n, theme in enumerate(themes, 1))
    gender = ''.join(f'I{n},1.0\n' for n, _ in enumerate(themes, 1))
    path = tmp_path / 'oasis.zip'
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('OASIS.csv', HEADER + rows)
        zf.writestr('OASIS_bygender_CORRECTED_092617.csv', ',Valence_mean_f\n' + gender)
        for name in images:
            zf.writestr(f'images/{name}.jpg', b'not-a-real-jpeg')
    return path


def run(tmp_path, zip_path):
    result = CONVERTERS['oasis_normative']({}, {'media_archive': zip_path}, tmp_path / 'out', lambda: None)
    return result, [json.loads(line) for line in Path(result['path']).read_text().splitlines()]


def test_every_row_links_its_archive_image_and_the_mapping_exposes_it_as_media(tmp_path):
    themes = [f'Theme {n}' for n in range(900)]
    result, rows = run(tmp_path, archive(tmp_path, themes))
    assert result['count'] == 900 and rows[0]['media_ref'] == 'images/Theme 0.jpg'
    # Regression: the mapping once named id, text and label only, so the preview carried 100 records and no images.
    assert result['adapter_config']['mapping']['media'] == 'media_ref'
    assert result['adapter_config']['mapping']['id'] == 'source_id'


def test_trailing_whitespace_in_a_theme_is_joined_and_flagged_not_rewritten(tmp_path):
    themes = [f'Theme {n}' for n in range(899)] + ['Padded ']
    _, rows = run(tmp_path, archive(tmp_path, themes, images=[f'Theme {n}' for n in range(899)] + ['Padded']))
    assert rows[-1]['theme'] == 'Padded ' and rows[-1]['media_ref'] == 'images/Padded.jpg' and rows[-1]['join_trailing_whitespace_removed']
    assert not rows[0]['join_trailing_whitespace_removed']


def test_an_archive_without_its_nine_hundred_images_is_refused(tmp_path):
    with pytest.raises(ValueError, match='900 original JPEGs'):
        run(tmp_path, archive(tmp_path, ['a', 'b']))
