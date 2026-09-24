"""Order-independent, bounded sampling while the complete index is written."""
from __future__ import annotations

import hashlib
import heapq
from io import BytesIO

from PIL import Image


class PreviewSampler:
    """Select distinct primary assets, or examples when there is no asset.

    SHA-256 ranks give every group a reproducible pseudorandom priority. Only
    the best ``size`` groups are retained, including one ranked example from
    each group. Repeated questions cannot crowd out distinct images. This is
    not a sample for estimating example-level population prevalence.
    """

    def __init__(self, size=100, seed=0, group_by='primary_asset'):
        if type(size) is not int or not 1 <= size <= 500:
            raise ValueError('Preview candidate pool must be between 1 and 500')
        if type(seed) is not int:
            raise ValueError('Preview seed must be an integer')
        if group_by not in {'primary_asset', 'example'}:
            raise ValueError('Preview grouping must be primary_asset or example')
        self.size, self.seed, self.group_by = size, seed, group_by
        self.selected = {}
        self.heap = []
        self.population_count = 0

    def rank(self, value):
        return int.from_bytes(hashlib.sha256(f'{self.seed}:{value}'.encode()).digest(), 'big')

    def add(self, record):
        self.population_count += 1
        primary = record.asset_ids[0] if self.group_by == 'primary_asset' and record.asset_ids else None
        group = f'asset:{primary}' if primary else f'example:{record.id}'
        rank = self.rank(group)
        example_rank = (self.rank('record:' + record.id), record.id)
        previous = self.selected.get(group)
        if previous is not None:
            if example_rank < previous[0]:
                self.selected[group] = (example_rank, record)
            return
        if len(self.heap) == self.size:
            worst_rank, worst_group = self.heap[0]
            if (rank, group) >= (-worst_rank, worst_group):
                return
            heapq.heappop(self.heap)
            del self.selected[worst_group]
        heapq.heappush(self.heap, (-rank, group))
        self.selected[group] = (example_rank, record)

    def records(self):
        return [self.selected[group][1] for group in sorted(self.selected, key=lambda group: (self.rank(group), group))]

    def description(self, release, unit='example'):
        if unit not in {'asset', 'example', 'entity', 'conversation'}:
            raise ValueError('Unknown preview sampling unit')
        return {'method': 'sha256_bottom_k_primary_asset' if self.group_by == 'primary_asset' else 'sha256_bottom_k_example', 'seed': self.seed,
                'unit': unit, 'grouping': 'primary asset ID; record ID for records without assets' if self.group_by == 'primary_asset' else 'record ID',
                'population': 'complete pinned indexed population', 'population_count': self.population_count,
                'requested_count': self.size, 'returned_count': len(self.selected),
                'source_revision': release, 'media_representation': 'original',
                'selection_note': 'One hash-ranked record per sampled primary asset. All linked assets remain. Not an example-prevalence estimate.' if self.group_by == 'primary_asset' else 'Hash-ranked examples. Reused images may occur more than once.'}


def select_verified_remote_preview(candidates, resolve_asset, count, on_progress=None):
    """Keep the first hash-ranked candidates whose original image slots open."""
    verified = []
    absent = 0
    checked_assets = 0
    for record in candidates:
        if len(verified) == count:
            break
        try:
            record_assets = 0
            for asset in record.assets:
                if asset.modality != 'image' or not asset.uri:
                    continue
                handle = resolve_asset(asset.uri)
                with Image.open(BytesIO(handle.data)) as image:
                    image.verify()
                asset.sha256 = handle.sha256
                record_assets += 1
        except FileNotFoundError:
            absent += 1
            continue
        checked_assets += record_assets
        verified.append(record)
        if on_progress and (len(verified) % 5 == 0 or len(verified) == count):
            on_progress(verified_records=len(verified), verified_assets=checked_assets,
                        candidates_checked=len(verified) + absent)
    if len(verified) != count:
        raise ValueError(f'Only {len(verified)} of {count} original-media preview records are available')
    return verified, {'candidate_pool': len(candidates),
        'candidates_checked': len(verified) + absent,
        'unavailable_candidate_records': absent,
        'verified_preview_assets': checked_assets,
        'selection': 'Lowest SHA-256-ranked distinct assets with every selected image opened from the pinned source'}


class AssetFirstPreviewSampler:
    """Prefer distinct images, then fill a short preview with distinct examples."""

    def __init__(self, size=100, seed=0):
        self.size = size
        self.assets = PreviewSampler(size, seed, group_by='primary_asset')
        self.examples = PreviewSampler(size, seed, group_by='example')

    @property
    def population_count(self):
        return self.assets.population_count

    def add(self, record):
        self.assets.add(record)
        self.examples.add(record)

    def records(self):
        selected = self.assets.records()
        seen = {record.id for record in selected}
        for record in self.examples.records():
            if len(selected) == self.size:
                break
            if record.id not in seen:
                selected.append(record)
                seen.add(record.id)
        return selected

    def description(self, release, unit='example'):
        result = self.assets.description(release, unit)
        result.update(method='sha256_asset_first_with_example_fill',
            grouping='Distinct primary assets first; hash-ranked distinct examples fill remaining slots',
            returned_count=len(self.records()),
            selection_note='Distinct images are preferred. When there are fewer distinct images than requested examples, additional hash-ranked examples reuse those images.')
        return result
