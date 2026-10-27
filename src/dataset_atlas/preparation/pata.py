"""Bounded, reproducible PATA metadata index; image inspection stays unavailable."""
from __future__ import annotations
from datetime import datetime, timezone
from contextlib import nullcontext
import hashlib
import heapq
import json
import os
import re
from pathlib import Path
import tempfile
import time
import httpx
from dataset_atlas.adapters import get_adapter
from dataset_atlas.converters.pata import convert_pata
from dataset_atlas.models import Dataset, FieldDescriptor, Pack
from dataset_atlas.queries.parquet import build_parquet_snapshot, ParquetSnapshot
from dataset_atlas.registry import Registry
from dataset_atlas.preparation import atomic
from dataset_atlas.preparation.slots import try_writer_slot

REVISION = 'c65a7f34e6e200d77b82a53d33b224389798ff6c'
SOURCES = {
    'files': ('pata_fairness.files.lst', '735d14cf33cf8bd0b8d5ca7b13db7c2ea11c48330529c23c86f596f863964033', 744512),
    'captions': ('pata_fairness.captions.json', '592dd19362dd62a3372224e2e0b599b418e44bbea852c8f298e17dffa1c455b0', 15437),
}


def metadata_contract():
    """Fixed data pins for the builtin route; no caller-selected executable or URL."""
    return {'revision': REVISION, 'files': [
        {'source_name': name, 'sha256': digest, 'bytes': size,
         'url': f'https://raw.githubusercontent.com/pata-fairness/pata_dataset/{REVISION}/{name}'}
        for name, digest, size in SOURCES.values()]}


