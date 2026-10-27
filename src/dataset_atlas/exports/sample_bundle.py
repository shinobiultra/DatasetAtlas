"""Build a bounded, checksummed sample browser from validated static output.

Publication approval and building a fresh frontend belong to the caller. This
module packages the three already approved previews without changing their
records, original media, sampling, or derived artifact populations.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from dataset_atlas import sample_launcher


_DATASETS = ('clevr', 'eurosat', 'pairs')
_FORBIDDEN_DIRS = {'work', 'local-config', 'registry', 'reports', 'node_modules', '__pycache__'}
_FORBIDDEN_SUFFIXES = {'.pdf', '.pem', '.key', '.pkl', '.pickle', '.joblib', '.sqlite', '.sqlite3', '.db', '.py', '.pyc', '.map', '.whl', '.zip', '.tar', '.gz', '.pt', '.pth', '.safetensors'}
_DATA_JSON = {'catalogue.json', 'guide.json', 'thumbnails.json', *(name + '.json' for name in _DATASETS)}
_README = """Dataset Atlas sample browser

Run: python3 OPEN_ATLAS.py
Check without serving: python3 OPEN_ATLAS.py --check
No automatic browser: python3 OPEN_ATLAS.py --no-browser
Stop with Ctrl-C. The server listens only at http://127.0.0.1:8767/ by default.
Reusing this address keeps saved selections available between restarts in the same
browser. Use --port PORT to choose another stable address, or --port 0 for a
temporary port; saved selections remain tied to the address where you made them.
Python 3.11 or newer is sufficient; no package install, GPU, model or Node is needed.
Extract the complete ZIP before running; opening index.html directly is not supported.

This browser includes 100 approved preview records each from CLEVR, EuroSAT and
PAIRS, their approved original media, and the approved CLEVR analysis overlay.
Those 300 examples, their filters, linked inspection, saved selections and selection export
work without internet access. Other catalogue entries describe access and coverage;
choosing an optional live Hugging Face preview or a source link requires internet.
This launcher does not download datasets or contact a model service.

These are previews of the pinned populations, not complete datasets or prevalence
estimates. Sampling declarations and provenance stay with the records. Computational
results are evidence for the included preview only, not scientific validation.
The complete Dataset Atlas v1 acceptance contract remains unfinished.

The code is MIT licensed (LICENSE). Dataset media and annotations keep their own
rights, source notices and attribution, shown in the browser and licenses/.
Only the previously approved CLEVR, EuroSAT and PAIRS examples are included.
This bundle grants no rights over other datasets and does not resolve the precise
historical releases or subsets used by the papers that cite them.

