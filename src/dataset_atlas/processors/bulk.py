"""Columnar processor results for runs too large for one JSON item per record.

A processor that runs with ``storage: arrays`` returns this instead of an items list.
``ids`` names the completed rows, each array in ``arrays`` has one row per id, and
``extras`` holds arrays that are not row-aligned (cluster centres, say). Every other
requested record is in ``skipped`` with its status and reason, so each record is
accounted for. The worker writes the result as a shard; the coordinator assembles the
shards into one artifact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class BulkResult:
    ids: list[str]
    arrays: dict[str, np.ndarray]
    provenance: dict[str, Any]
    extras: dict[str, np.ndarray] = field(default_factory=dict)
    skipped: dict[str, dict[str, Any]] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    texts: dict[str, list[str]] = field(default_factory=dict)  # one string per id, for answers, labels, verdicts

    def check(self, requested: list[str]) -> None:
        """Every requested record is either a row or skipped, exactly once."""
        accounted = list(self.ids) + list(self.skipped)
        if len(accounted) != len(set(accounted)) or set(accounted) != set(requested):
            raise ValueError("A bulk result must account for every requested record exactly once")
        for name, array in self.arrays.items():
            if len(array) != len(self.ids):
                raise ValueError(f"Array {name} has {len(array)} rows for {len(self.ids)} ids")
        for name, values in self.texts.items():
            if len(values) != len(self.ids):
                raise ValueError(f"Text column {name} has {len(values)} rows for {len(self.ids)} ids")
