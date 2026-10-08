"""Conversions of pinned original multimodal benchmarks into the records (and extracted media) an adapter reads.

Each converter reproduces, exactly, the table the catalogue's maintained copy was built from; the recipe pins its row digest.
Original fields and values are preserved, and only identity/media-reference fields are added. Where media are extracted from an
archive they are written byte for byte (never re-encoded) under `<output>/media/images/` and returned as `media_dir`, so the
recipe can pin them with `media_sha256` and the worker can point the adapter's `media_root` at them.
"""
from __future__ import annotations
import csv
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from . import RowDigest, converter, file_sha256, write_rows

MAX_IMAGE_BYTES = 10_000_000
IMAGE_MAGIC = ((b'\x89PNG\r\n\x1a\n', '.png'), (b'\xff\xd8\xff', '.jpg'))


@converter('golan_presented_stimuli')
def golan_presented_stimuli(params, inputs, output_dir, check):
    """Retain only the PNGs presented to participants, in the maintained alternating experiment order."""
    import tarfile
    from itertools import zip_longest
    from dataset_atlas.adapters.core import _safe_relative
    media_dir=Path(output_dir)/'media'
    groups={1:[],2:[]}; seen=set()
    with tarfile.open(inputs['source_archive'],'r|gz') as archive:
        for member in archive:
            check()
            relative=member.name.partition('/')[2]
            if not relative.endswith('.png') or '/stimuli_presented_in_behavioral_experiment/' not in relative:continue
            _safe_relative(relative)
            if not member.isfile() or relative in seen:raise ValueError('Presented stimulus must be a unique regular file')
            experiment=1 if relative.startswith('experiment_1_results/') else 2 if relative.startswith('experiment_2_results/') else None
            if experiment is None:raise ValueError('Unknown presented experiment')
            stream=archive.extractfile(member)
            if stream is None or member.size>MAX_IMAGE_BYTES:raise ValueError('Presented stimulus exceeds image bound')
            data=checked_image(stream.read(MAX_IMAGE_BYTES+1));stream.close()
            if image_extension(data)!='.png':raise ValueError('Presented stimulus is not PNG')
            store_image(media_dir,relative,data);seen.add(relative)
            name=Path(relative).name
            groups[experiment].append({'path':relative,'experiment':'MNIST' if experiment==1 else 'CIFAR-10',
                'replication':next((p.removeprefix('replication_') for p in Path(relative).parts if p.startswith('replication_')),''),
                'stimulus_kind':'natural_control' if name.startswith(('MNIST_','CIFAR_10_test_')) else 'synthesized_controversial',
                'source_bytes':str(len(data)),'source_sha256':hashlib.sha256(data).hexdigest()})
    if [len(groups[1]),len(groups[2])]!=params.get('counts',[820,1043]):raise ValueError('Presented experiment counts differ')
    def rows():
        for pair in zip_longest(*[sorted(groups[i],key=lambda row:row['path']) for i in (1,2)]):
            yield from (row for row in pair if row is not None)
    return {**write_rows(rows,Path(output_dir)/'records.csv','csv',check),'media_dir':media_dir}


def image_extension(data: bytes) -> str:
    """The file extension for a PNG/JPEG/WebP payload, judged from its signature; anything else is refused."""
    for magic, extension in IMAGE_MAGIC:
        if data.startswith(magic):
            return extension
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    raise ValueError('Unsupported source image encoding (expected PNG, JPEG or WebP)')


def checked_image(data: bytes) -> bytes:
    if not 1 <= len(data) <= MAX_IMAGE_BYTES:
        raise ValueError('Source image is empty or exceeds the 10 MB per-image bound')
    return data


def store_image(media_dir: Path, relative: str, data: bytes) -> None:
    """Write original bytes at `relative` under `media_dir`, refusing to overwrite different content already there."""
    target = Path(media_dir) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(data).digest():
            raise ValueError(f'Extracted media collision: {relative}')
        return
    target.write_bytes(data)


