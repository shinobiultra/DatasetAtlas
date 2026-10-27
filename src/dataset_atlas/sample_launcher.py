"""Standard-library-only launcher, also copied into portable sample bundles."""

from __future__ import annotations

import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import stat
import sys
from urllib.parse import unquote, urlsplit
import webbrowser


def _safe_name(name: str) -> None:
    if not isinstance(name, str) or not name or name.startswith('/') or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('Unsafe bundle filename')
    if any(part in {'', '.', '..'} for part in name.split('/')):
        raise ValueError('Unsafe bundle filename')


def _unlinked(path: Path) -> None:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('Linked paths are not allowed')


def verify_bundle(directory: Path) -> dict:
    """Check every declared byte and reject extra files before opening a server.

    The manifest detects changes relative to the bundled manifest; it is not an
    independent signature or a new dataset publication approval.
    """
    directory = Path(directory).absolute()
    _unlinked(directory)
    manifest_path = directory / 'manifest.json'
    _unlinked(manifest_path)
    if not manifest_path.is_file() or manifest_path.stat().st_size > 4_000_000:
        raise ValueError('Missing or oversized bundle manifest')
    manifest = json.loads(manifest_path.read_bytes())
    if not isinstance(manifest, dict) or manifest.get('schema_version') != '1.0' or manifest.get('kind') != 'dataset-atlas-sample':
        raise ValueError('Unsupported sample bundle manifest')
    files = manifest.get('files')
    budget = manifest.get('expanded_budget_bytes')
    if not isinstance(files, dict) or not files or len(files) > 10_000 or type(budget) is not int or budget <= 0:
        raise ValueError('Invalid bundle file list or budget')
    required = {'OPEN_ATLAS.py', 'README.txt', 'LICENSE', 'site/index.html', 'site/data/catalogue.json',
                'site/data/clevr.json', 'site/data/eurosat.json', 'site/data/pairs.json'}
    if not required.issubset(files) or 'manifest.json' in files:
        raise ValueError('Bundle manifest is incomplete')
    total = manifest_path.stat().st_size
    for name, info in files.items():
        _safe_name(name)
        if not isinstance(info, dict) or set(info) != {'bytes', 'sha256'} or type(info['bytes']) is not int or info['bytes'] < 0:
            raise ValueError('Invalid bundle file metadata')
        if not isinstance(info['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', info['sha256']):
            raise ValueError('Invalid bundle file checksum')
        total += info['bytes']
    if total > budget or len({name.casefold() for name in files}) != len(files):
        raise ValueError('Bundle exceeds its expanded budget or has conflicting names')
    actual = set()
    directories = {parent.as_posix() for name in files for parent in Path(name).parents}
    for path in directory.rglob('*'):
        if path.is_symlink():
            raise ValueError('Linked bundle members are not allowed')
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            relative = path.relative_to(directory)
            if relative.as_posix() not in directories and not (path.name == '__pycache__' and relative.parent.as_posix() in directories):
                raise ValueError('Bundle contains an unknown directory')
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Bundle contains a non-regular file')
        name = path.relative_to(directory).as_posix()
        # Direct script execution creates no local cache, but importing the
        # launcher later may do so. Only conventional Python bytecode is ignored.
        if '__pycache__' in path.relative_to(directory).parts and path.suffix == '.pyc':
            continue
        actual.add(name)
        if len(actual) > 10_001:
            raise ValueError('Bundle contains too many files')
    if actual != set(files) | {'manifest.json'}:
        raise ValueError('Bundle contains missing or unknown files')
    for name, info in files.items():
        path = directory / name
        if path.stat().st_size != info['bytes']:
            raise ValueError(f'Bundle file size changed: {name}')
        digest = hashlib.sha256()
        with path.open('rb') as source:
            while chunk := source.read(1_048_576):
                digest.update(chunk)
        if digest.hexdigest() != info['sha256']:
            raise ValueError(f'Bundle checksum changed: {name}')
    return manifest


class _SiteHandler(SimpleHTTPRequestHandler):
    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        address = self.server.server_address
        if not isinstance(address, tuple) or len(address) < 2:
            self.send_error(403, 'Unsupported server address')
            return False
        port = address[1]
        hosts = self.headers.get_all('Host', [])
        if len(hosts) != 1 or hosts[0] not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            self.send_error(403, 'Unapproved Host header')
            return False
        return True

    def _allowed(self) -> bool:
        try:
            name = unquote(urlsplit(self.path).path).lstrip('/')
            if name:
                _safe_name(name.rstrip('/'))
            target = Path(self.directory) / name
            _unlinked(target)
            root = Path(self.directory).resolve()
            if not target.resolve().is_relative_to(root):
                return False
            if target.is_dir():
                target = target / 'index.html'
                _unlinked(target)
            return target.is_file()
        except (ValueError, OSError):
            return False

    def do_GET(self):
        if not self._allowed():
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._allowed():
            self.send_error(404)
            return
        super().do_HEAD()


def serve(directory: Path, port: int = 8767, open_browser: bool = True) -> None:
    """Serve on a stable loopback origin; explicit port 0 picks a temporary port."""
    directory = Path(directory).absolute()
    _unlinked(directory)
    _unlinked(directory / 'index.html')
    if not (directory / 'index.html').is_file():
        raise ValueError('Static browser index.html is missing')
    if type(port) is not int or not 0 <= port <= 65_535:
        raise ValueError('Port must be between 0 and 65535')
    handler = partial(_SiteHandler, directory=str(directory))
    with ThreadingHTTPServer(('127.0.0.1', port), handler) as server:
        url = f'http://127.0.0.1:{server.server_address[1]}/'
        print(f'Dataset Atlas sample: {url}', flush=True)
        if open_browser:
            try:
                webbrowser.open(url)
            except webbrowser.Error:
                pass  # The printed address also works on hosts without a browser.
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Open the Dataset Atlas sample browser locally; no dependencies or dataset downloads.')
    parser.add_argument('--site', type=Path, help='Explicit local static build directory, without a bundle manifest')
    parser.add_argument('--check', action='store_true', help='Verify the bundle and exit without starting a server')
    parser.add_argument('--port', type=int, default=8767, help='Stable loopback port (default 8767); 0 picks a temporary port')
    parser.add_argument('--no-browser', action='store_true', help='Print the local address without opening a browser')
    args = parser.parse_args(argv)
    try:
        if args.site is not None:
            if args.check:
                raise ValueError('--check requires a sample bundle manifest; omit --site')
            directory = args.site
        else:
            root = Path(__file__).absolute().parent
            manifest = verify_bundle(root)
            if args.check:
                print(f"Verified sample bundle: {manifest['dataset_count']} datasets, {manifest['record_count']} preview records.")
                return 0
            directory = root / 'site'
        serve(directory, port=args.port, open_browser=not args.no_browser)
        return 0
    except (ValueError, OSError) as exc:
        print(f'Dataset Atlas: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
