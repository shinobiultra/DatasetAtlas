"""Install the pinned public model weights the analysis processors need, and configure the processors to use them.

Each `registry/models/*.yaml` entry with an `install:` block lists exact files (URL, byte length, SHA-256) and the processor
configuration that uses them. Nothing downloads without an explicit plan; every file is verified against its SHA-256 before it
is placed in `work/models/`, and a file already present with the right checksum is never fetched again. Weights are public
third-party artifacts: Atlas records their provenance but does not redistribute them.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import yaml

HF_HOSTS = ['huggingface.co', 'cdn-lfs.huggingface.co', 'cdn-lfs-us-1.huggingface.co', 'cdn-lfs-eu-1.huggingface.co',
            'cas-bridge.xethub.hf.co', 'us.aws.cdn.hf.co', 'eu.aws.cdn.hf.co']
MAX_FILE_BYTES = 5_000_000_000
SMALL_VERIFY_BYTES = 200_000_000


def catalogue(root: Path) -> list[dict]:
    entries = []
    for path in sorted((Path(root) / 'registry/models').glob('*.yaml')):
        entry = yaml.safe_load(path.read_text())
        if entry.get('install'):
            entries.append({'key': path.stem, **entry})
    return entries


def _files(root: Path, entry: dict) -> list[dict]:
    install = entry['install']
    base = Path(root) / install['dir']
    if install.get('kind') == 'package':
        return [{'path': install['path'], 'destination': base / install['path'], 'bytes': install['bytes'], 'sha256': install['sha256'], 'package': install}]
    for item in install['files']:
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_][A-Za-z0-9_.\-]*)*', item['path']):
            raise ValueError(f"Unsafe model file path: {item['path']!r}")
        if not 0 < item['bytes'] <= MAX_FILE_BYTES or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']):
            raise ValueError(f"Model file needs a size within limits and a SHA-256: {item['path']}")
    return [{**item, 'destination': base / item['path']} for item in install['files']]


def _sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _present(item: dict, verify: bool) -> bool:
    path = item['destination']
    if not path.is_file() or path.stat().st_size != item['bytes']:
        return False
    return _sha256(path) == item['sha256'] if verify or item['bytes'] <= SMALL_VERIFY_BYTES else True


def _placeholders(entry: dict, root: Path) -> dict:
    install = entry['install']
    base = (Path(root) / install['dir']).resolve()
    return {'{dir}': str(base), '{file}': str(base / install.get('path', ''))} if install.get('kind') == 'package' else {'{dir}': str(base)}


def processor_config(root: Path, entry: dict) -> dict:
    replacements = _placeholders(entry, root)
    def fill(value):
        if isinstance(value, str):
            for token, text in replacements.items():
                value = value.replace(token, text)
        return value
    return {processor: {key: fill(value) for key, value in config.items()} for processor, config in entry['install'].get('processors', {}).items()}


def configured(root: Path, entry: dict) -> bool:
    path = Path(root) / 'local-config/recipes.json'
    saved = json.loads(path.read_text()) if path.is_file() else {}
    return all(processor in saved for processor in entry['install'].get('processors', {}))


def status(root: Path, verify: bool = False) -> list[dict]:
    rows = []
    for entry in catalogue(root):
        files = _files(root, entry)
        present = [_present(item, verify) for item in files]
        rows.append({'model': entry['key'], 'id': entry.get('id'), 'bytes': sum(item['bytes'] for item in files), 'installed': all(present),
                     'files_present': sum(present), 'files': len(files), 'configured': configured(root, entry), 'verified': verify})
    return rows


def plan(root: Path, models: list[str] | None = None) -> list[dict]:
    chosen = [entry for entry in catalogue(root) if not models or entry['key'] in models]
    unknown = set(models or []) - {entry['key'] for entry in chosen}
    if unknown:
        raise KeyError(f"Unknown model: {', '.join(sorted(unknown))}")
    rows = []
    for entry in chosen:
        files = _files(root, entry)
        missing = [item for item in files if not _present(item, False)]
        rows.append({'model': entry['key'], 'id': entry.get('id'), 'source': entry.get('source'), 'files_missing': len(missing),
                     'download_bytes': sum(item['bytes'] for item in missing if 'package' not in item), 'entry': entry, 'missing': missing})
    return rows


def _place(root: Path, item: dict, cache, fetcher) -> None:
    destination = item['destination']
    destination.parent.mkdir(parents=True, exist_ok=True)
    if 'package' in item:
        import importlib.util
        spec = importlib.util.find_spec(item['package']['package'])
        if spec is None or not spec.submodule_search_locations:
            raise ValueError(f"Install the {item['package']['package']} package (the `vision` extra) to copy its bundled model.")
        source = Path(next(iter(spec.submodule_search_locations))) / item['package']['resource']
        if not source.is_file():
            raise ValueError(f"The installed {item['package']['package']} does not bundle {item['package']['resource']}")
    else:
        from dataset_atlas.storage import CacheIdentity
        source = fetcher.fetch(item['url'], cache, CacheIdentity(item['sha256'], item['path'], 'model-file'), expected_sha256=item['sha256'], byte_budget=item['bytes'])
    if _sha256(source) != item['sha256']:
        raise ValueError(f"{item['path']} does not match its pinned SHA-256; refusing to install it")
    staged = destination.with_name(destination.name + f'.{os.getpid()}.part')
    try:
        try:
            os.link(source, staged)  # a cached download and its installed copy share storage
        except OSError:
            shutil.copy2(source, staged)
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)


def install(root: Path, models: list[str] | None = None, *, execute: bool = False, max_download_bytes: int = 3_000_000_000,
            reconfigure: bool = False, log=lambda message: None) -> dict:
    root = Path(root).resolve()
    rows = plan(root, models)
    total = sum(row['download_bytes'] for row in rows)
    report = {'executed': execute, 'download_bytes': total, 'max_download_bytes': max_download_bytes, 'models': []}
    if total > max_download_bytes:
        raise ValueError(f'These models need {total:,} bytes but the limit is {max_download_bytes:,}; raise --max-download-bytes or choose fewer models.')
    cache = fetcher = None
    if execute and total:
        from dataset_atlas.storage import BoundedCache, HttpsFetcher
        cache = BoundedCache(root / 'work/download-cache', max_bytes=max(item['bytes'] for row in rows for item in row['missing']) + 1_000_000)
        fetcher = HttpsFetcher(HF_HOSTS + ['download.pytorch.org'], timeout=60, max_bytes=MAX_FILE_BYTES)
    for row in rows:
        entry = {'model': row['model'], 'files_missing': row['files_missing'], 'download_bytes': row['download_bytes']}
        if execute:
            for item in row['missing']:
                log(f"fetching {row['model']}/{item['path']} ({item['bytes']:,} bytes)")
                _place(root, item, cache, fetcher)
            if not all(_present(item, True) for item in _files(root, row['entry'])):
                raise ValueError(f"{row['model']} is not completely installed after fetching")
            entry['installed'] = True
            entry['configured'] = _configure(root, row['entry'], reconfigure)
        report['models'].append(entry)
    return report


def _configure(root: Path, entry: dict, reconfigure: bool) -> list[str]:
    """Point the processors at the installed files without overriding a researcher's own settings."""
    path = root / 'local-config/recipes.json'
    saved = json.loads(path.read_text()) if path.is_file() else {}
    written = []
    for processor, config in processor_config(root, entry).items():
        if processor not in saved or reconfigure:
            saved[processor] = config
            written.append(processor)
    if written:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_text(json.dumps(saved, indent=2) + '\n')
        temporary.replace(path)
    return written
