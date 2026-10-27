"""Read-only, aggregate-only audit of one native scope expansion candidate.

Native record contents remain local. This checks artifact integrity, exact source
ordinals and locally retained annotation fidelity; it never activates a version.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pyarrow.parquet as pq


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit(root: Path, dataset_id: str, version: str):
    root = root.resolve()
    directory = root / 'work/prepared' / dataset_id / version
    dataset = json.loads((directory/'dataset.json').read_text())
    receipt = json.loads((directory/'receipt.json').read_text())
    manifest = json.loads((directory/'snapshot/manifest.json').read_text())
    pack = json.loads((directory/'pack/pack.json').read_text())
    assert dataset['id'] == dataset_id and receipt['record_count'] == manifest['record_count']
    assert manifest['dataset_id'] == dataset_id
    assert manifest['snapshot_id'] == dataset['snapshot_id'] == receipt['snapshot_id']
    # Instantiate the production reader to validate every declared snapshot file.
    from dataset_atlas.queries.parquet import ParquetSnapshot
    reader = ParquetSnapshot(root, directory/'snapshot')
    assert reader.record_count == receipt['record_count']
    for name, checksum in manifest['checksums'].items():
        path = (directory/'snapshot'/name).resolve()
        assert path.is_relative_to((directory/'snapshot').resolve()) and digest(path) == checksum
    source_files = dataset['adapter_config'].get('source_files', dataset['adapter_config'].get('files', []))
    local_sources = {}
    for entry in source_files:
        path = Path(entry['path'])
        assert path.is_file() and path.stat().st_size == entry['bytes']
        assert digest(path) == entry['sha256']
        local_sources[entry['source_name']] = entry
    for name, checksum in pack.get('checksums', {}).items():
        path = (directory/'pack'/name).resolve()
        assert path.is_relative_to((directory/'pack').resolve()) and digest(path) == checksum
    ids = set(); kinds = Counter(); splits = Counter(); media = Counter(); ordinal_counts = Counter()
    checked_native = 0
    science_rows = {}
    if dataset_id == 'scienceqa':
        for name, entry in local_sources.items():
            parquet = pq.ParquetFile(entry['path'])
            columns = [field.name for field in parquet.schema_arrow if field.name != 'image']
            science_rows[name] = parquet.read(columns=columns).to_pylist()
    mv_rows = {}
    if dataset_id == 'mvbench':
        config = dataset['adapter_config']
        mv_rows = {entry['path_key']: json.loads(Path(config[entry['path_key']]).read_text())
                   for entry in config['annotations']}
    hc_rows = []; hc_native = {}
    if dataset_id == 'hc-bench':
        hc_rows = [json.loads(line) for line in Path(dataset['adapter_config']['path']).read_text().splitlines()]
        for entry in local_sources.values():
            native_path=unquote(urlsplit(entry['url']).path).split('/'+dataset['release']+'/',1)[1]
            path=Path(entry['path'])
            hc_native[native_path]=(entry,json.loads(path.read_text()) if entry['format']=='json'
                                    else path.read_text() if entry['format']=='txt' else None)
    for batch in pq.ParquetFile(directory/'snapshot/records.parquet').iter_batches(columns=['record_json'], batch_size=128):
        for value in batch.column(0).to_pylist():
            record = json.loads(value)
            assert record['id'] not in ids
            ids.add(record['id'])
            assert (record['dataset_id'], record['snapshot_id'], record['release_id']) == (
                dataset_id, dataset['snapshot_id'], dataset['release'])
            source = record['source']; origin = source.get('_atlas_origin', {})
            kinds[source.get('unit_kind', 'question')] += 1
            if origin.get('file'):
                name = origin['file']; ordinal = origin['row']
                assert ordinal == ordinal_counts[name]
                ordinal_counts[name] += 1
                splits[source.get('_atlas_native_split', Path(name).name.split('-')[0])] += 1
            for asset in record['assets']:
                media[(asset['modality'], asset['metadata'].get('availability', 'available') if asset['uri'] else asset['metadata'].get('availability', 'no_uri'))] += 1
            if dataset_id == 'scienceqa':
                expected = science_rows[origin['file']][origin['row']]
                assert all(source[key] == native for key, native in expected.items())
                checked_native += 1
            elif dataset_id == 'mvbench':
                expected = mv_rows[origin['file']][origin['row']]
                assert {key:native for key,native in source.items() if not key.startswith('_atlas_')} == expected
                assert record['question'] == expected['question'] and record['choices'] == expected['candidates']
                checked_native += 1
            elif dataset_id == 'hc-bench':
                assert source == hc_rows[checked_native]
                entry,native=hc_native[source['source_file']]
                if source['unit_kind']=='image':
                    assert source['source_sha256']==entry['sha256'] and source['source_bytes']==str(entry['bytes'])
                elif source['unit_kind']=='annotation':
                    assert source['native_annotation']==native[source['source_row']]
                    assert source['source_file_sha256']==entry['sha256']
                else:
                    assert source['text']==native and source['source_file_sha256']==entry['sha256']
                checked_native += 1
    assert len(ids) == manifest['record_count']
    if dataset_id == 'mmmu':
        footers = json.loads((root/'work/finalization-20261027/scope-expansions/mmmu-native-footer-counts.json').read_text())
        assert dict(ordinal_counts) == footers['source_file_counts']
    result = {'dataset_id': dataset_id, 'version': version, 'snapshot_id': dataset['snapshot_id'],
        'native_record_count': len(ids), 'native_kind_counts': dict(kinds), 'native_split_counts': dict(splits),
        'media_counts': {f'{kind}/{state}':count for (kind,state),count in media.items()},
        'preview_records': len(pack['records']),
        'preview_records_with_media': sum(any(asset['uri'] for asset in record['assets']) for record in pack['records']),
        'preview_originals_pinned': len(pack.get('checksums', {})),
        'local_source_files_sha256_verified': len(local_sources),
        'native_image_mime_overrides':len(dataset['adapter_config'].get('media_type_overrides',{})),
        'exact_local_native_annotation_rows_checked': checked_native,
        'snapshot_file_sha256': digest(directory/'snapshot/records.parquet'),
        'source_integrity_scope': ('Full local source SHA-256 checked.' if local_sources else
                                   'Remote Parquet strong ETags and full metadata index; complete remote source SHA-256 not computed locally.'),
        'activation': 'Candidate only; active pointer was not written by preparation.'}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--dataset', required=True, choices=['scienceqa','mmmu','mvbench','hc-bench'])
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root, args.dataset, args.version)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
