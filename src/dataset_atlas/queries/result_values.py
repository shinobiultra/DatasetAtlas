"""One scalar result contract for preview and complete-index queries."""
from __future__ import annotations

import math
from typing import Any


def result_values(item: dict[str, Any]) -> dict[str, Any]:
    status = item.get('status', 'unknown')
    if not isinstance(status, str):
        raise ValueError('Result item status must be a string')
    values = {'status': status}
    if status != 'completed':
        return values
    output = item.get('output', {})
    if not isinstance(output, dict):
        raise ValueError('Completed result output must be an object')
    def add_scalars(mapping, excluded=()):
        for key, value in mapping.items():
            if not isinstance(key, str):
                raise ValueError('Result output keys must be strings')
            if key not in excluded and (value is None or isinstance(value, (str, bool, int, float))) and (not isinstance(value, float) or math.isfinite(value)):
                values[key] = value
    add_scalars(output)
    if isinstance(output.get('detections'), list):
        values['detection_count'] = len(output['detections'])
    assets = output.get('assets')
    if isinstance(assets, list) and assets:
        completed = [asset for asset in assets if isinstance(asset, dict) and asset.get('status') == 'completed']
        if len(completed) == len(assets) == 1:
            add_scalars(completed[0], {'asset_id', 'status'})
        if len(completed) == len(assets):
            unique = {}
            for ordinal, asset in enumerate(completed):
                identity = ('sha256', asset['file_sha256']) if asset.get('file_sha256') else ('asset', asset.get('asset_id', ordinal))
                unique[identity] = asset
            groups = [asset.get('detections', (asset.get('output') or {}).get('detections')) for asset in unique.values()]
            if all(isinstance(group, list) for group in groups):
                boxes = [box for group in groups for box in group]
                values['detection_count'] = len(boxes)
                values['person_count'] = sum(isinstance(box, dict) and box.get('class') == 'person' for box in boxes)
    return values
