"""Find immutable results in active and retained version packs."""
from collections import OrderedDict
import hashlib
from threading import RLock

from dataset_atlas.models import Pack


def merge_artifacts(items, max_encoded_bytes=100_000_000):
    result = {}; hashes = {}; total = 0
    for artifact in items:
        encoded = artifact.model_dump_json().encode()
        digest = hashlib.sha256(encoded).hexdigest()
        if artifact.id in hashes and hashes[artifact.id] != digest:
            raise ValueError('Retained result ID has conflicting immutable contents')
        if artifact.id not in hashes:
            total += len(encoded)
            if total > max_encoded_bytes:
                raise ValueError('Retained results exceed interactive response budget; narrow the selected snapshots')
        hashes[artifact.id] = digest
        result[artifact.id] = artifact
    return list(result.values())


class RetainedArtifactIndex:
    def __init__(self, registry, max_encoded_bytes=64_000_000):
        self.registry = registry
        self.maximum = max_encoded_bytes
        self.cache = OrderedDict()
        self.lock = RLock()

    def list(self, snapshot_ids=None, dataset_ids=None, artifact_ids=None):
        items = []
        for dataset_id in dataset_ids if dataset_ids is not None else self.registry.ids():
            for dataset, path, _ in self.registry.versions(dataset_id):
                if snapshot_ids is not None and dataset.snapshot_id not in snapshot_ids:
                    continue
                if not path.is_file():continue
                stat = path.stat()
                if stat.st_size > 100_000_000:
                    raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
                signature = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
                with self.lock:
                    cached = self.cache.get(str(path))
                    if cached is not None and cached[0] == signature:
                        self.cache.move_to_end(str(path))
                        packed = cached[1]
                    else:
                        packed = Pack.model_validate_json(path.read_bytes()).artifacts
                        size = sum(len(item.model_dump_json().encode()) for item in packed)
                        self.cache.pop(str(path), None)
                        if size <= self.maximum:
                            while self.cache and sum(value[2] for value in self.cache.values())+size > self.maximum:
                                self.cache.popitem(last=False)
                            self.cache[str(path)] = (signature, packed, size)
                items.extend(item for item in packed if (snapshot_ids is None or snapshot_ids.intersection(item.snapshot_ids))
                             and (artifact_ids is None or item.id in artifact_ids))
        return merge_artifacts(items)
