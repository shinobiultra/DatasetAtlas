"""Author-defined What's-Up transformations for the Pathways datasets.

Caption parsing functions follow israfelsr/vlm-pathways (MIT), data/build_whatsup.py
at 470944b3f6b44901a9055cf8d91aef18cee21671. Original annotations and media
remain intact; RGB re-encoding from the upstream HF export is not repeated.

MIT License

Copyright (c) 2026 Israfel Salazar

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from pathlib import Path
import re
from .structured_collection import StructuredCollectionAdapter

def extract_preposition(caption):
    """Extract preposition from a caption (coco_one / vg_qa_one legacy path)."""
    caption_lower = caption.lower()
    patterns = [
        r"on the (top|bottom|left|right)",
        r"to the (left|right|front|behind) of",
        r"\s(on|under|above|below|behind|left|right|front)\s",
    ]
    for pattern in patterns:
        match = re.search(pattern, caption_lower)
        if match:
            return match.group(1)
    return "unknown"

def extract_objects(caption):
    """Extract [obj1, obj2] from a caption (coco_one / vg_qa_one legacy path)."""
    caption = re.sub(r"^A photo of ", "", caption, flags=re.IGNORECASE)
    prep_patterns = [
        r" to the (?:left|right|front|behind) of ",
        r" on the (?:top|bottom|left|right) ",
        r" (?:on|under|above|below|behind) ",
    ]
    for pattern in prep_patterns:
        parts = re.split(pattern, caption, flags=re.IGNORECASE)
        if len(parts) == 2:
            obj1 = re.sub(r"^(a|an|the)\s+", "", parts[0].strip(), flags=re.IGNORECASE)
            obj2 = re.sub(r"^(a|an|the)\s+", "", parts[1].strip(), flags=re.IGNORECASE)
            return [obj1, obj2]
    words = caption.split()
    if len(words) >= 2:
        obj1 = re.sub(r"^(a|an|the)$", "", words[0], flags=re.IGNORECASE)
        obj2 = re.sub(r"^(a|an|the)$", "", words[-1], flags=re.IGNORECASE)
        return [obj1 or "unknown", obj2 or "unknown"]
    return [caption, "unknown"]

def extract_from_filename_controlled(image_path):
    """Parse controlled filenames: {object1}_{preposition}_{object2}.jpeg."""
    stem = Path(image_path).stem
    parts = stem.split("_")
    obj1 = parts[0].replace("-", " ")
    obj2 = parts[-1].replace("-", " ")
    prep_raw = "_".join(parts[1:-1])
    prep_map = {
        "right_of": "right", "left_of": "left", "in-front_of": "front",
        "behind": "behind", "on": "on", "under": "under",
    }
    return obj1, prep_map.get(prep_raw, prep_raw), obj2

def extract_from_caption_photo(caption):
    """Parse 'A photo of a {obj1} {preposition} a {obj2}' (coco_two / vg_qa_two)."""
    pattern = (r"^A photo of an? (.+?) "
               r"(to the left of|to the right of|to the front of|to the behind of|above|below) "
               r"an? (.+)$")
    match = re.match(pattern, caption, re.IGNORECASE)
    if match:
        prep_map = {
            "to the left of": "left", "to the right of": "right",
            "to the front of": "front", "to the behind of": "behind",
            "above": "above", "below": "below",
        }
        return match.group(1).strip(), prep_map.get(match.group(2).strip().lower(), match.group(2)), match.group(3).strip()
    return "unknown", "unknown", "unknown"

class PathwaysAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_pathways_rows'):
            return self._pathways_rows
        split = self.config['pathways_split']
        allowed = {'controlled_images', 'controlled_clevr', 'coco_one', 'coco_two', 'vg_qa_one', 'vg_qa_two'}
        if split not in allowed:
            raise ValueError('Unknown Pathways source transformation')
        rows = []
        for native in super()._rows():
            if '_atlas_pathways' in native:
                raise ValueError('Source collides with Pathways derived fields')
            options = native['_atlas_choices']
            if not options:
                raise ValueError('Pathways source requires caption options')
            if split.startswith('controlled_'):
                obj1, prep, obj2 = extract_from_filename_controlled(native['image_path'])
                objects = [obj1, obj2]
            elif split in {'coco_two', 'vg_qa_two'}:
                obj1, prep, obj2 = extract_from_caption_photo(options[0])
                objects = [obj1, obj2]
            else:
                prep, objects = extract_preposition(options[0]), extract_objects(options[0])
            # The author drops only VG two-object captions with unknown parsing.
            if split == 'vg_qa_two' and prep == 'unknown':
                continue
            rows.append({**native, '_atlas_pathways': {
                'caption_correct': options[0], 'caption_incorrect': options[1:],
                'preposition': prep, 'objects': objects,
                'transform_revision': '470944b3f6b44901a9055cf8d91aef18cee21671',
                'media_representation': 'original source bytes; upstream RGB export not repeated'}})
        self._pathways_rows = rows
        return rows
