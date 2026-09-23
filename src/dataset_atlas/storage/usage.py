"""Read-only, inode-aware accounting of the actual Atlas workspace."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path
import stat


def workspace_usage(root, target_bytes=100_000_000_000, ceiling_bytes=150_000_000_000, extra_roots=()):
    if not 0 < target_bytes <= ceiling_bytes:
        raise ValueError('Storage target must be positive and no larger than the ceiling')
    root = Path(root).resolve()
    groups = defaultdict(lambda: {'files': 0, 'logical_bytes': 0, 'unique_file_bytes': 0, 'allocated_bytes': 0})
    seen = set()
    skipped_links = 0
    errors = []
    # Explicit external roots are included, while incidental symlink targets are not.
    locations = [(root, None)]
    for value in extra_roots:
        external = Path(value).expanduser().resolve()
        if external.is_relative_to(root) or any(external.is_relative_to(p) for p, _ in locations):
            continue
        locations.append((external, 'external:' + str(external)))
    for location, external_category in locations:
        if not location.is_dir():
            errors.append({'path': str(location), 'error': 'Configured storage root is missing or not a directory'})
            continue
        def onerror(exc):
            errors.append({'path': str(exc.filename), 'error': str(exc)})
        for directory, children, filenames in os.walk(location, followlinks=False, onerror=onerror):
            children.sort()
            filenames.sort()
            for name in children + filenames:
                path = Path(directory) / name
                try:
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode):
                        skipped_links += 1
                        continue
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    relative = path.relative_to(location)
                    parts = relative.parts
                    category = external_category or ('/'.join(parts[:2]) if parts[0] == 'work' and len(parts) > 2 else parts[0] if len(parts) > 1 else 'workspace files')
                    row = groups[category]
                    row['files'] += 1
                    row['logical_bytes'] += info.st_size
                    inode = (info.st_dev, info.st_ino)
                    if inode not in seen:
                        seen.add(inode)
                        row['unique_file_bytes'] += info.st_size
                        row['allocated_bytes'] += info.st_blocks * 512
                except OSError as exc:
                    errors.append({'path': str(path), 'error': str(exc)})
    totals = {key: sum(row[key] for row in groups.values()) for key in ('files', 'logical_bytes', 'unique_file_bytes', 'allocated_bytes')}
    used = totals['allocated_bytes']
    return {'root': str(root), 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'target_bytes': target_bytes, 'ceiling_bytes': ceiling_bytes,
            'status': 'incomplete_scan' if errors else 'above_ceiling' if used > ceiling_bytes else 'above_target' if used > target_bytes else 'within_target',
            **totals, 'bytes_above_target': max(0, used - target_bytes),
            'groups': dict(sorted(groups.items(), key=lambda item: -item[1]['allocated_bytes'])),
            'external_symlinks_not_counted': skipped_links, 'errors': errors,
            'included_external_roots': [str(p) for p, category in locations if category],
            'measurement_note': 'Regular files only; hard links counted once, allocated filesystem blocks. Reflink-shared extents may be counted more than once. Only explicitly configured external model/source roots are included. Incidental symlink targets and directory metadata are outside this measurement.'}
