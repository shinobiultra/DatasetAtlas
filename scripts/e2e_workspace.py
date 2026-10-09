#!/usr/bin/env python3
"""Serve a throwaway workbench on an empty workspace, for browser tests of a colleague's first run.

It copies only the shipped catalogue and the built interface, writes small synthetic fixtures (clearly not
catalogue data) for the "add your own dataset" journey, and then serves in the foreground.
"""
import argparse
from pathlib import Path
import shutil
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def write_fixtures(fixtures: Path) -> None:
    folder = fixtures / 'sorted-shapes'
    for label, colour in (('red', (220, 40, 40)), ('green', (40, 180, 70)), ('blue', (40, 80, 220))):
        for i in range(4):
            (folder / label).mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (48, 32), colour).save(folder / label / f'{i}.png')
    table = fixtures / 'scored'
    (table / 'imgs').mkdir(parents=True, exist_ok=True)
    rows = ['file,score,group,note']
    for i in range(10):
        Image.new('RGB', (40, 40), (i * 25, 90, 160)).save(table / 'imgs' / f'{i}.png')
        rows.append(f'imgs/{i}.png,{i * 0.1:.1f},{"a" if i % 2 else "b"},{"" if i == 3 else "row " + str(i)}')
    (table / 'scored.csv').write_text('\n'.join(rows) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4188)
    parser.add_argument('--fixtures', type=Path, required=True, help='Directory to (re)create synthetic fixtures in')
    args = parser.parse_args()
    if args.fixtures.exists():
        shutil.rmtree(args.fixtures)
    write_fixtures(args.fixtures)
    workspace = Path(tempfile.mkdtemp(prefix='atlas-e2e-'))
    for name in ('registry', 'schemas'):
        shutil.copytree(ROOT / name, workspace / name)
    shutil.copytree(ROOT / 'apps/web/dist', workspace / 'apps/web/dist')
    from dataset_atlas.cli import main as atlas
    raise SystemExit(atlas(['--root', str(workspace), 'serve', '--port', str(args.port)]))


if __name__ == '__main__':
    main()
