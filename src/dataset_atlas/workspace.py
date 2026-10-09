"""Create or refresh a workspace from the catalogue that ships inside the installed package.

An installed wheel carries the tool and a snapshot of the catalogue (`registry/` and `schemas/`), but no
workspace. `atlas init` makes one. Everything a researcher creates lives outside the shipped catalogue —
fetched data in `work/`, their own datasets and settings in `local-config/` — so refreshing the catalogue
can never touch it.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import shutil

SEED = Path(__file__).resolve().parent / 'catalogue_seed'
OWNED = ('registry', 'schemas')


def seed_available(seed: Path = SEED) -> bool:
    return (seed / 'registry/datasets').is_dir()


def initialised(target: Path) -> bool:
    return (Path(target) / 'registry/datasets').is_dir()


def init_workspace(target: Path, *, update: bool = False, seed: Path = SEED) -> dict:
    target = Path(target).expanduser().resolve()
    if not seed_available(seed):
        raise ValueError('This installation carries no catalogue. Run Atlas from a repository checkout, or install a release wheel built with scripts/build_release.py.')
    existing = initialised(target)
    if existing and not update:
        raise ValueError(f'{target} is already a workspace. Use --update to replace its shipped catalogue with this version; your datasets, fetched data and settings are not touched.')
    if update and not existing:
        raise ValueError(f'{target} is not a workspace yet; run init without --update.')
    target.mkdir(parents=True, exist_ok=True)
    replaced = []
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for name in OWNED:
        source, destination = seed / name, target / name
        if not source.is_dir():
            continue
        staging = target / f'.{name}.incoming'
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(source, staging)
        if destination.exists():
            # Keep the previous catalogue until the new one is in place, then drop it: it is shipped data, not the user's.
            retired = target / f'.{name}.retired-{stamp}'
            destination.rename(retired)
            staging.rename(destination)
            shutil.rmtree(retired)
            replaced.append(name)
        else:
            staging.rename(destination)
    for name in ('work', 'local-config'):
        (target / name).mkdir(exist_ok=True)
    datasets = len(list((target / 'registry/datasets').glob('*.yaml')))
    return {'workspace': str(target), 'datasets': datasets, 'replaced': replaced, 'updated': update}
