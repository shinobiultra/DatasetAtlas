"""Original MME yes/no question pairs with category and pair identity intact."""
from pathlib import PurePosixPath
import zipfile

from .classic_vision import ClassicVisionAdapter


class MMEAdapter(ClassicVisionAdapter):
    def _rows(self):
        if hasattr(self, '_metadata_rows'):
            return self._metadata_rows
        prefix = self.config.get('archive_prefix', 'MME_Benchmark_release_version/MME_Benchmark/')
        rows = []
        consumed = 0
        with zipfile.ZipFile(self._path()) as archive:
            members = {i.filename: i for i in archive.infolist() if not i.is_dir()}
            used = set()
            categories = set()
            for name, info in sorted(members.items()):
                if not name.startswith(prefix) or not name.endswith('.txt'):
                    continue
                category = name[len(prefix):].split('/')[0]
                categories.add(category)
                consumed += info.file_size
                if consumed > self.config.get('max_annotation_bytes', 20_000_000):
                    raise ValueError('MME annotation byte budget exceeded')
                pair = PurePosixPath(name).stem
                parent = str(PurePosixPath(name).parent).replace('/questions_answers_YN', '/images')
                candidates = [f'{parent}/{pair}{ext}' for ext in ('.jpg', '.png', '.jpeg') if f'{parent}/{pair}{ext}' in members]
                if len(candidates) != 1:
                    raise ValueError('MME pair must have exactly one native image')
                image = candidates[0]
                used.add(image)
                lines = archive.read(info).decode('utf-8-sig').splitlines()
                if len(lines) != 2:
                    raise ValueError('MME native pair must contain two questions')
                for ordinal, line in enumerate(lines, 1):
                    parts = line.rsplit('\t', 1)
                    if len(parts) != 2 or parts[1] not in {'Yes', 'No', 'yes', 'no'}:
                        raise ValueError('Invalid MME question/answer line')
                    rows.append({'image_id': f'{category}:{pair}:{ordinal}', 'image': image,
                                 'category': category, 'pair_id': f'{category}:{pair}',
                                 'question': parts[0], 'answer': parts[1],
                                 'native_annotation_member': name, 'native_line_1based': ordinal})
            if used != {n for n in members if PurePosixPath(n).suffix.lower() in {'.jpg', '.png', '.jpeg'}}:
                raise ValueError('MME archive has unjoined images')
        selected = self.config.get('categories')
        if selected:
            if not set(selected) <= categories:
                raise ValueError('Requested MME category not present')
            rows = [r for r in rows if r['category'] in selected]
        if not rows:
            raise ValueError('No MME questions found')
        self._metadata_rows = rows
        return rows
