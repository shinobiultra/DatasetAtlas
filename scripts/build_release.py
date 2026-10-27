"""Build approved public data and the frontend, then the installable archives."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build_frontend(root: Path = ROOT):
    """Always validate approved inputs; ignored public/data is never an input."""
    from dataset_atlas.exports import build_publication

    report = build_publication(root / 'registry', root / 'examples/approved-packs',
                               root / 'apps/web/public', root / 'registry/publication.json')
    subprocess.run(['npm', 'ci'], cwd=root / 'apps/web', check=True)
    subprocess.run(['npm', 'run', 'build'], cwd=root / 'apps/web', check=True,
                   env={**os.environ, 'ATLAS_BASE': './'})
    return report


def build_release(root: Path = ROOT):
    build_frontend(root)
    target = root / 'src/dataset_atlas/web'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(root / 'apps/web/dist', target)
    # The installed package can create a workspace without a checkout.
    seed = root / 'src/dataset_atlas/catalogue_seed'
    if seed.exists():
        shutil.rmtree(seed)
    for name in ('registry', 'schemas'):
        shutil.copytree(root / name, seed / name)
    subprocess.run([sys.executable, '-m', 'build', '--installer', 'uv'], cwd=root, check=True)


if __name__ == '__main__':
    build_release()
