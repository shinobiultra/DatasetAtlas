#!/usr/bin/env python3
"""Fill an empty `modalities` list from what a catalogue entry's own prepared preview actually contains.

Only entries with a prepared preview pack and no declared modalities are touched. A modality is listed when at least one preview record has an
asset of that kind (image, audio, video, model3d) or text content (text, question, choices or a conversation). Nothing is inferred from names or
descriptions, tasks are left alone, and an entry without a pack keeps 'Modality unknown' rather than receive a guess. The basis is recorded as
evidence on the entry. Re-running is idempotent.

    python scripts/derive_catalogue_modalities.py [--dry-run]
"""
import argparse
import difflib
import subprocess
from pathlib import Path

import yaml

from dataset_atlas.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
CHECKED = '2026-10-06'
ASSET_KINDS = ('image', 'audio', 'video', 'model3d')


def lines_changed(a: str, b: str) -> int:
    return sum(1 for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm='', n=0) if line[:1] in '+-' and line[:3] not in ('+++', '---'))


def derive(pack) -> list[str]:
    kinds = {asset.modality for record in pack.records for asset in record.assets if asset.modality in ASSET_KINDS}
    has_text = any(record.text or record.question or record.choices or getattr(record, 'conversation', None) for record in pack.records)
    return [kind for kind in ASSET_KINDS if kind in kinds] + (['text'] if has_text else [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    registry = Registry(ROOT)
    changed = []
    for dataset in registry.datasets():
        if dataset.modalities or dataset.coverage.preview_count == 0:
            continue
        try:
            pack = registry.pack(dataset.id)
        except FileNotFoundError:
            continue
        modalities = derive(pack)
        if not modalities:
            continue
        path = ROOT / f'registry/datasets/{dataset.id}.yaml'
        text = path.read_text()
        data = yaml.safe_load(text)
        if data.get('modalities'):
            continue
        # Re-dump with the wrap width that reproduces the committed text, so the diff holds only the new lines.
        width = min(range(60, 260, 5), key=lambda w: lines_changed(text, yaml.safe_dump(data, sort_keys=False, width=w, allow_unicode=True)))
        data['modalities'] = modalities
        data.setdefault('evidence', []).append({
            'kind': 'derived_facet', 'field': 'modalities', 'checked_on': CHECKED,
            'note': f"Derived from the {len(pack.records)}-record prepared preview: asset kinds and text fields present in at least one record. Not inferred from the name or description."})
        changed.append((dataset.id, modalities))
        if not args.dry_run:
            path.write_text(yaml.safe_dump(data, sort_keys=False, width=width, allow_unicode=True))
    for entry, modalities in changed:
        print(f'{entry}: {modalities}')
    print(f'{len(changed)} entries {"would be " if args.dry_run else ""}updated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
