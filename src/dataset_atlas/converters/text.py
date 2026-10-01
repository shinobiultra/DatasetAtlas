"""Conversions of pinned original text benchmarks (GLUE tasks, SentEval MRPC, CEBaB) into split-preserving tables.

Each converter reproduces, exactly, the table the catalogue's maintained copy was built from; the recipe pins its row digest.
Original columns are preserved; GLUE's withheld test labels stay null (`label_status: withheld_by_glue`).
"""
from __future__ import annotations
import json
import zipfile
from pathlib import Path
from . import converter, write_rows

GLUE_TASKS = {'CoLA': 'CoLA', 'QNLI': 'QNLI', 'QQP': 'QQP', 'WNLI': 'WNLI'}


def tsv_rows(text: str, headers=None):
    lines = text.splitlines()
    if headers is None:
        headers = lines.pop(0).split('\t')
    for ordinal, line in enumerate(lines):
        values = line.split('\t')
        if len(values) != len(headers):
            raise ValueError(f'Malformed source row {ordinal}: expected {len(headers)} columns, got {len(values)}')
        yield ordinal, dict(zip(headers, values, strict=True))


def glue_rows(archive_path: Path, folder: str, cola: bool):
    with zipfile.ZipFile(archive_path) as z:
        for split in ('train', 'dev', 'test'):
            member = f'{folder}/{split}.tsv'
            headers = ['publication', 'label', 'author_annotation', 'sentence'] if cola and split != 'test' else None
            for ordinal, row in tsv_rows(z.read(member).decode('utf-8-sig'), headers):
                label = row.get('label', row.get('is_duplicate'))
                row.update(source_id=f'{split}:{ordinal}', split=split, source_member=member, label=label,
                           label_status='withheld_by_glue' if label is None else 'source_labeled')
                row['display_text'] = row.get('sentence', row.get('question1', row.get('sentence1', '')))
                if 'question2' in row:
                    row['display_text'] += '\n\n' + row['question2']
                if 'sentence2' in row:
                    row['display_text'] += '\n\n' + row['sentence2']
                yield row


@converter('glue_task')
def glue_task(params, inputs, output_dir, check):
    task = params['task']
    if task not in GLUE_TASKS:
        raise ValueError(f'Unknown GLUE task: {task!r}')
    archive = inputs['source_zip']
    return write_rows(lambda: glue_rows(archive, GLUE_TASKS[task], task == 'CoLA'), output_dir / 'records.parquet', 'parquet', check)


@converter('mrpc_senteval')
def mrpc_senteval(params, inputs, output_dir, check):
    def rows():
        for split in ('train', 'test'):
            path = inputs[f'{split}_txt']
            for ordinal, row in tsv_rows(path.read_text(encoding='utf-8-sig')):
                row.update(source_id=f'{split}:{ordinal}', split=split, source_member=params['member_names'][split], label=row['Quality'],
                           label_status='source_labeled', display_text=row['#1 String'] + '\n\n' + row['#2 String'])
                yield row
    return write_rows(rows, output_dir / 'records.parquet', 'parquet', check)


@converter('cebab')
def cebab(params, inputs, output_dir, check):
    def rows():
        with zipfile.ZipFile(inputs['source_zip']) as z:
            for split in ('train_inclusive', 'train_exclusive', 'train_observational', 'dev', 'test'):
                member = f'CEBaB-v1.1/{split}.json'
                for original in json.loads(z.read(member)):
                    yield {**original, 'source_id': split + ':' + original['id'], 'split': split, 'source_member': member}
    return write_rows(rows, output_dir / 'records.jsonl', 'jsonl', check)


@converter('glue_sst2')
def glue_sst2(params, inputs, output_dir, check):
    """GLUE SST-2: train/dev/test TSVs with typed columns; the test split's labels are withheld (null)."""
    import csv
    import io
    import pyarrow as pa
    counts = {'train': 67349, 'dev': 872, 'test': 1821}

    def rows():
        with zipfile.ZipFile(inputs['source_zip']) as zf:
            for split, expected in counts.items():
                member = f'SST-2/{split}.tsv'
                info = zf.getinfo(member)
                if info.file_size > 5_000_000:
                    raise ValueError(f'GLUE TSV member exceeds 5 MB: {member}')
                reader = csv.DictReader(io.StringIO(zf.read(info).decode('utf-8'), newline=''), delimiter='\t')
                required = ['index', 'sentence'] if split == 'test' else ['sentence', 'label']
                if reader.fieldnames != required:
                    raise ValueError(f'Unexpected GLUE {split} fields: {reader.fieldnames}')
                count = 0
                for index, row in enumerate(reader):
                    if not row['sentence'].strip():
                        raise ValueError(f'Empty GLUE sentence at {split}:{index}')
                    if split == 'test':
                        if row['index'] != str(index):
                            raise ValueError('GLUE test source index is not sequential')
                        label = None
                    else:
                        if row['label'] not in {'0', '1'}:
                            raise ValueError(f'Invalid GLUE label at {split}:{index}')
                        label = int(row['label'])
                    count += 1
                    yield {'source_id': f'{split}:{index}', 'sentence': row['sentence'], 'label': label,
                           'label_status': 'withheld_by_glue' if label is None else 'source_labeled', 'split': split,
                           'source_index': index, 'source_member': member}
                if count != expected:
                    raise ValueError(f'GLUE {split} count {count} differs from expected {expected}')
    schema = pa.schema([('source_id', pa.string()), ('sentence', pa.string()), ('label', pa.int8()), ('label_status', pa.string()),
                        ('split', pa.string()), ('source_index', pa.int32()), ('source_member', pa.string())])
    return write_rows(rows, output_dir / 'records.parquet', 'parquet', check, schema=schema)
