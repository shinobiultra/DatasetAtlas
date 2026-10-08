"""Bounded conversions of native released tables and archive members."""
from __future__ import annotations
import csv
import hashlib
import tarfile
from pathlib import Path
from typing import IO
from . import converter, write_rows

MAX_MEMBER_BYTES = 500_000_000


@converter('audioset_segments')
def audioset_segments(params, inputs, output_dir, check):
    """Native weak-label segment tables; audio is hosted separately by YouTube."""
    import pyarrow as pa
    with inputs['class_labels'].open(encoding='utf-8',newline='') as stream:
        labels={row['mid']:row['display_name'] for row in csv.DictReader(stream)}
    def rows():
        for split in ('balanced_train','eval','unbalanced_train'):
            with inputs[split].open(encoding='utf-8',newline='') as stream:
                headers=[next(stream).rstrip('\n') for _ in range(3)]
                if headers[2] != '# YTID, start_seconds, end_seconds, positive_labels':
                    raise ValueError('AudioSet native columns changed')
                for values in csv.reader(stream,skipinitialspace=True):
                    if len(values)!=4:raise ValueError('Malformed native AudioSet segment')
                    video,start,end,positive=values
                    codes=positive.split(',')
                    if any(code not in labels for code in codes):raise ValueError('AudioSet label absent from native class table')
                    yield {'YTID':video,'start_seconds':start,'end_seconds':end,'positive_labels':positive,
                           'split':split,'source_id':f'{split}:{video}:{start}:{end}',
                           'label_names':[labels[code] for code in codes],
                           'media_availability':'YouTube audio not acquired; inspect native segment annotations',
                           'source_header':headers}
    schema=pa.schema([(key,pa.string()) for key in ['YTID','start_seconds','end_seconds','positive_labels','split','source_id','media_availability']]+[
        ('label_names',pa.list_(pa.string())),('source_header',pa.list_(pa.string()))])
    return write_rows(rows,output_dir/'segments.parquet','parquet',check,schema=schema)


@converter('vhd11k_annotations')
def vhd11k_annotations(params, inputs, output_dir, check):
    """Preserve both native tables and add explicit modality-scoped identities."""
    from pathlib import PurePosixPath
    def rows():
        for modality in ('image','video'):
            with inputs[modality+'_annotations'].open(encoding='utf-8-sig',newline='') as stream:
                for row in csv.DictReader(stream):
                    name=row[modality+'Path']
                    if not name or PurePosixPath(name).is_absolute() or len(PurePosixPath(name).parts)!=1 or name in {'.','..'}:
                        raise ValueError('Unsafe native VHD11K media filename')
                    row.update(modality=modality,source_id=modality+':'+name,media_ref=modality+'s/'+name)
                    yield row
    return write_rows(rows,output_dir/'records.jsonl','jsonl',check)


def _member(archive: tarfile.TarFile, name: str) -> IO[bytes]:
    info = archive.getmember(name)
    if not info.isreg() or info.size > MAX_MEMBER_BYTES:
        raise ValueError(f'{name} is not a regular file within the size limit')
    stream = archive.extractfile(info)
    if stream is None:
        raise ValueError(f'{name} cannot be read from the archive')
    return stream


@converter('tar_csv_member')
def tar_csv_member(params, inputs, output_dir, check):
    """One CSV member of a tarball, unchanged: its rows are exactly what the publisher released."""
    import io
    def rows():
        with tarfile.open(inputs['source_tar']) as archive, _member(archive, params['member']) as stream:
            yield from csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
    return write_rows(rows, output_dir / Path(params['member']).name, 'csv', check)


@converter('activation_summary')
def activation_summary(params, inputs, output_dir, check):
    """One row per neuron summarising its published activation values (the full 50,000-value rows stay in the source file).

    `values_sha256` is the SHA-256 of the row's values exactly as published, comma-joined, so a summary can be checked against
    the source without redistributing it. Minimum, maximum, mean and the count of non-zero values are computed in double precision."""
    import io
    def rows():
        with tarfile.open(inputs['source_tar']) as archive, _member(archive, params['member']) as stream:
            reader = csv.reader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
            next(reader)
            for index, row in enumerate(reader):
                raw = row[1:]
                values = [float(value) for value in raw]
                yield {'k': row[0], 'source_row_index': index, 'value_count': len(values),
                       'values_sha256': hashlib.sha256(','.join(raw).encode()).hexdigest(), 'minimum': min(values),
                       'maximum': max(values), 'mean': sum(values) / len(values), 'nonzero_count': sum(1 for v in values if v != 0)}
    return write_rows(rows, output_dir / 'activations_index.csv', 'csv', check)
