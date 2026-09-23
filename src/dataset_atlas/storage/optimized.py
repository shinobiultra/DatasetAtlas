"""An evictable, shared cache of full-resolution browsing representations."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import threading

from .cache import BoundedCache, CacheIdentity
from .compact import encode_image

_ENCODERS = threading.BoundedSemaphore(2)


def storage_policy(root):
    path = Path(root)/'local-config/storage.json'
    if not path.is_file(): return None
    policy = json.loads(path.read_text())
    target = policy.get('target_bytes', 100_000_000_000)
    ceiling = policy.get('ceiling_bytes', 150_000_000_000)
    cache = policy.get('optimized_cache_bytes', 5_000_000_000)
    if any(type(n) is not int for n in (target, ceiling, cache)) or not 0 < cache <= target <= ceiling:
        raise ValueError('Invalid shared storage policy byte limits')
    if not isinstance(policy.get('external_roots', []), list) or any(not isinstance(p, str) for p in policy.get('external_roots', [])):
        raise ValueError('External storage roots must be a list of directory paths')
    return {**policy, 'target_bytes': target, 'ceiling_bytes': ceiling, 'optimized_cache_bytes': cache}


def configure_storage(root, *, target_bytes, ceiling_bytes, optimized_cache_bytes, external_roots=()):
    policy = {'target_bytes': target_bytes, 'ceiling_bytes': ceiling_bytes,
              'optimized_cache_bytes': optimized_cache_bytes, 'optimize_on_demand': True,
              'enforce_preparation_ceiling': True,
              'external_roots': [str(Path(p).expanduser().resolve()) for p in external_roots]}
    if any(type(n) is not int for n in (target_bytes, ceiling_bytes, optimized_cache_bytes)) or not 0 < optimized_cache_bytes <= target_bytes <= ceiling_bytes:
        raise ValueError('Require 0 < cache <= target <= ceiling')
    from dataset_atlas.preparation import atomic
    atomic(Path(root)/'local-config/storage.json', policy)
    return policy


def preparation_headroom(root, required_bytes, running_reservations=0):
    policy = storage_policy(root)
    if not policy or not policy.get('enforce_preparation_ceiling'): return None
    from .usage import workspace_usage
    usage = workspace_usage(root, policy['target_bytes'], policy['ceiling_bytes'], policy.get('external_roots', []))
    available = max(0, policy['ceiling_bytes'] - usage['allocated_bytes'] - running_reservations)
    return {'ceiling_bytes': policy['ceiling_bytes'], 'allocated_workspace_bytes': usage['allocated_bytes'],
            'reserved_by_running_preparations': running_reservations, 'available_bytes': available,
            'required_bytes': required_bytes, 'admitted': not usage['errors'] and required_bytes <= available,
            'scope': 'Workspace regular files plus explicitly configured external model/source roots.',
            'measurement_errors': usage['errors']}


@contextmanager
def _lock(path):
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def optimized_image(root, dataset_id, snapshot_id, asset_ref, load_original, *, cache_bytes=5_000_000_000):
    """Fetch/encode once per immutable identity; no original is modified or evicted."""
    from PIL import Image
    identity = CacheIdentity(snapshot_id, json.dumps([dataset_id, asset_ref]), 'optimized-browsing-v1',
                             f'avif-quality60-speed6-444-pillow{Image.__version__}')
    cache = BoundedCache(Path(root)/'work/media-cache/optimized', cache_bytes)
    with _lock(cache.root/'partial'/(identity.key+'.lock')):
        with _lock(cache.root/'objects.lock'):
            path = cache.get(identity)
            packet = path.read_bytes() if path else None
        if packet is None:
            with _ENCODERS:
                original = load_original()
                data, mime, metadata = encode_image(original, quality=60, speed=6)
            packet = json.dumps({'mime': mime, 'metadata': metadata}, separators=(',', ':')).encode() + b'\n' + data
            with _lock(cache.root/'objects.lock'):
                partial = cache.partial_path(identity)
                try:
                    partial.write_bytes(packet)
                    cache.commit(identity, partial)
                finally:
                    partial.unlink(missing_ok=True)
        header, data = packet.split(b'\n', 1)
        entry = json.loads(header)
        return data, entry['mime'], entry['metadata']
