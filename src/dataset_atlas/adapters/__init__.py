"""Bounded, source-backed adapters. No adapter prepares data without an explicit plan."""
from .core import (
    DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource, RecordBatch,
    SourceDescription, ValidationReport, build_preview, get_adapter,
    resolve_dataset_asset,
)

__all__ = [
    "DatasetAdapter", "MediaHandle", "PreparationPlan", "PreparedSource",
    "RecordBatch", "SourceDescription", "ValidationReport", "build_preview",
    "get_adapter",
    "resolve_dataset_asset",
]