def safe_name(name: str) -> str:
    if not name or PurePosixPath(name).name != name or name in {'.', '..'}:
        raise ValueError(f'Unsafe media file name: {name!r}')
    return name


# ---- WHOOPS! ---------------------------------------------------------------------------------------------------

WHOOPS_JSON_COLUMNS = ('crowd_captions', 'crowd_explanations', 'crowd_underspecified_captions', 'question_answering_pairs')


@converter('whoops')
def whoops(params, inputs, output_dir, check):
    """WHOOPS!'s CSV joined to its image ZIP by `image_id`: list columns parsed from JSON, each image stored under its content hash.

    Adds `source_image_name`, `media_path` (images/<sha256>.<ext>) and `image_sha256`; the media are the archive's exact bytes."""
    media_dir = Path(output_dir) / 'media'

    def rows():
        with zipfile.ZipFile(inputs['source_zip']) as archive, Path(inputs['source_csv']).open(encoding='utf-8-sig', newline='') as handle:
            files = {Path(info.filename).name: info for info in archive.infolist()
                     if not info.is_dir() and info.filename.startswith('whoops_images/') and info.filename.endswith('.png')}
            if len(files) != params.get('images', 500):
                raise ValueError('WHOOPS! archive does not contain the expected number of source images')
            for row in csv.DictReader(handle):
                name = row['image_id'] + '.png'
                if name not in files:
                    raise ValueError(f'WHOOPS! image absent from the archive: {name}')
                for key in WHOOPS_JSON_COLUMNS:
                    row[key] = json.loads(row[key])
                data = checked_image(archive.read(files[name]))
                digest = hashlib.sha256(data).hexdigest()
                relative = f'images/{digest}{image_extension(data)}'
                store_image(media_dir, relative, data)
                row.update(source_image_name=name, media_path=relative, image_sha256=digest)
                yield row
    result = write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)
    return {**result, 'media_dir': media_dir}


# ---- LLaVA-Bench (In-the-Wild) -----------------------------------------------------------------------------------

def jsonl_objects(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


@converter('llava_bench')
def llava_bench(params, inputs, output_dir, check):
    """LLaVA-Bench In-the-Wild: each question joined to its image's context caption; the original image files are copied unchanged.

    Inputs are `questions`, `context` and one `image_<stem>` per image (e.g. image_001 for 001.jpg)."""
    media_dir = Path(output_dir) / 'media'
    questions, context = jsonl_objects(inputs['questions']), jsonl_objects(inputs['context'])
    captions = {row['image']: row for row in context}
    if len(questions) != params.get('questions', 60) or len(captions) != params.get('images', 24):
        raise ValueError('LLaVA-Bench question or image population differs from the pinned release')

    def rows():
        used = set()
        for row in questions:
            name = safe_name(row['image'])
            if name not in captions:
                raise ValueError('LLaVA-Bench question has no context caption')
            source = Path(inputs['image_' + Path(name).stem])
            data = checked_image(source.read_bytes())
            relative = f'images/{name}'
            store_image(media_dir, relative, data)
            used.add(name)
            yield {'question_id': row['question_id'], 'question': row['text'], 'category': row['category'], 'source_image_name': name,
                   'context_caption': captions[name]['caption'], 'context_id': captions[name]['id'],
                   'image_sha256': hashlib.sha256(data).hexdigest(), 'media_path': relative}
        if len(used) != len(captions):
            raise ValueError('LLaVA-Bench question images are incomplete')
    result = write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)
    return {**result, 'media_dir': media_dir}


# ---- MM-Vet (v1) -----------------------------------------------------------------------------------------------

