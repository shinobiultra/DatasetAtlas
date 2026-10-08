"""Named threshold transforms over retained detector results; no model execution."""
from __future__ import annotations

import copy
import math
import json

from dataset_atlas.models import Artifact, content_id


def run_detector_view(records, config):
    raw = config.get('detector_artifact')
    if not isinstance(raw, dict):
        raise ValueError('Choose a retained detector artifact')
    artifact = Artifact.model_validate(raw)
    if len(json.dumps(raw, ensure_ascii=False, allow_nan=False)) > 20_000_000:
        raise ValueError('Detector view input exceeds 20 MB JSON bound')
    if not artifact.kind.startswith('detect.'):
        raise ValueError('Threshold views require a detector artifact')
    if any(record.snapshot_id not in artifact.snapshot_ids or record.unit != artifact.unit for record in records):
        raise ValueError('Detector view snapshot or sample unit is incompatible')
    provenance = artifact.provenance.get('processor_provenance', {})
    extraction = provenance.get('extraction_threshold')
    minimum = provenance.get('display_threshold', extraction)
    threshold = config.get('display_threshold')
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in (extraction, minimum, threshold)):
        raise ValueError('Detector view requires explicit finite extraction/display thresholds within 0..1')
    if threshold < minimum:
        raise ValueError('Display threshold cannot reveal detections discarded by the upstream run or view')
    source = {}
    for item in artifact.data.get('items', []):
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in source:
            raise ValueError('Detector source requires unique stable item IDs')
        source[item['id']] = item
    items = []
    for record in records:
        original = source.get(record.id)
        if original is None:
            items.append({'id': record.id, 'status': 'not_applicable', 'output': None})
            continue
        if original.get('status') != 'completed':
            items.append({'id': record.id, 'status': original.get('status', 'not_applicable'), 'output': None,
                          **({'error': original['error']} if 'error' in original else {})})
            continue
        output = copy.deepcopy(original.get('output') or {})
        assets = output.get('assets')
        if not isinstance(assets, list):
            raise ValueError('Retained detector output lacks per-asset results')
        all_boxes = []
        seen_originals = set()
        complete = bool(assets)
        for asset in assets:
            if asset.get('status') != 'completed':
                complete = False
                continue
            boxes = asset.get('detections')
            if not isinstance(boxes, list):
                raise ValueError('Completed detector asset lacks retained detections')
            if any(not isinstance(box, dict) or type(box.get('score')) not in (int, float)
                   or not math.isfinite(box['score']) or not 0 <= box['score'] <= 1 for box in boxes):
                raise ValueError('Retained detection scores are invalid')
            asset['detections'] = [box for box in boxes if box['score'] >= threshold]
            original_key = ('sha256', asset['file_sha256']) if asset.get('file_sha256') else ('asset', asset.get('asset_id'))
            if original_key not in seen_originals:
                seen_originals.add(original_key)
                all_boxes.extend(asset['detections'])
        output['derived'] = {'detection_coverage_complete_v1': complete,
                             'detection_count_v1': len(all_boxes) if complete else None,
                             'max_score_v1': max((box['score'] for box in all_boxes), default=None)}
        if artifact.kind == 'detect.coco_v1' or 'person_count_v1' in (original.get('output') or {}).get('derived', {}):
            output['derived']['person_count_v1'] = sum(box.get('class') == 'person' for box in all_boxes) if complete else None
        items.append({'id': record.id, 'status': 'completed', 'output': output})
    transform = {'method': 'retained-detection-score-gte-v1', 'source_artifact_id': artifact.id,
                 'source_run_id': artifact.run_id, 'extraction_threshold': extraction,
                 'upstream_display_threshold': minimum, 'display_threshold': threshold,
                 'sample_unit': artifact.unit, 'snapshot_ids': artifact.snapshot_ids}
    return items, {**transform, 'transform_id': content_id(transform, 'detector-view:'),
                   'model_execution': False, 'source_results_modified': False}
