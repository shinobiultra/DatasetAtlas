"""COCO-GB (Tang et al., WWW 2021): the author repository's gender-annotated COCO caption splits, one row per image record.

v1 is `COCOGBv1.zip` (`Ksplit_gender_category.json`: the Karpathy split of COCO 2014 with a four-valued `gender`, COCO `category_id` string and a
1,000-image gender-balanced `secret_test` list). v2 is `COCOv2.zip` (three JSON files that reorganise train/test). Both are joined to COCO images
by `filepath`/`filename`. Nothing is reinterpreted: `gender` stays the author's integer (the repository's benchmarking code defines a caption-word
coding of 0 woman words only, 1 man words only, 2 both or neutral only, 3 none, but does not document the JSON field itself), v1 and v2 stay separate
rows because their train/test assignments differ, v2's `fine_tune` file has no gender or category fields (they stay absent) and keeps only some
of each image's sentences while listing all their IDs (`captions_subset_of_listed`).
Every native sentence field is retained, including raw whitespace, tokens and sentence/image IDs.
"""
from __future__ import annotations
import json
import zipfile
from pathlib import Path
from . import converter, write_rows

V1_MEMBER = 'Ksplit_gender_category.json'
V2_MEMBERS = {'COCOv2_train.json': 'train', 'COCOv2_test.json': 'test', 'COCOv2_fine_tune.json': 'fine_tune'}
COCO_URL = 'https://images.cocodataset.org/{filepath}/{filename}'


def _row(variant: str, partition: str, image: dict, secret: dict | None) -> dict:
    if image['filepath'] not in {'train2014', 'val2014'}:
        raise ValueError(f'Unexpected COCO folder {image["filepath"]!r}')
    expected = f'COCO_{image["filepath"]}_{image["cocoid"]:012d}.jpg'
    if image['filename'] != expected:
        raise ValueError(f'COCO-GB filename {image["filename"]!r} does not match its COCO ID')
    sentences = image['sentences']
    captions = [s['raw'] for s in sentences]
    present = [s['sentid'] for s in sentences]
    listed = image['sentids']
    # The v2 fine_tune file keeps only some of an image's sentences while still listing every sentence ID, so present IDs may be a strict subset.
    if len(set(present)) != len(present) or not set(present) <= set(listed):
        raise ValueError(f'COCO-GB image {image["cocoid"]} has sentences that its sentence ID list does not contain')
    category = image.get('category_id')
    return {
        'source_id': f'{variant}:{partition}:{image["cocoid"]}', 'release_variant': variant, 'partition': partition, 'split': image['split'],
        'cocoid': image['cocoid'], 'imgid': image['imgid'], 'filepath': image['filepath'], 'filename': image['filename'],
        'gender': image.get('gender'), 'category_id': category, 'category_ids': [int(x) for x in category.split()] if category else None,
        'captions': captions, 'native_sentences':sentences, 'caption_ids': present, 'listed_sentence_ids': listed, 'captions_subset_of_listed': len(present) < len(listed), 'secret_test': None if secret is None else image['cocoid'] in secret,
        'display_text': captions[0] if captions else '', 'coco_url': COCO_URL.format(filepath=image['filepath'], filename=image['filename'])}


@converter('coco_gb')
def coco_gb(params, inputs, output_dir, check):
    """v1 rows (123,287) then v2 rows (train, test, fine_tune), each scoped by variant and partition because COCO IDs repeat across them."""
    member_limit=params.get('max_annotation_member_bytes',200_000_000)
    total_limit=params.get('max_annotation_expanded_bytes',350_000_000)
    if any(type(value) is not int or not 1<=value<=2_000_000_000 for value in [member_limit,total_limit]):
        raise ValueError('COCO-GB requires bounded positive annotation expansion limits')
    def rows():
        decoded=0
        def read_json(archive,name):
            nonlocal decoded
            info=archive.getinfo(name);limit=min(member_limit,total_limit-decoded)
            if not 1<=info.file_size<=limit:raise ValueError('COCO-GB native annotation exceeds its expanded byte budget')
            with archive.open(info) as stream:payload=stream.read(limit+1)
            if len(payload)!=info.file_size:raise ValueError('COCO-GB native annotation length changed')
            decoded+=len(payload)
            return json.loads(payload)
        with zipfile.ZipFile(inputs['v1_zip']) as archive:
            data = read_json(archive,V1_MEMBER)
        categories = {c['id'] for c in data['categories']}
        secret = {item['coco_id']: item for item in data['secret_test']}
        images = {image['cocoid'] for image in data['images']}
        if len(secret) != len(data['secret_test']) or not set(secret) <= images:
            raise ValueError('COCO-GB v1 secret_test must list distinct images that are present in the split')
        by_id = {image['cocoid']: image for image in data['images']}
        for item in data['secret_test']:
            image = by_id[item['coco_id']]
            if image['gender'] != item['gender'] or image['category_id'] != item['category_id']:
                raise ValueError(f'COCO-GB v1 secret_test entry {item["coco_id"]} disagrees with the split record')
        for image in data['images']:
            check()
            row = _row('v1', image['split'], image, secret)
            if row['category_ids'] and not set(row['category_ids']) <= categories:
                raise ValueError(f'COCO-GB image {image["cocoid"]} names a category outside the 80 declared')
            yield row
        del data, by_id
        with zipfile.ZipFile(inputs['v2_zip']) as archive:
            for member, partition in V2_MEMBERS.items():
                for image in read_json(archive,member)['images']:
                    check()
                    yield _row('v2', partition, image, None)
    return write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)