manifest.json records the exact bundled file sizes and SHA-256 hashes. Startup
checks all declared files and refuses missing, changed, linked or unknown files.
The manifest checks integrity relative to itself; it is not a digital signature.
Keep the publisher's ZIP checksum separately when checking provenance.
"""


def _files(directory: Path) -> list[Path]:
    sample_launcher._unlinked(directory)
    if not directory.is_dir():
        raise ValueError('Missing sample input directory')
    files = []
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink inputs are not allowed')
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Sample input contains a non-regular file')
        files.append(path)
        if len(files) > 10_000:
            raise ValueError('Sample input exceeds the file limit')
    return files


def _safe_input_name(name: str) -> None:
    sample_launcher._safe_name(name)
    parts = name.split('/')
    if any(part.startswith('.') or part in _FORBIDDEN_DIRS for part in parts) or Path(name).suffix.lower() in _FORBIDDEN_SUFFIXES:
        raise ValueError('Forbidden private sample input file')


def _site_name(name: str) -> None:
    _safe_input_name(name)
    parts = name.split('/')
    if len(parts) == 1:
        if name != 'index.html' and Path(name).suffix.lower() not in {'.ico', '.svg'}:
            raise ValueError('Unsafe sample site file')
    elif parts[0] not in {'assets', 'data', 'licenses'}:
        raise ValueError('Unsafe sample site directory')
    elif parts[0] == 'data' and not (len(parts) == 2 and parts[1] in _DATA_JSON) and not (len(parts) >= 4 and parts[1] == 'media' and parts[2] in _DATASETS):
        raise ValueError('Unsafe or unapproved sample data file')


def _coverage(contents: dict[str, bytes]) -> dict:
    try:
        catalogue = json.loads(contents['site/data/catalogue.json'])
        if not isinstance(catalogue, list):
            raise ValueError('Invalid sample catalogue')
        catalogue_ids = [row['id'] for row in catalogue]
        if len(catalogue_ids) != len(set(catalogue_ids)) or not set(_DATASETS).issubset(catalogue_ids):
            raise ValueError('Invalid sample catalogue identities')
        datasets = []
        all_media = set()
        for dataset_id in _DATASETS:
            pack = json.loads(contents[f'site/data/{dataset_id}.json'])
            dataset = pack['dataset']
            records = pack['records']
            if dataset['id'] != dataset_id or not dataset.get('release') or not dataset.get('snapshot_id'):
                raise ValueError('Sample dataset identity is incomplete')
            if pack.get('population_scope') != 'preview' or not pack.get('sampling') or len(records) != 100:
                raise ValueError('Sample must retain each complete 100-record approved preview')
            if len({row['id'] for row in records}) != 100:
                raise ValueError('Sample preview record identities are not unique')
            media = set()
            for record in records:
                for asset in record.get('assets', []):
                    uri = asset.get('uri')
                    if not uri:
                        continue
                    sample_launcher._safe_name(uri)
                    if not uri.startswith(f'data/media/{dataset_id}/'):
                        raise ValueError('Sample media must be a local approved dataset original')
                    name = 'site/' + uri
                    if name not in contents or hashlib.sha256(contents[name]).hexdigest() != asset.get('sha256'):
                        raise ValueError('Sample original media is missing or changed')
                    media.add(name)
            if len(media) != 100:
                raise ValueError('Sample must retain 100 original approved media files per dataset')
            all_media.update(media)
            datasets.append({'id': dataset_id, 'release': dataset['release'], 'snapshot_id': dataset['snapshot_id'],
                             'record_count': len(records), 'media_files': len(media)})
        if all_media != {name for name in contents if name.startswith('site/data/media/')}:
            raise ValueError('Sample includes unreferenced or unapproved media')
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError('Missing or invalid sample publication data') from exc
    return {'dataset_count': len(datasets), 'record_count': 300, 'media_files': len(all_media),
            'catalogue_count': len(catalogue), 'population_scope': 'preview', 'datasets': datasets}


def build_sample_bundle(site_dir: Path, output: Path, *, notices_dir: Path, license_path: Path,
                        max_bytes: int = 50_000_000) -> dict:
    """Create a deterministic ZIP; refuse overwrites and bound expanded bytes.

    The caller first creates a fresh static build using the normal publication
    validator. No records or artifacts are subset here, and no network is used.
    """
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError('Sample expanded byte budget must be positive')
    site_dir, notices_dir, license_path, output = (Path(path).absolute() for path in (site_dir, notices_dir, license_path, output))
    sample_launcher._unlinked(output)
    if os.path.lexists(output):
        raise ValueError('Sample bundle output already exists')
    if output.is_relative_to(site_dir) or output.is_relative_to(notices_dir):
        raise ValueError('Sample output must be outside its input directories')
    sources = {}
    for path in _files(site_dir):
        name = path.relative_to(site_dir).as_posix()
        _site_name(name)
        sources['site/' + name] = path
    notices = _files(notices_dir)
    if not notices:
        raise ValueError('Dataset notices are required for a sample bundle')
    for path in notices:
        name = path.relative_to(notices_dir).as_posix()
        _safe_input_name(name)
        sources['licenses/' + name] = path
    sample_launcher._unlinked(license_path)
    if not license_path.is_file() or not stat.S_ISREG(license_path.stat().st_mode):
        raise ValueError('Missing code LICENSE')
    sources['LICENSE'] = license_path
    launcher_path = Path(sample_launcher.__file__)
    sources['OPEN_ATLAS.py'] = launcher_path
    if len(sources) > 10_000 or sum(path.stat().st_size for path in sources.values()) + len(_README.encode()) > max_bytes:
        raise ValueError('Sample inputs exceed the expanded byte budget')
    contents = {'README.txt': _README.encode('utf-8')}
    remaining = max_bytes - len(contents['README.txt'])
    for name, path in sources.items():
        # A source that grows after the initial stat must not bypass the bound.
        with path.open('rb') as source:
            content = source.read(remaining + 1)
        if len(content) > remaining:
            raise ValueError('Sample inputs exceed the expanded byte budget')
        contents[name] = content
        remaining -= len(content)
    coverage = _coverage(contents)
    if 'site/index.html' not in contents:
        raise ValueError('Sample browser index.html is missing')
    if len({name.casefold() for name in contents}) != len(contents):
        raise ValueError('Sample filenames conflict on case-insensitive filesystems')
    manifest = {'schema_version': '1.0', 'kind': 'dataset-atlas-sample', 'expanded_budget_bytes': max_bytes,
                **coverage, 'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                                    for name, data in sorted(contents.items())}}
    contents['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    expanded_bytes = sum(len(data) for data in contents.values())
    if expanded_bytes > max_bytes:
        raise ValueError('Sample bundle exceeds the expanded byte budget')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.atlas-sample-', dir=output.parent) as staging:
        temporary = Path(staging) / 'sample.zip'
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, content in sorted(contents.items()):
                entry = zipfile.ZipInfo('dataset-atlas-sample/' + name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, content, compresslevel=6)
        archive_bytes = temporary.stat().st_size
        if archive_bytes > max_bytes:
            raise ValueError('Sample ZIP exceeds its byte budget')
        checksum = hashlib.sha256(temporary.read_bytes()).hexdigest()
        # Same-filesystem link is atomic and never replaces an existing path.
        os.link(temporary, output)
    return {'output': str(output), 'bytes': archive_bytes, 'expanded_bytes': expanded_bytes, 'sha256': checksum,
            'files': len(contents), **coverage}