@converter('mm_vet')
def mm_vet(params, inputs, output_dir, check):
    """MM-Vet v1's release ZIP: one row per annotation (in file order) with the image's exact bytes extracted beside it.

    Adds `source_id` (the annotation key), `bard_set` (membership of bard_set.json), `image_sha256` and `media_path`."""
    media_dir = Path(output_dir) / 'media'

    def rows():
        with zipfile.ZipFile(inputs['source_zip']) as archive:
            annotations = json.loads(archive.read('mm-vet/mm-vet.json'))
            bard_set = set(json.loads(archive.read('mm-vet/bard_set.json')))
            if len(annotations) != params.get('annotations', 218) or len(bard_set) != params.get('bard_set', 168):
                raise ValueError('MM-Vet v1 annotation population differs from the pinned release')
            available = {info.filename: info for info in archive.infolist() if info.filename.startswith('mm-vet/images/') and not info.is_dir()}
            if len(available) != params.get('images', 200):
                raise ValueError('MM-Vet v1 image population differs from the pinned release')
            used = set()
            for source_id, item in annotations.items():
                name = safe_name(item['imagename'])
                if f'mm-vet/images/{name}' not in available:
                    raise ValueError('MM-Vet annotation image is missing from the archive')
                data = checked_image(archive.read(available[f'mm-vet/images/{name}']))
                relative = f'images/{name}'
                store_image(media_dir, relative, data)
                used.add(name)
                yield {'source_id': source_id, 'source_image_name': name, 'question': item['question'], 'answer': item['answer'],
                       'capability': item['capability'], 'imagesource': item['imagesource'], 'bard_set': source_id in bard_set,
                       'image_sha256': hashlib.sha256(data).hexdigest(), 'media_path': relative}
            if len(used) != len(available):
                raise ValueError('MM-Vet source images are not all referenced')
    result = write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)
    return {**result, 'media_dir': media_dir}


# ---- IllusionVQA (embedded images) -----------------------------------------------------------------------------

class BytesRowDigest(RowDigest):
    """RowDigest for rows that carry raw bytes (embedded images): each bytes value is hashed in place as {"bytes_sha256": ...}."""
    def add(self, row: dict) -> None:
        def marker(value):
            if isinstance(value, bytes):
                return {'bytes_sha256': hashlib.sha256(value).hexdigest()}
            raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')
        self._hash.update(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=marker).encode() + b'\n')
        self.count += 1


def digest_existing_with_bytes(path: Path) -> dict:
    """The row digest (bytes hashed in place) of an already-converted Parquet table that embeds image bytes, to pin or compare."""
    import pyarrow.parquet as pq
    digest = BytesRowDigest()
    for batch in pq.ParquetFile(path).iter_batches(batch_size=64):
        for row in batch.to_pylist():
            digest.add(row)
    return {'count': digest.count, 'rows_sha256': digest.hexdigest()}


ILLUSION_TASKS = (('comprehension', 'comprehension', 435), ('soft-localization', 'soft_localization', 1000))
ILLUSION_SOURCE_FILE = 'data/test-00000-of-00001.parquet'


