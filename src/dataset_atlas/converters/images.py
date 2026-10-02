"""Conversions that turn published numeric image arrays into browsable image files and records."""
from __future__ import annotations
import collections
import numpy as np
from . import converter, write_rows


@converter('npy_images_round_robin')
def npy_images_round_robin(params, inputs, output_dir, check):
    """Pinned NPY pixel/label arrays -> one lossless PNG per image, and records in a class round-robin order.

    Arrays are read with pickle disabled. Every PNG is decoded again and must equal its source row exactly, so integrity
    does not depend on a Pillow version's PNG bytes. The original row index stays the identity, so ordering cannot rename samples."""
    import pyarrow as pa
    from PIL import Image
    images = np.load(inputs['data_npy'], allow_pickle=False)
    labels = np.load(inputs['labels_npy'], allow_pickle=False)
    expected, classes = params['count'], params['class_names']
    if images.shape != (expected, *params['image_shape']) or images.dtype != np.uint8 or labels.shape != (expected,):
        raise ValueError('Source array shape or dtype differs from the release')
    per_class = expected // len(classes)
    if collections.Counter(labels.tolist()) != {label: per_class for label in range(len(classes))}:
        raise ValueError('Source class counts differ from the release')
    media = output_dir / 'images'
    media.mkdir(parents=True, exist_ok=True)
    rows = []
    for ordinal, (pixels, label) in enumerate(zip(images, labels, strict=True)):
        check()
        filename = f'{ordinal:04d}.png'
        Image.fromarray(pixels).save(media / filename)
        with Image.open(media / filename) as saved:
            if not np.array_equal(np.asarray(saved), pixels):
                raise ValueError('PNG conversion changed source pixels')
        rows.append({'source_id': str(ordinal), 'source_index': ordinal, 'label': int(label), 'class_name': classes[label], 'image': filename,
                     'release_variant': params['release_variant'],
                     'pixel_representation': 'Lossless RGB PNG encoding of original NPY row; no resize or normalization'})
    groups = {label: [row for row in rows if row['label'] == label] for label in range(len(classes))}
    ordered = [groups[label][index] for index in range(per_class) for label in range(len(classes))]
    schema = pa.schema([('source_id', pa.string()), ('source_index', pa.int64()), ('label', pa.int64()), ('class_name', pa.string()),
                        ('image', pa.string()), ('release_variant', pa.string()), ('pixel_representation', pa.string())])
    result = write_rows(lambda: iter(ordered), output_dir / 'records.parquet', 'parquet', check, schema=schema)
    return {**result, 'media_dir': media}
