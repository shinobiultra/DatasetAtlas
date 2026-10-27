"""Check release archives for bundled public site and accidental private files.

Usage: python scripts/verify_distribution.py [dist-directory]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile


FORBIDDEN_ROOTS = {"work", "registry", "reports", ".git", ".venv", "node_modules"}
FORBIDDEN_SUFFIXES = {".pdf", ".pem", ".key", ".pkl", ".pickle", ".joblib", ".sqlite", ".db"}
PRIVATE_MARKERS = (b"/home/" + b"bitwise/", b"-----BEGIN " + b"PRIVATE KEY-----")
MAX_SITE_BYTES = 200_000_000
ROOT = Path(__file__).resolve().parents[1]


def release_archives(directory: Path, *, wheel: Path | None = None, version: str | None = None) -> tuple[Path, Path]:
    """Select this source version, preserving older archives without testing them by mistake."""
    if version is None:
        version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    if not re.fullmatch(r'[A-Za-z0-9.!+]+', version):
        raise ValueError('Unsafe release version')
    expected = f'dataset_atlas-{version}-py3-none-any.whl'
    wheel = Path(wheel) if wheel is not None else Path(directory) / expected
    if wheel.name != expected:
        raise ValueError(f'Explicit wheel does not match current release version {version}')
    sdist = Path(directory) / f'dataset_atlas-{version}.tar.gz'
    if not wheel.is_file() or not sdist.is_file():
        raise ValueError(f'Missing current release wheel or source archive for version {version}')
    return wheel.absolute(), sdist.absolute()


def inspect_sample_bundle(path: Path, *, max_bytes: int = 50_000_000) -> dict:
    """Check its external checksum, ZIP paths/budget, manifest and standalone launcher."""
    from dataset_atlas.sample_launcher import _safe_name, verify_bundle

    path = Path(path).absolute()
    if path.stat().st_size > max_bytes:
        raise ValueError('Sample ZIP exceeds its byte budget')
    checksum = path.with_name(path.name + '.sha256').read_text().strip()
    with path.open('rb') as source:
        actual = hashlib.file_digest(source, 'sha256').hexdigest()
    if checksum != f'{actual}  {path.name}':
        raise ValueError('Sample ZIP checksum mismatch')
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix='atlas-sample-verify-') as scratch:
        members = archive.infolist()
        if not members or len(members) > 10_001 or sum(item.file_size for item in members) > max_bytes:
            raise ValueError('Sample ZIP exceeds its expanded byte budget')
        seen = set()
        for member in members:
            _safe_name(member.filename)
            parts = member.filename.split('/')
            if len(parts) < 2 or parts[0] != 'dataset-atlas-sample':
                raise ValueError('Unexpected sample ZIP root')
            if member.filename.casefold() in seen or stat.S_IFMT(member.external_attr >> 16) not in {0, stat.S_IFREG}:
                raise ValueError('Duplicate or non-regular sample ZIP member')
            seen.add(member.filename.casefold())
        archive.extractall(scratch)
        bundle = Path(scratch) / 'dataset-atlas-sample'
        manifest = verify_bundle(bundle)
        subprocess.run([sys.executable, '-I', str(bundle / 'OPEN_ATLAS.py'), '--check'],
                       cwd=scratch, check=True, capture_output=True, text=True, timeout=30)
        if (manifest.get('dataset_count'), manifest.get('record_count'), manifest.get('media_files')) != (3, 300, 300):
            raise ValueError('Sample publication scope differs from the approved previews')
        return {'archive': path.name, 'sha256': actual, 'bytes': path.stat().st_size,
                'files': len(members), 'record_count': manifest['record_count'], 'media_files': manifest['media_files']}


def _check_path(raw: str, *, sdist: bool) -> str:
    parts = PurePosixPath(raw).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Unsafe archive path: {raw}")
    relative = parts[1:] if sdist else parts
    if not relative:
        return ""
    if relative[0] in FORBIDDEN_ROOTS or "node_modules" in relative:
        raise ValueError(f"Private directory in archive: {raw}")
    if any(part.startswith(".env") for part in relative) or PurePosixPath(raw).suffix.lower() in FORBIDDEN_SUFFIXES:
        raise ValueError(f"Private or executable artifact in archive: {raw}")
    return "/".join(relative)


def _check_contents(name: str, content: bytes) -> None:
    for marker in PRIVATE_MARKERS:
        if marker in content:
            raise ValueError(f"Private marker in archive entry: {name}")
    # A static JSON file must have no local or registry-only metadata.
    if re.search(r"(?:^|/)web/data/[^/]+\.json$", name):
        value = json.loads(content)
        datasets = value if isinstance(value, list) else [value.get("dataset", {})]
        for dataset in datasets:
            if dataset.get("adapter_config") or dataset.get("evidence"):
                raise ValueError(f"Private dataset metadata in archive entry: {name}")


def inspect_archive(path: Path, *, sdist: bool) -> dict:
    members: dict[str, int] = {}
    site_bytes = 0
    if sdist:
        with tarfile.open(path, "r:gz") as archive:
            for item in archive:
                if item.issym() or item.islnk() or not (item.isfile() or item.isdir()):
                    raise ValueError(f"Unsafe source archive member: {item.name}")
                name = _check_path(item.name, sdist=True)
                if not item.isfile():
                    continue
                source = archive.extractfile(item)
                if source is None:
                    raise ValueError(f'Unreadable source archive member: {item.name}')
                with source:
                    content = source.read()
                _check_contents(name, content)
                members[name] = len(content)
                if name.startswith("src/dataset_atlas/web/"):
                    site_bytes += len(content)
    else:
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f"Unsafe wheel link: {item.filename}")
                name = _check_path(item.filename, sdist=False)
                if item.is_dir():
                    continue
                content = archive.read(item)
                _check_contents(name, content)
                members[name] = len(content)
                if name.startswith("dataset_atlas/web/"):
                    site_bytes += len(content)
    prefix = "src/dataset_atlas/web/" if sdist else "dataset_atlas/web/"
    required = {prefix + "index.html", prefix + "data/catalogue.json", prefix + "data/clevr.json", prefix + "data/eurosat.json", prefix + "data/pairs.json", prefix + "licenses/eurosat-MIT.txt"}
    if sdist:
        required.update({'start.sh', 'scripts/build_sample_bundle.py'})
    missing = required - members.keys()
    if missing:
        raise ValueError(f"Missing bundled public site entries in {path.name}: {sorted(missing)}")
    suffixes = {"clevr": ".png", "eurosat": ".jpg", "pairs": ".png"}
    media_counts = {
        dataset_id: sum(name.startswith(prefix + f"data/media/{dataset_id}/") and name.endswith(suffix) for name in members)
        for dataset_id, suffix in suffixes.items()
    }
    if media_counts != {"clevr": 100, "eurosat": 100, "pairs": 100}:
        raise ValueError(f"Approved media count differs in {path.name}: {media_counts}")
    # The wheel must be able to create a workspace: it carries the catalogue, and the catalogue is clean.
    if not sdist:
        seed_datasets = [name for name in members if name.startswith("dataset_atlas/catalogue_seed/registry/datasets/") and name.endswith(".yaml")]
        expected = len(list((Path(__file__).resolve().parents[1] / "registry/datasets").glob("*.yaml")))  # the seed is a copy of the checkout registry
        if len(seed_datasets) != expected or "dataset_atlas/catalogue_seed/schemas/atlas.schema.json" not in members:
            raise ValueError(f"Wheel catalogue seed is missing or incomplete in {path.name}: {len(seed_datasets)} dataset entries")
    if site_bytes > MAX_SITE_BYTES:
        raise ValueError(f"Bundled site exceeds 200 MB in {path.name}: {site_bytes}")
    return {"archive": path.name, "files": len(members), "site_bytes": site_bytes, "approved_media_files": media_counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=ROOT / 'dist')
    parser.add_argument('--wheel', type=Path, help='Explicit wheel, required to match the current project version')
    parser.add_argument('--sample', type=Path, help='Also verify the portable ZIP and its adjacent .sha256')
    args = parser.parse_args()
    wheel, sdist = release_archives(args.directory, wheel=args.wheel)
    result = {'wheel': inspect_archive(wheel, sdist=False), 'sdist': inspect_archive(sdist, sdist=True)}
    if args.sample is not None:
        result['sample'] = inspect_sample_bundle(args.sample)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
