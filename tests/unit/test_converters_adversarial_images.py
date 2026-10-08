"""SAEgis converter on a small synthetic inventory: structure, clean/attacked pairing and refusal of malformed trees."""
import hashlib
import json
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS
from dataset_atlas.converters import adversarial_images  # noqa: F401  (registers the converter)

SOURCES, ATTACKS = ['A', 'B'], ['atk1', 'atk2']
SIZES = {'original': {'train': 3, 'dev': 2, 'test': 2}, 'attacked': {'dev': 2, 'test': 2}}


def inventory(drop=(), extra=()):
    files = {}
    for source in SOURCES:
        for split, size in SIZES['original'].items():
            for i in range(size):
                files[f'images/{source}/original/{split}/{i}.png'] = {'bytes': 10 + i, 'git_blob_sha1': f'{abs(hash((source, split, i))):040x}'[:40]}
        for attack in ATTACKS:
            for split, size in SIZES['attacked'].items():
                for i in range(size):
                    files[f'images/{source}/attacked/{attack}/{split}/{i}.png'] = {'bytes': 20 + i, 'git_blob_sha1': f'{abs(hash((source, attack, split, i))):040x}'[:40]}
    for name in drop:
        del files[name]
    for name in extra:
        files[name] = {'bytes': 1, 'git_blob_sha1': 'a' * 40}
    return files


def setup(tmp_path, files):
    media = tmp_path / 'registry/media'
    media.mkdir(parents=True)
    payload = json.dumps({'files': files}, separators=(',', ':')).encode()
    (media / 'inv.json').write_bytes(payload)
    params = {'inventory': 'registry/media/inv.json', 'inventory_sha256': hashlib.sha256(payload).hexdigest(), 'sources': SOURCES,
              'attacks': ATTACKS, 'split_sizes': SIZES, 'count': len(files)}
    return params, tmp_path / 'work/prepared/x/v/sources/converted'


def convert(params, out):
    return CONVERTERS['saegis_images'](params, {}, out, lambda: None)


def test_rows_state_the_structure_the_paths_carry(tmp_path):
    params, out = setup(tmp_path, inventory())
    result = convert(params, out)
    rows = [json.loads(line) for line in Path(result['path']).read_text().splitlines()]
    # per source: 7 originals + 4 attacks-in-splits x 2 attacks x ... = 3+2+2 originals and 2 attacks x (2+2) attacked
    assert result['count'] == len(rows) == 2 * (7 + 2 * 4)
    clean = [r for r in rows if r['condition'] == 'original']
    attacked = [r for r in rows if r['condition'] == 'attacked']
    assert all(r['attack'] is None and r['clean_counterpart'] is None for r in clean)
    assert not any(r['split'] == 'train' for r in attacked)
    sample = next(r for r in attacked if r['attack'] == 'atk2' and r['split'] == 'test' and r['index'] == 1 and r['image_source'] == 'B')
    assert sample['clean_counterpart'] == 'images/B/original/test/1.png' and sample['media_path'] == 'images/B/attacked/atk2/test/1.png'
    assert len({r['source_id'] for r in rows}) == len(rows)


def test_an_attacked_image_without_its_clean_counterpart_is_refused(tmp_path):
    files = inventory(drop=['images/A/original/dev/1.png'])
    params, out = setup(tmp_path, files)
    with pytest.raises(ValueError, match='does not hold'):
        convert(params, out)


def test_attacked_file_names_must_match_the_originals_exactly(tmp_path):
    files = inventory(drop=['images/A/attacked/atk1/dev/1.png'], extra=['images/A/attacked/atk1/dev/9.png'])
    params, out = setup(tmp_path, files)
    with pytest.raises(ValueError, match='file names differ'):
        convert(params, out)


def test_unknown_sources_attacks_and_paths_are_refused_not_ignored(tmp_path):
    for extra, message in ((['images/C/original/dev/0.png'], 'Unexpected SAEgis source'), (['images/A/attacked/atk3/dev/0.png'], 'Unexpected SAEgis attack'),
                           (['images/A/original/dev/0.jpg'], 'Unexpected SAEgis inventory path')):
        sub = tmp_path / message.split()[-1]
        sub.mkdir()
        params, out = setup(sub, inventory(extra=extra))
        with pytest.raises(ValueError, match=message):
            convert(params, out)


def test_a_changed_inventory_or_a_wrong_pinned_count_is_refused(tmp_path):
    params, out = setup(tmp_path, inventory())
    with pytest.raises(ValueError, match='pinned'):
        convert({**params, 'count': params['count'] + 1}, out)
    (tmp_path / 'registry/media/inv.json').write_text(json.dumps({'files': {}}))
    with pytest.raises(ValueError, match='differs from the recipe checksum'):
        convert(params, out)


def test_conversion_outside_a_workspace_cannot_find_its_inventory(tmp_path):
    params = {'inventory': 'registry/media/inv.json', 'inventory_sha256': '0' * 64, 'sources': SOURCES, 'attacks': ATTACKS,
              'split_sizes': SIZES, 'count': 1}
    with pytest.raises(ValueError, match='Cannot locate the workspace'):
        convert(params, tmp_path / 'elsewhere')
