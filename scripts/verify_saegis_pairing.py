#!/usr/bin/env python3
"""Check SAEgis' clean/attacked pairing by pixel similarity and every fetched file against its pinned Git blob SHA-1.

Every attacked image (dev and test, all sources and attacks) is fetched from the pinned commit together with its same-named original, checked
against the inventory's Git blob SHA-1 and byte length, and compared by PSNR. A pair is accepted when the images have the same size and a PSNR
of at least THRESHOLD dB. Unrelated images of this collection measured 6-16 dB and genuine pairs 24-30 dB in the sampled check, so the
threshold separates the two; it is a plausibility check on the file-name pairing, not a proof of how the authors generated the images.
Only network reads of the pinned commit are made; train originals are not fetched.
"""
import argparse
import concurrent.futures as futures
import hashlib
import io
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = 20.0


def fetch(url: str) -> bytes:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', default=str(ROOT / 'registry/media/saegis-clean-and-adversarial-splits.json'))
    parser.add_argument('--commit', default='6365cbfc9e4de1e6df01624b793abbef09789cc8')
    parser.add_argument('--output', default=str(ROOT / 'reports/saegis-pairing-verification-20261006.json'))
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--limit', type=int, default=0, help='check only the first N attacked images (for a quick run)')
    args = parser.parse_args()
    inventory = json.loads(Path(args.inventory).read_bytes())['files']
    base = f'https://raw.githubusercontent.com/conan1024hao/SAEgis/{args.commit}/'
    attacked = sorted(name for name in inventory if '/attacked/' in name)
    if args.limit:
        attacked = attacked[:args.limit]
    cache: dict[str, bytes] = {}

    def blob(name: str) -> bytes:
        data = fetch(base + name)
        entry = inventory[name]
        if len(data) != entry['bytes'] or hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest() != entry['git_blob_sha1']:
            raise ValueError(f'{name} differs from its pinned Git blob')
        return data

    def check(name: str) -> dict:
        parts = name.split('/')
        original_name = '/'.join(['images', parts[1], 'original', parts[-2], parts[-1]])
        attacked_data, original_data = blob(name), blob(original_name)
        a = Image.open(io.BytesIO(attacked_data)).convert('RGB')
        o = Image.open(io.BytesIO(original_data)).convert('RGB')
        if a.size != o.size:
            return {'attacked': name, 'original': original_name, 'same_size': False, 'size': [list(a.size), list(o.size)], 'psnr_db': None, 'ok': False}
        x, y = np.asarray(a, dtype='float64'), np.asarray(o, dtype='float64')
        mse = float(((x - y) ** 2).mean())
        psnr = 99.0 if mse == 0 else float(10 * np.log10(255 ** 2 / mse))
        return {'attacked': name, 'original': original_name, 'same_size': True, 'size': list(a.size), 'psnr_db': round(psnr, 2), 'ok': psnr >= THRESHOLD}

    results = []
    with futures.ThreadPoolExecutor(args.workers) as pool:
        for result in pool.map(check, attacked):
            results.append(result)
    by_attack: dict[str, list[float]] = {}
    for r in results:
        if r['psnr_db'] is not None:
            by_attack.setdefault(r['attacked'].split('/')[3], []).append(r['psnr_db'])
    failures = [r for r in results if not r['ok']]
    receipt = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'repository': 'https://github.com/conan1024hao/SAEgis', 'commit': args.commit,
        'method': f'every attacked image fetched with its same-named original; Git blob SHA-1 and length verified for both; same size and PSNR >= {THRESHOLD} dB',
        'threshold_db': THRESHOLD, 'pairs_checked': len(results), 'pairs_failing': len(failures),
        'psnr_db_by_attack': {k: {'n': len(v), 'min': min(v), 'median': round(float(np.median(v)), 2), 'max': max(v)} for k, v in sorted(by_attack.items())},
        'failures': failures[:50], 'train_originals_fetched': False,
        'limits': 'A similarity threshold on file-name pairing, not proof of how the images were generated. Train originals have no attacked counterpart and were not fetched.',
    }
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('pairs_checked', 'pairs_failing', 'psnr_db_by_attack')}, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
