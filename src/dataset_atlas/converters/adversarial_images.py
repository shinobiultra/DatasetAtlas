"""SAEgis: the author repository's committed clean and adversarially attacked images, one row per image file.

The repository ships no annotation table, only PNGs whose paths carry the structure: `images/<source>/original/<split>/<n>.png` and
`images/<source>/attacked/<attack>/<split>/<n>.png`. This converter reads the checksum-pinned inventory of those files (Git blob SHA-1
and byte length, written once from the repository tree at the pinned commit) and states the structure as fields. It never opens an
image: the clean counterpart of an attacked image is the original with the same file name in the same split, a pairing the recipe's
verification receipt checks by pixel similarity on a sample. A missing or extra file, a split of the wrong size, or an attacked image
without a clean counterpart stops the conversion.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from . import converter, write_rows

PATH = re.compile(r'images/(?P<source>[^/]+)/(?:original/(?P<osplit>train|dev|test)|attacked/(?P<attack>[^/]+)/(?P<asplit>dev|test))/(?P<index>\d+)\.png')


def workspace_root(output_dir: Path) -> Path:
    """The workspace holding `registry/media`, found from where the worker places conversion output (`<root>/work/prepared/...`)."""
    for parent in Path(output_dir).resolve().parents:
        if (parent / 'registry/media').is_dir():
            return parent
    raise ValueError('Cannot locate the workspace registry from the conversion output directory')


@converter('saegis_images')
def saegis_images(params, inputs, output_dir, check):
    """One row per image: source dataset, split, condition (original or attacked), attack method and the clean counterpart's path.

    Adds `media_path` (the inventory key, relative to the repository root at the pinned commit), `source_id` and a display `label`."""
    path = workspace_root(output_dir) / params['inventory']
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != params['inventory_sha256']:
        raise ValueError('The pinned SAEgis inventory differs from the recipe checksum')
    inventory = json.loads(payload)['files']
    sources, attacks = params['sources'], params['attacks']
    expected = params['split_sizes']
    entries: dict[tuple, dict] = {}
    for name, info in inventory.items():
        match = PATH.fullmatch(name)
        if not match:
            raise ValueError(f'Unexpected SAEgis inventory path: {name}')
        if match['source'] not in sources:
            raise ValueError(f'Unexpected SAEgis source dataset: {match["source"]}')
        if match['attack'] and match['attack'] not in attacks:
            raise ValueError(f'Unexpected SAEgis attack method: {match["attack"]}')
        key = (match['source'], 'attacked' if match['attack'] else 'original', match['attack'] or '', match['asplit'] or match['osplit'], int(match['index']))
        if key in entries:
            raise ValueError(f'SAEgis inventory repeats {key}')
        entries[key] = {'name': name, **info}
    groups: dict[tuple, set] = {}
    for source, condition, attack, split, index in entries:
        groups.setdefault((source, condition, attack, split), set()).add(index)
    for source in sources:
        for split, size in expected['original'].items():
            if len(groups.get((source, 'original', '', split), ())) != size:
                raise ValueError(f'SAEgis {source} original/{split} does not hold {size} images')
        for attack in attacks:
            for split, size in expected['attacked'].items():
                indices = groups.get((source, 'attacked', attack, split), set())
                if len(indices) != size:
                    raise ValueError(f'SAEgis {source} attacked/{attack}/{split} does not hold {size} images')
                if indices != groups[(source, 'original', '', split)]:
                    raise ValueError(f'SAEgis {source} attacked/{attack}/{split} file names differ from the clean originals')
    if len(entries) != params['count']:
        raise ValueError(f'SAEgis inventory holds {len(entries)} images, not the pinned {params["count"]}')

    def rows():
        for source in sources:
            for split in ('train', 'dev', 'test'):
                originals = sorted(i for (s, c, _, p, i) in entries if s == source and c == 'original' and p == split)
                for index in originals:
                    check()
                    yield row(source, 'original', '', split, index)
                for attack in attacks:
                    for index in originals if split != 'train' else ():
                        yield row(source, 'attacked', attack, split, index)

    def row(source, condition, attack, split, index):
        entry = entries[(source, condition, attack, split, index)]
        clean = entries[(source, 'original', '', split, index)]['name'] if condition == 'attacked' else None
        label = f'{source} · {split} #{index} · ' + (f'attacked by {attack}' if attack else 'clean original')
        return {'source_id': f'{source}/{condition}/{attack or "none"}/{split}/{index}', 'image_source': source, 'condition': condition,
                'attack': attack or None, 'split': split, 'index': index, 'clean_counterpart': clean, 'media_path': entry['name'],
                'git_blob_sha1': entry['git_blob_sha1'], 'image_bytes': entry['bytes'], 'label': label}
    return write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)
