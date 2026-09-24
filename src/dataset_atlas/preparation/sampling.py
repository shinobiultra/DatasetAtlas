"""Order-independent, bounded sampling while the complete index is written."""
from __future__ import annotations

import hashlib
import heapq


class PreviewSampler:
    """Select distinct primary assets, or examples when there is no asset.

    SHA-256 ranks give every group a reproducible pseudorandom priority. Only
    the best ``size`` groups are retained, including one ranked example from
    each group. Repeated questions cannot crowd out distinct images. This is
    not a sample for estimating example-level population prevalence.
    """

    def __init__(self, size=100, seed=0):
        if type(size) is not int or not 1 <= size <= 100:
            raise ValueError('Preview size must be between 1 and 100')
        if type(seed) is not int:
            raise ValueError('Preview seed must be an integer')
        self.size, self.seed = size, seed
        self.selected = {}
        self.heap = []
        self.population_count = 0

    def rank(self, value):
        return int.from_bytes(hashlib.sha256(f'{self.seed}:{value}'.encode()).digest(), 'big')

    def add(self, record):
        self.population_count += 1
        primary = record.asset_ids[0] if record.asset_ids else None
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
        return {'method': 'sha256_bottom_k_primary_asset', 'seed': self.seed,
                'unit': unit, 'grouping': 'primary asset ID; record ID for records without assets',
                'population': 'complete pinned indexed population', 'population_count': self.population_count,
                'requested_count': self.size, 'returned_count': len(self.selected),
                'source_revision': release, 'media_representation': 'original',
                'selection_note': 'One hash-ranked record per sampled primary asset. All linked assets remain. Not an example-prevalence estimate.'}
