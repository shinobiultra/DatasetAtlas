"""Check release archives for bundled public site and accidental private files.

Usage: python scripts/verify_distribution.py [dist-directory]
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import zipfile


FORBIDDEN_ROOTS = {"work", "registry", "reports", ".git", ".venv", "node_modules"}
FORBIDDEN_SUFFIXES = {".pdf", ".pem", ".key", ".pkl", ".pickle", ".joblib", ".sqlite", ".db"}
PRIVATE_MARKERS = (b"/home/" + b"bitwise/", b"-----BEGIN " + b"PRIVATE KEY-----")
MAX_SITE_BYTES = 200_000_000


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
                content = archive.extractfile(item).read()
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
        if len(seed_datasets) < 300 or "dataset_atlas/catalogue_seed/schemas/atlas.schema.json" not in members:
            raise ValueError(f"Wheel catalogue seed is missing or incomplete in {path.name}: {len(seed_datasets)} dataset entries")
    if site_bytes > MAX_SITE_BYTES:
        raise ValueError(f"Bundled site exceeds 200 MB in {path.name}: {site_bytes}")
    return {"archive": path.name, "files": len(members), "site_bytes": site_bytes, "approved_media_files": media_counts}


def main() -> int:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist")
    wheels = sorted(directory.glob("dataset_atlas-*.whl"))
    sdists = sorted(directory.glob("dataset_atlas-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Expected exactly one Dataset Atlas wheel and source archive")
    print(json.dumps({"wheel": inspect_archive(wheels[0], sdist=False), "sdist": inspect_archive(sdists[0], sdist=True)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
