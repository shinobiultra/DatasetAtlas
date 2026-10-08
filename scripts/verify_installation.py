#!/usr/bin/env python3
"""Install the built wheel into a fresh base-only virtual environment outside the checkout and exercise it over real HTTP.

Follows docs/publication.md. Nothing from the checkout is importable: the environment gets only the wheel and its declared base dependencies,
`atlas init` creates a workspace from the catalogue embedded in the wheel, `atlas serve` starts from that workspace, and the script requests the
bundled interface, the static catalogue, an approved preview pack, its media and `/api/v1/capabilities`. It also asserts that no optional model
package was installed. No dataset is fetched and no model is run.

    python scripts/verify_installation.py [--dist dist] [--output reports/installation-verification.json]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIONAL = ['torch', 'torchvision', 'transformers', 'nudenet', 'sklearn', 'umap', 'lancedb', 'sentence_transformers']


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def get(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.status, response.headers.get('content-type', ''), response.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist', help='directory holding the built wheel and sdist')
    parser.add_argument('--wheel', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/installation-verification.json')
    args = parser.parse_args()
    wheel = args.wheel or max(args.dist.glob('dataset_atlas-*.whl'), key=lambda p: p.stat().st_mtime)
    sdist = max(args.dist.glob('dataset_atlas-*.tar.gz'), key=lambda p: p.stat().st_mtime)
    inspection = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_distribution.py'), str(args.dist)], capture_output=True, text=True)
    receipt = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'failed', 'wheel': wheel.name, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
               'release_archives': {wheel.name: wheel.stat().st_size, sdist.name: sdist.stat().st_size},
               'archive_inspection': {'passed': inspection.returncode == 0, 'output': (inspection.stdout + inspection.stderr)[-600:]},
               'scope': 'Fresh base-only virtual environment outside the checkout; real HTTP requests to the installed server; no dataset fetched, no model run.'}
    if inspection.returncode != 0:
        args.output.write_text(json.dumps(receipt, indent=2) + '\n')
        print(inspection.stdout + inspection.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix='atlas-install-') as scratch:
        scratch_path = Path(scratch)
        venv = scratch_path / 'venv'
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
        python = venv / 'bin/python'
        subprocess.run([str(python), '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', str(wheel)], check=True, cwd=scratch)
        installed = subprocess.run([str(python), '-m', 'pip', 'freeze'], capture_output=True, text=True, cwd=scratch).stdout.splitlines()
        present = [name for name in OPTIONAL if subprocess.run([str(python), '-c', f'import importlib.util,sys;sys.exit(0 if importlib.util.find_spec("{name}") else 1)'], cwd=scratch).returncode == 0]
        receipt.update(python=sys.version.split()[0], installed_packages=len(installed), optional_model_packages_present=present)
        workspace = scratch_path / 'workspace'
        env = {**os.environ, 'PYTHONPATH': ''}
        init = subprocess.run([str(venv / 'bin/atlas'), 'init', str(workspace)], capture_output=True, text=True, cwd=scratch, env=env)
        if init.returncode != 0:
            receipt['error'] = init.stderr[-400:]
            args.output.write_text(json.dumps(receipt, indent=2) + '\n')
            return 1
        catalogue = len(list((workspace / 'registry/datasets').glob('*.yaml')))
        port = free_port()
        server = subprocess.Popen([str(venv / 'bin/atlas'), '--root', str(workspace), 'serve', '--port', str(port)], cwd=scratch, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        base = f'http://127.0.0.1:{port}'
        try:
            for _ in range(60):
                try:
                    get(base + '/api/v1/capabilities')
                    break
                except Exception:
                    if server.poll() is not None:
                        raise RuntimeError('server exited: ' + (server.stderr.read() if server.stderr else ''))
                    time.sleep(0.5)
            routes = {}
            status, kind, body = get(base + '/')
            routes['/'] = {'status': status, 'content_type': kind, 'has_script': b'<script' in body}
            status, kind, body = get(base + '/api/v1/capabilities')
            capabilities = json.loads(body)
            routes['/api/v1/capabilities'] = {'status': status, 'mode': capabilities.get('mode'), 'operations': len(capabilities.get('operations', []))}
            status, _, body = get(base + '/data/catalogue.json')
            entries = json.loads(body)
            routes['/data/catalogue.json'] = {'status': status, 'entries': len(entries), 'any_adapter_config': any(e.get('adapter_config') for e in entries)}
            approved = sorted(e['id'] for e in entries if e.get('coverage', {}).get('publication') == 'approved')
            media_checked = 0
            for dataset_id in approved:
                status, _, body = get(base + f'/data/{dataset_id}.json')
                pack = json.loads(body)
                routes[f'/data/{dataset_id}.json'] = {'status': status, 'records': len(pack.get('records', []))}
                first = next((a['uri'] for r in pack.get('records', []) for a in r.get('assets', []) if a.get('uri')), None)
                if first:
                    status, kind, body = get(base + '/' + first.lstrip('/'))
                    routes['/' + first.lstrip('/')] = {'status': status, 'content_type': kind, 'bytes': len(body)}
                    media_checked += 1
            ok = (all(r.get('status') == 200 for r in routes.values()) and capabilities.get('mode') in {'workbench', 'static'} and not present
                  and routes['/']['has_script'] and not routes['/data/catalogue.json']['any_adapter_config'] and len(approved) >= 3 and media_checked >= 3)
            receipt.update(fresh_catalogue_entries=catalogue, approved_static_previews=approved, http_routes=routes, status='passed' if ok else 'failed')
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('status', 'python', 'optional_model_packages_present', 'fresh_catalogue_entries', 'approved_static_previews')}, indent=1))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