def prepare_metadata(root: Path, *, execute=False, max_download_bytes=1_000_000,
                     max_output_bytes=20_000_000, activate=True, _version_id=None,
                     _writer_lease=None, _cancel_check=None):
    root = Path(root).resolve()
    if type(activate) is not bool or (_version_id is not None and not re.fullmatch('[a-f0-9]{64}', _version_id)):
        raise ValueError('PATA activation and managed version identity are invalid')
    expected = sum(item[2] for item in SOURCES.values())
    if type(max_download_bytes) is not int or max_download_bytes < expected or max_download_bytes > 5_000_000:
        raise ValueError('PATA metadata needs a download budget between 759949 and 5000000 bytes')
    if type(max_output_bytes) is not int or not 10_000_000 <= max_output_bytes <= 100_000_000:
        raise ValueError('PATA metadata needs an output budget between 10 and 100 MB')
    result = {'dataset_id': 'pata', 'source_revision': REVISION, 'expected_download_bytes': expected,
              'expected_records': 4934, 'expected_preview_records': 100, 'native_image_preview_count': 0,
              'scope': 'All released label/URL rows and exact scene captions; no third-party media requested.',
              'status': 'planned', 'executed': execute, 'activated': False}
    if not execute:
        return result
    deadline = time.monotonic() + 120
    def check():
        if _cancel_check is not None:
            _cancel_check()
        if time.monotonic() > deadline:
            raise TimeoutError('PATA metadata preparation exceeded 120 seconds')
    locks = root / 'work/preparation'
    if locks.is_symlink() or not locks.resolve().is_relative_to(root):
        raise ValueError('PATA preparation lease escapes the workspace')
    locks.mkdir(parents=True, exist_ok=True)
    # Only the fixed normal-worker dispatch supplies its already-held lease.
    # The public CLI/helper path acquires the same two-slot writer policy here.
    lease = nullcontext() if _writer_lease is not None else try_writer_slot(locks, 'pata', 'pata-metadata-' + REVISION)
    if lease is None:
        raise RuntimeError('Another preparation owns the PATA writer')
    with lease:
        sources = root / 'work/sources/pata' / REVISION
        if sources.is_symlink() or not sources.resolve().is_relative_to(root):
            raise ValueError('PATA source directory escapes the workspace')
        sources.mkdir(parents=True, exist_ok=True)
        inputs = {}
        downloaded = 0
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False, headers={'Accept-Encoding': 'identity'}) as client:
            for key, (name, checksum, size) in SOURCES.items():
                check()
                path = sources / name
                if path.is_symlink():
                    raise ValueError('PATA source file is a symlink')
                if path.exists():
                    if path.stat().st_size != size or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                        raise ValueError('Retained PATA source differs from the pinned native file')
                else:
                    url = f'https://raw.githubusercontent.com/pata-fairness/pata_dataset/{REVISION}/{name}'
                    chunks = []
                    with client.stream('GET', url) as response:
                        response.raise_for_status()
                        if response.headers.get('content-encoding', 'identity') != 'identity':
                            raise ValueError('Unexpected compressed PATA transport')
                        for chunk in response.iter_raw(chunk_size=65536):
                            check()
                            downloaded += len(chunk)
                            if downloaded > max_download_bytes or sum(map(len, chunks)) + len(chunk) > size:
                                raise ValueError('PATA source exceeds its pinned byte length or transfer budget')
                            chunks.append(chunk)
                    data = b''.join(chunks)
                    if len(data) != size or hashlib.sha256(data).hexdigest() != checksum:
                        raise ValueError('Downloaded PATA file differs from its native pin')
                    path.write_bytes(data)
                inputs[key] = path
        converted = sources / 'converted'
        if converted.is_symlink() or not converted.resolve().is_relative_to(root):
            raise ValueError('PATA converted source escapes the workspace')
        converted.mkdir(exist_ok=True)
        if (converted / 'pata-metadata.jsonl').is_symlink():
            raise ValueError('PATA converted source is a symlink')
        with tempfile.TemporaryDirectory(prefix='pata-conversion-', dir=sources) as scratch:
            conversion = convert_pata({'max_output_bytes': max_output_bytes}, inputs, Path(scratch), check)
            output = converted / 'pata-metadata.jsonl'
            if output.exists():
                if (output.stat().st_size != conversion['path'].stat().st_size
                        or hashlib.sha256(output.read_bytes()).hexdigest() != conversion['file_sha256']):
                    raise ValueError('Retained PATA converted source differs; original input was not modified')
            else:
                os.replace(conversion['path'], output)
                output.chmod(0o444)
            conversion['path'] = output
        if conversion['count'] != 4934:
            raise ValueError('PATA native population count changed')
        snapshot_id = 'pata-metadata-' + conversion['rows_sha256'][:24]
        # Keep the old metadata-only and frozen versions intact. The index
        # identity stays source-derived; only the prepared presentation changes.
        version = _version_id or 'metadata-preview-v2-' + conversion['rows_sha256']
        directory = root / 'work/prepared/pata' / version
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            raise ValueError('PATA prepared directory escapes the workspace')
        directory.mkdir(parents=True, exist_ok=True)
        dataset = Registry(root).baseline_dataset('pata').model_copy(deep=True)
        dataset.release = 'PATA author label/URL and caption metadata @ ' + REVISION
        dataset.snapshot_id = snapshot_id
        dataset.source_url = 'https://github.com/pata-fairness/pata_dataset'
        dataset.adapter_config = {'path': str(conversion['path'].relative_to(root)), 'format': 'jsonl',
                                  'sha256': conversion['file_sha256'], 'record_identity': 'source_row',
                                  'mapping': {'id': 'source_identifier'}}
        dataset.coverage.adapter = 'implemented'
        dataset.coverage.access = 'public'
        dataset.coverage.complete_data = 'indexed_metadata_partial_media'
        dataset.coverage.total_count = 4934
        dataset.coverage.preview_count = 100
        dataset.coverage.preview = 'metadata_only'
        dataset.coverage.blockers = [
            'All 4,934 author label/URL rows and 24 exact caption objects are indexed; no image preview is claimed.',
            'Third-party images are not archived or fetched. URL availability and image rights remain unverified.',
            'Demographic labels are author annotations, not self-reports. Historical paper membership and redistribution remain unreviewed.']
        resolved = dataset.model_copy(deep=True)
        resolved.adapter_config['path'] = str(conversion['path'])
        adapter = get_adapter(resolved)
        source = adapter.prepare(adapter.plan(1000, max_output_bytes))
        fields = [FieldDescriptor.model_validate({'id': 'source.' + name, 'name': name, 'dtype': dtype})
                  for name, dtype in [('scene', 'category'), ('source_race', 'category'),
                    ('source_gender', 'category'), ('source_age', 'category'),
                    ('media_url', 'string'), ('source_identifier', 'string'),
                    ('source_row', 'number'), ('captions', 'object'), ('media_available', 'boolean')]]
        def records():
            cursor = None
            while True:
                check()
                batch = adapter.iter_records(source, cursor, 1000)
                yield from batch.records
                cursor = batch.next_cursor
                if not cursor:
                    break
        index = directory / 'snapshot'
        if not index.exists():
            build_parquet_snapshot(records(), fields, index, root=root, dataset_id='pata',
                                   release_id=dataset.release, snapshot_id=snapshot_id,
                                   expected_count=4934, population_scope='complete',
                                   max_bytes=max_output_bytes - conversion['path'].stat().st_size)
        if (index / 'records.parquet').stat().st_size + conversion['path'].stat().st_size > max_output_bytes:
            raise ValueError('Retained PATA index exceeds the output budget')
        reader = ParquetSnapshot(root, index)
        if ((reader.dataset_id, reader.release_id, reader.snapshot_id, reader.unit,
             reader.population_scope, reader.record_count) !=
                ('pata', dataset.release, snapshot_id, 'example', 'complete', 4934)
                or reader.fields != fields):
            raise ValueError('Retained PATA index identity differs')
        import pyarrow.parquet as pq
        from dataset_atlas.converters.pata import native_rows
        expected_rows = iter(native_rows(inputs['files'], inputs['captions'], check))
        verified = 0
        preview_heap = []
        from dataset_atlas.queries.parquet import _BASE_FIELDS, _field_value, _encode_field
        for batch in pq.ParquetFile(index / 'records.parquet').iter_batches(batch_size=128):
            for stored in batch.to_pylist():
                check()
                row = next(expected_rows)
                expected_record = adapter._record(row, verified)
                rank = int.from_bytes(hashlib.sha256(f'0:{expected_record.id}'.encode()).digest(), 'big')
                item = (-rank, expected_record.id, expected_record)
                if len(preview_heap) < 100:
                    heapq.heappush(preview_heap, item)
                elif item[:2] > preview_heap[0][:2]:
                    heapq.heapreplace(preview_heap, item)
                if json.loads(stored['record_json']) != expected_record.model_dump(mode='json'):
                    raise ValueError('PATA canonical record differs from its exact native row/caption join')
                for name in _BASE_FIELDS:
                    if stored[name] != _field_value(expected_record, name):
                        raise ValueError('PATA materialized identity field differs from its native record')
                for field_id, (column, dtype, _) in reader.registry.items():
                    if field_id not in _BASE_FIELDS and stored[column] != _encode_field(_field_value(expected_record, field_id), dtype, field_id):
                        raise ValueError('PATA materialized query field differs from its native record')
                search_text = '\n'.join([expected_record.text or '', expected_record.question or '',
                                        json.dumps(expected_record.source, ensure_ascii=False, separators=(',', ':'))]).lower()
                if stored['search_text'] != search_text:
                    raise ValueError('PATA materialized search text differs from its native record')
                verified += 1
        if verified != 4934 or next(expected_rows, None) is not None:
            raise ValueError('PATA native/canonical membership differs')
        preview = [item[2] for item in sorted(preview_heap, key=lambda item: (-item[0], item[1]))]
        if len(preview) != 100 or any(record.assets for record in preview):
            raise ValueError('PATA metadata preview membership or media contract differs')
        pack = Pack(dataset=dataset, fields=fields, records=preview, sampling={
            'method': 'sha256_bottom_k_metadata_records', 'seed': 0, 'unit': 'example',
            'population': 'complete released label/URL and exact-caption metadata', 'population_count': 4934,
            'requested_count': 100, 'returned_count': 100, 'media_representation': 'none',
            'selection_note': 'Metadata-only native records; zero images fetched. Author labels are not self-reports.'})
        pack_path = directory / 'pack/pack.json'
        if pack_path.is_symlink() or not pack_path.resolve().is_relative_to(root):
            raise ValueError('PATA preview pack escapes the workspace')
        if pack_path.exists():
            retained_pack = Pack.model_validate_json(pack_path.read_text())
            if (retained_pack.records != pack.records or retained_pack.fields != fields
                    or retained_pack.sampling != pack.sampling or retained_pack.checksums
                    or retained_pack.dataset.snapshot_id != snapshot_id):
                raise ValueError('Retained PATA metadata preview differs from its exact native records')
        else:
            atomic(pack_path, pack.model_dump(mode='json'), compact=True)
        output_bytes = conversion['path'].stat().st_size + sum(path.stat().st_size for path in directory.rglob('*') if path.is_file())
        if output_bytes > max_output_bytes:
            raise ValueError('PATA metadata index and preview exceed the output budget')
        result.update(status='completed', downloaded_bytes=downloaded, snapshot_id=snapshot_id,
                      plan_id=version, rows_sha256=conversion['rows_sha256'],
                      preview_records=100, output_bytes=output_bytes,
                      exact_native_record_checks=verified, checked_at_utc=datetime.now(timezone.utc).isoformat(), sources=[
                          {'name': name, 'sha256': digest, 'bytes': size} for name, digest, size in SOURCES.values()])
        for key, (_, checksum, size) in SOURCES.items():
            path = inputs[key]
            if (path.is_symlink() or path.stat().st_size != size
                    or hashlib.sha256(path.read_bytes()).hexdigest() != checksum):
                raise ValueError('Native PATA source changed during conversion/index verification')
        dataset_path = directory / 'dataset.json'
        if dataset_path.exists():
            retained = Dataset.model_validate_json(dataset_path.read_text())
            if (retained.id, retained.release, retained.snapshot_id) != ('pata', dataset.release, snapshot_id):
                raise ValueError('Retained PATA dataset identity differs')
        else:
            atomic(dataset_path, dataset.model_dump(mode='json'))
        receipt_path = directory / 'receipt.json'
        if not receipt_path.exists():
            # Include the receipt itself and dataset metadata in the measured
            # output. Iterate only within a new candidate; existing receipts
            # and frozen version files remain byte-identical on repeat runs.
            for _ in range(3):
                atomic(receipt_path, result)
                measured = conversion['path'].stat().st_size + sum(path.stat().st_size for path in directory.rglob('*') if path.is_file())
                if result['output_bytes'] == measured:
                    break
                result['output_bytes'] = measured
        else:
            result['output_bytes'] = conversion['path'].stat().st_size + sum(path.stat().st_size for path in directory.rglob('*') if path.is_file())
        final_output_bytes = result['output_bytes']
        if not isinstance(final_output_bytes, int) or final_output_bytes > max_output_bytes:
            raise ValueError('PATA final metadata and receipt exceed the output budget')
        check()
        if activate:
            atomic(directory.parent / 'active.json', {'version': version})
            result['activated'] = True
        return result
