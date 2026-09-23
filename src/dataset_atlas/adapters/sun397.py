"""SUN397 native taxonomy and both published ten-fold partition protocols."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import zipfile

from .classic_vision import ClassicVisionAdapter
from .core import _safe_relative


class SUN397Adapter(ClassicVisionAdapter):
    def _rows(self):
        if hasattr(self, '_metadata_rows'):
            return self._metadata_rows
        import numpy as np
        from scipy.io import loadmat

        partitions = Path(self.config['partitions_path'])
        expected = next((f['sha256'] for f in self.config.get('source_files', [])
                         if Path(f['path']) == partitions), None)
        if expected:
            with partitions.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('SUN397 partition checksum changed')
        maximum = self.config.get('max_annotation_bytes', 150_000_000)
        consumed = 0
        with zipfile.ZipFile(self._path()) as images, zipfile.ZipFile(partitions) as annotations:
            def payload(archive, name):
                nonlocal consumed
                info = archive.getinfo(name)
                consumed += info.file_size
                if consumed > maximum:
                    raise ValueError('SUN397 annotations exceed byte budget')
                return archive.read(info)

            def lines(archive, name):
                return [line for line in payload(archive, name).decode('utf-8-sig').splitlines() if line]

            classes = lines(annotations, 'ClassName.txt')
            if len(set(classes)) != len(classes) or any(not c.startswith('/') for c in classes):
                raise ValueError('Invalid SUN397 class inventory')
            if classes != lines(images, 'SUN397/ClassName.txt'):
                raise ValueError('SUN397 image and partition taxonomies differ')
            names = {i.filename for i in images.infolist() if not i.is_dir() and i.filename.endswith('.jpg')}
            rows = {}
            for name in sorted(names):
                if len(rows) % 256 == 0 and getattr(self, 'cancel', None):
                    self.cancel()
                _safe_relative(name)
                if not name.startswith('SUN397/'):
                    raise ValueError('SUN397 image is outside native root')
                native = name[len('SUN397'):]
                category = native.rsplit('/', 1)[0]
                if category not in classes:
                    raise ValueError('SUN397 image has an unknown class')
                rows[native] = {'image_id': native, 'image': name, 'class_name': category,
                                'class_index': classes.index(category), 'text_training_folds': [],
                                'text_testing_folds': [], 'matlab_training_folds': [],
                                'matlab_testing_folds': [],
                                'partition_note': 'Text Testing_NN is the evaluation subset; MATLAB Testing is the non-training complement. Fold numbers are one-based.'}
            native_mat = loadmat(io.BytesIO(payload(annotations, 'split10.mat')), simplify_cells=True)['split']
            # Native data has ten object arrays of 397 structs. Explicit fixture
            # dimensions permit small tests without pretending they are real coverage.
            folds = self.config.get('fold_count', 10)
            class_count = self.config.get('class_count', 397)
            if len(classes) != class_count or len(native_mat) != folds:
                raise ValueError('SUN397 partition dimensions differ from release')
            for fold, class_tables in enumerate(native_mat, 1):
                if getattr(self, 'cancel', None):
                    self.cancel()
                text = {}
                for kind, field in [('Training', 'text_training_folds'), ('Testing', 'text_testing_folds')]:
                    values = lines(annotations, f'{kind}_{fold:02}.txt')
                    if len(values) != len(set(values)) or not set(values) <= rows.keys():
                        raise ValueError('SUN397 text partition has duplicate or missing images')
                    text[kind] = set(values)
                    for value in values:
                        rows[value][field].append(fold)
                if text['Training'] & text['Testing']:
                    raise ValueError('SUN397 text train/test partition overlaps')
                mat = {'Training': set(), 'Testing': set()}
                seen_classes = []
                for table in np.atleast_1d(class_tables):
                    category = table.ClassName
                    if category in seen_classes or category not in classes:
                        raise ValueError('SUN397 MATLAB class inventory differs')
                    seen_classes.append(category)
                    for kind, field in [('Training', 'matlab_training_folds'), ('Testing', 'matlab_testing_folds')]:
                        for filename in np.atleast_1d(getattr(table, kind)):
                            value = category + '/' + str(filename)
                            if value not in rows or value in mat[kind]:
                                raise ValueError('SUN397 MATLAB partition has duplicate or missing images')
                            mat[kind].add(value)
                            rows[value][field].append(fold)
                if seen_classes != classes:
                    raise ValueError('SUN397 MATLAB class order differs')
                if mat['Training'] != text['Training'] or not text['Testing'] <= mat['Testing']:
                    raise ValueError('SUN397 text and MATLAB partitions disagree')
                if mat['Training'] & mat['Testing'] or mat['Training'] | mat['Testing'] != rows.keys():
                    raise ValueError('SUN397 MATLAB partitions do not cover the image population')
        self._metadata_rows = list(rows.values())
        return self._metadata_rows