@converter('illusionvqa')
def illusionvqa(params, inputs, output_dir, check):
    """IllusionVQA's two author test Parquets (comprehension, then soft-localization) as one table with each image embedded unchanged.

    Adds `source_id` (task:test:id), `task`, `split` and `source_file`; every original field and the image bytes are kept. The
    expected per-task counts (435 and 1,000) may be overridden by `params.counts`. Rows carry bytes, so the pinned digest hashes those in place (BytesRowDigest, `digest_existing_with_bytes`)."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    image_type = pa.struct([pa.field('bytes', pa.binary()), pa.field('path', pa.string())])
    schema = pa.schema([('source_id', pa.string()), ('task', pa.string()), ('split', pa.string()), ('source_file', pa.string()),
                        ('id', pa.int64()), ('question', pa.string()), ('options', pa.list_(pa.string())), ('answer', pa.string()),
                        ('category', pa.string()), ('source', pa.string()), ('url', pa.string()), ('reasoning', pa.string()),
                        ('images', pa.list_(image_type))])
    output = Path(output_dir) / 'records.parquet'
    output.parent.mkdir(parents=True, exist_ok=True)
    digest, seen = BytesRowDigest(), set()
    with pq.ParquetWriter(output, schema, compression='zstd', compression_level=5) as writer:
        for task, key, default in ILLUSION_TASKS:
            expected = params.get('counts', {}).get(task, default)
            count = 0
            for batch in pq.ParquetFile(inputs[key]).iter_batches(batch_size=64):
                normalized = []
                for row in batch.to_pylist():
                    check()
                    image = row.get('image')
                    data = image.get('bytes') if image else None
                    if not isinstance(data, bytes):
                        raise ValueError('IllusionVQA row has no embedded image')
                    checked_image(data)
                    image_extension(data)
                    source_id = f"{task}:test:{row['id']}"
                    if source_id in seen:
                        raise ValueError('IllusionVQA source ID collision')
                    seen.add(source_id)
                    item = {'source_id': source_id, 'task': task, 'split': 'test', 'source_file': ILLUSION_SOURCE_FILE, 'id': row['id'],
                            'question': row['question'], 'options': row['options'], 'answer': row['answer'], 'category': row['category'],
                            'source': row.get('source'), 'url': row.get('url'), 'reasoning': row.get('reasoning'), 'images': [image]}
                    digest.add(item)
                    normalized.append(item)
                    count += 1
                writer.write_table(pa.Table.from_pylist(normalized, schema=schema))
            if count != expected:
                raise ValueError(f'IllusionVQA {task} has {count} rows; expected {expected}')
    return {'path': output, 'format': 'parquet', 'count': digest.count, 'rows_sha256': digest.hexdigest(),
            'file_sha256': file_sha256(output), 'columns': [field.name for field in schema]}


# ---- JailBreakV-28K and OmniSafeBench-MM (records only; media are served by pinned remote URL) ------------------

@converter('jailbreakv_28k')
def jailbreakv_28k(params, inputs, output_dir, check):
    """JailBreakV-28K's official CSV, every row kept as published.

    `media_path` is the row's `image_path` only when that image is in `params.released_images` (the files present in the pinned
    Hub tree, of which there are few); otherwise it is empty, so no asset is promised that cannot be fetched."""
    released = set(params['released_images'])

    def rows():
        with Path(inputs['source_csv']).open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                if not row['id']:
                    raise ValueError('JailBreakV row without an official ID')
                row['media_path'] = row['image_path'] if row['image_path'] in released else ''
                yield row
    return write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)


@converter('omnisafebench_mm')
def omnisafebench_mm(params, inputs, output_dir, check):
    """OmniSafeBench-MM's data_full.json, every row kept; `media_path` is `image_path` without its `dataset/` prefix (the Hub stores
    assets under `images/`)."""
    def rows():
        for row in json.loads(Path(inputs['source_json']).read_text()):
            image = row['image_path']
            if not image.startswith('dataset/images/') or '..' in PurePosixPath(image).parts:
                raise ValueError('Unexpected OmniSafeBench media reference')
            row['media_path'] = image.removeprefix('dataset/')
            yield row
    return write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)


# ---- HC-Bench (wild subset) ---------------------------------------------------------------------------------------

@converter('hc_bench')
def hc_bench(params, inputs, output_dir, check):
    """HC-Bench's wild subset: the index CSV the catalogue reads, built from the pinned image files themselves.

    Inputs are one `image_<NN>` per file (image_01 is `wild/image_01.png`), taken in key order. Each row records the path, the
    subset and the file's byte length and SHA-256; the images are copied unchanged under `<output>/media/wild/`. The index is
    written exactly as the maintainer's CSV (default `csv` dialect, CRLF line ends), so its file checksum matches too."""
    import csv
    subset, extension = params.get('subset', 'wild'), params.get('extension', 'png')
    media_dir = Path(output_dir) / 'media'
    columns = ['path', 'source_subset', 'source_bytes', 'source_sha256']
    output = Path(output_dir) / 'wild_index.csv'
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = RowDigest()
    with output.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for key in sorted(k for k in inputs if k.startswith('image_')):
            check()
            name = f'{key}.{extension}'
            data = checked_image(Path(inputs[key]).read_bytes())
            if image_extension(data) != '.' + extension:
                raise ValueError(f'HC-Bench image is not a {extension}: {name}')
            relative = f'{subset}/{name}'
            store_image(media_dir, relative, data)
            row = {'path': relative, 'source_subset': subset, 'source_bytes': str(len(data)), 'source_sha256': hashlib.sha256(data).hexdigest()}
            writer.writerow([row[column] for column in columns])
            digest.add(row)
    if digest.count == 0:
        raise ValueError('HC-Bench conversion received no images')
    return {'path': output, 'format': 'csv', 'count': digest.count, 'rows_sha256': digest.hexdigest(), 'file_sha256': file_sha256(output),
            'columns': columns, 'media_dir': media_dir}


