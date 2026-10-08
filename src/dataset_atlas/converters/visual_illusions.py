"""IllusionBench (Zhang et al.): the authors' `Image_properties.json` flattened into one row per annotated image.

Each source entry is `{image_property: {image_name, Difficult Level, Category, Description}, qa_data: [{Question, Question Type, Correct Answer}]}`.
Every source field is kept; the converter only adds `image_name` and the archive member name `media_member` (`IllusionDataset/<image_name>`) so the
adapter can address the image inside the authors' ZIP, and keeps the nested `image_property` and `qa_data` exactly as released. It never opens the
archive: which annotated images the archive lacks, and which archived images have no annotation, is decided by the adapter's directory check against
the recipe's declared absences, so a join failure cannot be dropped silently here.
"""
from __future__ import annotations
import json
from pathlib import Path
from . import converter, write_rows

QUESTION_TYPES = {'TF', 'select'}


@converter('illusionbench_properties')
def illusionbench_properties(params, inputs, output_dir, check):
    entries = json.loads(Path(inputs['properties']).read_text())
    if not isinstance(entries, list):
        raise ValueError('IllusionBench properties must be a list of entries')

    def rows():
        seen = set()
        for entry in entries:
            check()
            if set(entry) != {'image_property', 'qa_data'}:
                raise ValueError(f'Unexpected IllusionBench entry keys: {sorted(entry)}')
            properties, qa = entry['image_property'], entry['qa_data']
            name = properties['image_name']
            if not isinstance(name, str) or '/' in name or not name.endswith('.png'):
                raise ValueError(f'Unexpected IllusionBench image name: {name!r}')
            if name in seen:
                raise ValueError(f'IllusionBench repeats image {name}')
            seen.add(name)
            bad = [q for q in qa if q.get('Question Type') not in QUESTION_TYPES]
            if bad:
                raise ValueError(f'IllusionBench image {name} has an unknown question type: {bad[0].get("Question Type")!r}')
            yield {'image_name': name, 'media_member': f'{params.get("archive_root", "IllusionDataset")}/{name}',
                   'question_count': len(qa), 'image_property': properties, 'qa_data': qa}
    return write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)
