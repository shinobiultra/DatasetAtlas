#!/usr/bin/env python3
"""Exercise fresh clone startup or the dependency-free portable sample over HTTP."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

from verify_distribution import inspect_sample_bundle

ROOT = Path(__file__).resolve().parents[1]
_SOURCE_FILES = {'start.sh', 'pyproject.toml', 'uv.lock', 'LICENSE', 'README.md',
                 'scripts/build_release.py', 'scripts/build_sample_bundle.py',
                 'apps/web/index.html', 'apps/web/package.json', 'apps/web/package-lock.json',
                 'apps/web/tsconfig.json', 'apps/web/vite.config.ts',
                 'registry/publication.json', 'registry/live-previews.yaml'}
_SOURCE_TREES = ('src/dataset_atlas/', 'apps/web/src/', 'apps/web/public/',
                 'examples/approved-packs/', 'examples/public-schema/', 'registry/datasets/',
                 'registry/recipes/', 'registry/papers/', 'licenses/')
_GENERATED_TREES = ('src/dataset_atlas/web/', 'src/dataset_atlas/catalogue_seed/',
                    'apps/web/public/data/')


def copy_source_inputs(root: Path, destination: Path) -> dict:
    """Copy tracked startup inputs, without borrowing ignored or generated state.

    Read current file bytes so staged and unstaged fixes are tested together.
    The receipt fingerprints the exact copy used by the probe; Git metadata,
    private workspaces and optional prepared/model content are never copied.
    """
    root, destination = root.resolve(), destination.absolute()
    if destination.exists() or destination.resolve().is_relative_to(root):
        raise ValueError('Clean source destination must be new and outside the checkout')
    tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached'],
                             check=True, capture_output=True).stdout.split(b'\0')
    selected = []
    for raw in tracked:
        if not raw:
            continue
        name = os.fsdecode(raw)
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe tracked source path')
        if any(part in {'.git', '.venv', 'node_modules', '__pycache__', 'work', 'dist', 'local-config'} for part in relative.parts):
            continue
        if name.startswith(_GENERATED_TREES) or not (name in _SOURCE_FILES or name.startswith(_SOURCE_TREES)):
            continue
        source = root / relative
        if any(part.is_symlink() for part in (source, *source.parents)) or not source.is_file():
            raise ValueError(f'Tracked startup input is missing or linked: {name}')
        selected.append((name, source))
    if _SOURCE_FILES - {name for name, _ in selected}:
        raise ValueError('Tracked startup files are incomplete')
    destination.mkdir(parents=True)
    fingerprint = hashlib.sha256()
    size = 0
    for name, source in sorted(selected):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        with target.open('rb') as content:
            digest = hashlib.file_digest(content, 'sha256').hexdigest()
        fingerprint.update(name.encode() + b'\0' + digest.encode() + b'\n')
        size += target.stat().st_size
    return {'source_input_files': len(selected), 'source_input_bytes': size,
            'source_input_sha256': fingerprint.hexdigest()}


def verify_http(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> dict:
    """Start the actual launcher, inspect three original assets, and always stop it."""
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    captured = bytearray()
    try:
        assert process.stdout is not None
        deadline = time.monotonic() + 180
        with selectors.DefaultSelector() as readable:
            readable.register(process.stdout, selectors.EVENT_READ)
            while True:
                if time.monotonic() >= deadline or process.poll() is not None:
                    raise RuntimeError('Sample startup failed or timed out: ' + captured[-2000:].decode(errors='replace'))
                if not readable.select(timeout=0.5):
                    continue
                chunk = os.read(process.stdout.fileno(), 65_536)
                captured.extend(chunk)
                found = re.search(rb'Dataset Atlas sample: (http://127\.0\.0\.1:\d+/)', captured)
                if found:
                    base = found.group(1).decode()
                    break
        with urllib.request.urlopen(base, timeout=10) as response:
            if response.status != 200 or b'<script' not in response.read():
                raise ValueError('Sample interface did not load')
        counts = {}
        for dataset_id in ('clevr', 'eurosat', 'pairs'):
            with urllib.request.urlopen(base + f'data/{dataset_id}.json', timeout=10) as response:
                pack = json.load(response)
            if pack.get('population_scope') != 'preview' or len(pack['records']) != 100:
                raise ValueError('Sample preview scope changed')
            asset = next(asset for record in pack['records'] for asset in record.get('assets', []) if asset.get('uri'))
            with urllib.request.urlopen(base + asset['uri'], timeout=10) as response:
                if hashlib.sha256(response.read()).hexdigest() != asset['sha256']:
                    raise ValueError('Sample original media checksum changed')
            counts[dataset_id] = len(pack['records'])
        try:
            urllib.request.urlopen(urllib.request.Request(base, headers={'Host': 'attacker.invalid'}), timeout=10)
        except urllib.error.HTTPError as refused:
            if refused.code not in {400, 403}:
                raise
        else:
            raise ValueError('Sample server accepted an unapproved Host')
        return {'status': 'passed', 'preview_records': counts, 'original_assets_checked': 3, 'host_validation': 'passed'}
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        if process.stdout is not None:
            process.stdout.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source', action='store_true', help='Copy tracked startup inputs into a clean temporary tree and run start.sh with fresh Python and Node dependencies')
    mode.add_argument('--bundle', type=Path, help='Verify and launch this portable ZIP without package dependencies')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='atlas-sample-startup-') as scratch:
        directory = Path(scratch)
        if args.source:
            source = directory / 'source'
            inputs = copy_source_inputs(ROOT, source)
            env = {**os.environ, 'UV_PROJECT_ENVIRONMENT': str(source / '.venv'), 'PYTHONPATH': ''}
            result = verify_http(['bash', './start.sh', '--no-open', '--port', '0'], cwd=source, env=env)
            result.update(inputs)
            result['mode'] = 'fresh-source'
        else:
            inspect_sample_bundle(args.bundle)
            with zipfile.ZipFile(args.bundle) as archive:
                archive.extractall(directory)
            result = verify_http([sys.executable, '-I', str(directory / 'dataset-atlas-sample/OPEN_ATLAS.py'), '--no-browser', '--port', '0'], cwd=directory)
            result['mode'] = 'portable-bundle'
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