# ---- MMBench (English dev, CircularEval variants) ------------------------------------------------------------------

def mmbench_image(reference: str, images: dict) -> tuple[str, bytes]:
    """Follow an `image` cell to its base64 payload: a short cell names another row's index, a long one is the image itself."""
    import base64
    seen = set()
    while True:
        if reference in seen:
            raise ValueError('Cyclic MMBench image reference')
        seen.add(reference)
        if reference not in images:
            raise ValueError('Missing MMBench image reference')
        value = images[reference]
        if len(value) > 64:
            return reference, base64.b64decode(value, validate=True)
        reference = value


@converter('mmbench_dev')
def mmbench_dev(params, inputs, output_dir, check):
    """MMBench's official TSV (one row per circular choice-order variant): every original column kept, base64 images decoded once.

    Adds `image` (the decoded file name, `<sha256>.jpg|.png`), `source_id` (= `index`), `source_image_index` (the row that holds the
    payload), `image_sha256`, `image_width`, `image_height` and `choices` ("A. text" for each non-empty option). The images are the
    exact decoded bytes, written flat under `<output>/images/` (the catalogue's `media_root`)."""
    import csv
    import io
    import pyarrow as pa
    import pyarrow.parquet as pq
    from PIL import Image
    media_dir = Path(output_dir) / 'images'
    limit = csv.field_size_limit()
    csv.field_size_limit(max(limit, 10_000_000))
    try:
        with Path(inputs['source_tsv']).open(encoding='utf-8') as stream:
            raw = list(csv.DictReader(stream, delimiter='\t'))
    finally:
        csv.field_size_limit(limit)
    images = {row['index']: row['image'] for row in raw}
    if len(images) != len(raw):
        raise ValueError('Duplicate MMBench source indices')
    prepared, groups, digest = [], set(), RowDigest()
    for row in raw:
        check()
        holder, data = mmbench_image(row['index'], images)
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'JPEG', 'PNG'}:
                raise ValueError('Unsupported MMBench image encoding')
            suffix = '.jpg' if image.format == 'JPEG' else '.png'
            width, height = image.size
            image.verify()
        sha = hashlib.sha256(data).hexdigest()
        store_image(media_dir, sha + suffix, data)
        groups.add(holder)
        record = {**row, 'image': sha + suffix, 'source_id': row['index'], 'source_image_index': holder, 'image_sha256': sha,
                  'image_width': width, 'image_height': height, 'choices': [f'{key}. {row[key]}' for key in 'ABCD' if row.get(key)]}
        prepared.append(record)
        digest.add(record)
    if params.get('image_groups') is not None and len(groups) != params['image_groups']:
        raise ValueError('MMBench image-group population differs from the pinned release')
    output = Path(output_dir) / 'records.parquet'
    table = pa.Table.from_pylist(prepared)
    pq.write_table(table, output, compression='zstd')
    return {'path': output, 'format': 'parquet', 'count': digest.count, 'rows_sha256': digest.hexdigest(), 'file_sha256': file_sha256(output),
            'columns': table.schema.names, 'media_dir': media_dir}
