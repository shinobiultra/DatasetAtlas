"""Native nocaps image population with exact caption groups and hidden test labels."""
from .structured_collection import StructuredCollectionAdapter


class NocapsAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_nocaps_rows'):
            return self._nocaps_rows
        rows = super()._rows()
        seen = set()
        caption_ids = set()
        for row in rows:
            identity = row['id']
            if identity in seen:
                raise ValueError('Duplicate native nocaps image ID')
            seen.add(identity)
            split = row['_atlas_origin']['split']
            if split == 'validation':
                captions = row['native_captions']
                if len(captions) != 10:
                    raise ValueError('nocaps validation image requires ten native captions')
                for caption in captions:
                    if caption['image_id'] != identity or caption['id'] in caption_ids:
                        raise ValueError('Duplicate or mismatched nocaps caption')
                    if not isinstance(caption['caption'], str):
                        raise ValueError('Invalid nocaps caption text')
                    caption_ids.add(caption['id'])
                row['_atlas_caption_text'] = '\n'.join(c['caption'] for c in captions)
            elif split != 'test' or 'native_captions' in row:
                raise ValueError('nocaps test labels must remain unavailable')
        self._nocaps_rows = rows
        return rows
