"""Pinned Open Images validation tables joined without dropping native fields."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from . import converter, file_sha256, write_rows

ANNOTATIONS = ('human_labels', 'boxes', 'relationships', 'segmentations')


@converter('open_images_validation')
def open_images_validation(params, inputs, output_dir, check):
    """One record per released image, including every row of each declared table.

    Source strings, negative labels, annotation order and empty cells remain
    unchanged. Annotation subsets are never treated as the image population.
    Masks and localized narratives are separate media populations.
    """
    if set(inputs) != {'images', 'class_names', *ANNOTATIONS}:
        raise ValueError('Open Images requires the six declared native tables')
    expected = params.get('images', 41_620)
    max_rows = params.get('max_annotation_rows', 2_000_000)
    if type(expected) is not int or not 1 <= expected <= 200_000:
        raise ValueError('Open Images image population exceeds its bound')
    if type(max_rows) is not int or not 1 <= max_rows <= 5_000_000:
        raise ValueError('Open Images annotation population exceeds its bound')
    images: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    with Path(inputs['images']).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Open Images image metadata headers are invalid')
        for ordinal, row in enumerate(reader):
            check()
            image_id = row.get('ImageID', '')
            if not re.fullmatch(r'[a-f0-9]{16}', image_id) or image_id in by_id:
                raise ValueError('Open Images image identity is invalid or duplicate')
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Open Images image metadata row shape changed')
            if len(images) >= expected:
                raise ValueError('Open Images image population differs from pinned count')
            result: dict[str, Any] = {'source_id': image_id, 'source_image_row': ordinal,
                      'split': 'validation', 'native_image_metadata': row,
                      'media_ref': 'validation/' + image_id + '.jpg',
                      **{key: [] for key in ANNOTATIONS}}
            images.append(result)
            by_id[image_id] = result
    if len(images) != expected:
        raise ValueError('Open Images image population differs from pinned count')
    classes = {}
    with Path(inputs['class_names']).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.reader(stream):
            check()
            if len(row) != 2 or not row[0] or row[0] in classes:
                raise ValueError('Open Images class description join is invalid')
            classes[row[0]] = row[1]
            if len(classes) > 100_000:
                raise ValueError('Open Images class table exceeds its bound')
    counts = {}
    unlisted = set()
    for key in ANNOTATIONS:
        count = 0
        with Path(inputs[key]).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError('Open Images annotation headers are invalid')
            for ordinal, row in enumerate(reader):
                check()
                image_id = row.get('ImageID', '')
                if image_id not in by_id:
                    raise ValueError('Open Images annotation has no native image join')
                if None in row or any(value is None for value in row.values()):
                    raise ValueError('Open Images annotation row shape changed')
                unknown = {row[name] for name in ('LabelName', 'LabelName1', 'LabelName2') if name in row and row[name] not in classes}
                if unknown and not params.get('preserve_unlisted_native_classes', False):
                    raise ValueError('Open Images annotation has no native class join')
                unlisted.update(unknown)
                count += 1
                if count > max_rows:
                    raise ValueError('Open Images annotation table exceeds its bound')
                by_id[image_id][key].append({'source_annotation_row': ordinal, 'native': row})
        counts[key] = count
    source_hashes = {key: file_sha256(Path(path)) for key, path in inputs.items()}

    def rows():
        for image in images:
            ids = dict.fromkeys(row['native'][name]
                                for key in ANNOTATIONS for row in image[key]
                                for name in ('LabelName', 'LabelName1', 'LabelName2') if name in row['native'])
            yield {**image, 'native_class_descriptions': {label: classes.get(label) for label in ids},
                   'class_description_availability': 'Some native label or attribute IDs lack a name in the declared V7 class table' if any(label not in classes for label in ids) else 'All referenced label IDs joined',
                   'native_table_sha256': source_hashes,
                   'positive_image_labels': [row['native']['LabelName'] for row in image['human_labels']
                                             if row['native'].get('Confidence') == '1'],
                   'negative_image_labels': [row['native']['LabelName'] for row in image['human_labels']
                                             if row['native'].get('Confidence') == '0']}
    result = write_rows(rows, Path(output_dir) / 'images.jsonl', 'jsonl', check)
    result['adapter_config'] = {'mapping': {'id': 'source_id', 'media': 'media_ref'},
                                'fields': {'positive_image_labels': {'dtype': 'array', 'description': 'Native image labels with Confidence exactly 1.'},
                                           'negative_image_labels': {'dtype': 'array', 'description': 'Native image labels with Confidence exactly 0; absence is not a negative label.'}}}
    result['native_scope_counts'] = {'images': len(images), 'class_descriptions': len(classes), 'unlisted_class_or_attribute_ids': len(unlisted), **counts}
    return result
