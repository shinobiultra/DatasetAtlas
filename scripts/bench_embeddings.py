"""Time the columnar embedding path on synthetic inputs (needs the pinned local model weights).

Writes distinct JPEGs and sentences to a throwaway directory (no dataset content, nothing downloaded) and
reports images/s and sentences/s once the model is loaded, plus what a single legacy group of 16 costs.

    uv run python scripts/bench_embeddings.py --images 2000 --sentences 20000
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

from dataset_atlas.models import Asset, Record
from dataset_atlas.processors import embeddings

ROOT = Path(__file__).resolve().parents[1]


def jpegs(directory: Path, count: int, seed: int = 1) -> list[Record]:
    rng = np.random.default_rng(seed)
    records = []
    for index in range(count):
        coarse = rng.random((6, 8, 3)).repeat(80, 0).repeat(80, 1)[:480, :640]
        pixels = (255 * np.clip(coarse * 0.8 + 0.2 * rng.random((480, 640, 3)), 0, 1)).astype(np.uint8)
        path = directory / f"image{index:06d}.jpg"
        Image.fromarray(pixels).save(path, quality=88)
        records.append(Record(id=f"r{index}", dataset_id="d", release_id="v1", snapshot_id="s",
                              assets=[Asset(id=f"a{index}", dataset_id="d", release_id="v1", modality="image", uri=str(path))]))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images", type=int, default=2000)
    parser.add_argument("--sentences", type=int, default=20000)
    parser.add_argument("--precision", default="auto", choices=["auto", "fp32", "bf16", "fp16"])
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--decode-threads", type=int, default=None, help="default: the library's choice")
    args = parser.parse_args()
    recipes = json.loads((ROOT / "local-config/recipes.json").read_text())
    common = {"model_roots": [str(ROOT / "work/models")], "device": "cuda", "precision": args.precision}
    work = Path(tempfile.mkdtemp(prefix="atlas-embed-bench-"))
    try:
        records = jpegs(work, args.images)
        sigl = {**recipes["embed.siglip2"], **common, "asset_roots": [str(work)], "representation": "image", "batch_size": args.batch_size,
                **({"decode_threads": args.decode_threads} if args.decode_threads else {})}
        started = time.perf_counter()
        embeddings.run_embeddings_bulk("embed.siglip2", records[:8], sigl)
        print(f"SigLIP 2 first call (verify weights, load, place on GPU): {time.perf_counter() - started:.1f}s")
        started = time.perf_counter()
        result, _ = embeddings.run_embeddings_bulk("embed.siglip2", records, sigl)
        elapsed = time.perf_counter() - started
        print(f"SigLIP 2 images:  {len(result.ids)} in {elapsed:.1f}s = {len(result.ids) / elapsed:,.0f} images/s ({result.provenance['precision']})")
        started = time.perf_counter()
        embeddings.run_embeddings("embed.siglip2", records[:16], {**sigl, "precision": "fp32"})
        print(f"legacy path, one group of 16 (as a real run does): {time.perf_counter() - started:.1f}s = {16 / (time.perf_counter() - started):.1f} images/s")
        words = ["what", "color", "is", "the", "dog", "how", "many", "people", "are", "standing", "near", "table", "is", "there", "a", "red", "car"]
        rng = np.random.default_rng(2)
        questions = [Record(id=f"q{index}", dataset_id="d", release_id="v1", snapshot_id="s",
                            question=" ".join(rng.choice(words, size=int(rng.integers(5, 12)))) + f" {index}?") for index in range(args.sentences)]
        mini = {**recipes["embed.minilm"], **common, "representation": "question", "batch_size": 1024}
        embeddings.run_embeddings_bulk("embed.minilm", questions[:8], mini)
        started = time.perf_counter()
        result, _ = embeddings.run_embeddings_bulk("embed.minilm", questions, mini)
        elapsed = time.perf_counter() - started
        print(f"MiniLM questions: {len(result.ids)} in {elapsed:.1f}s = {len(result.ids) / elapsed:,.0f} sentences/s ({result.provenance['precision']})")
        started = time.perf_counter()
        embeddings.run_embeddings("embed.minilm", questions[:16], {**mini, "precision": "fp32"})
        print(f"legacy path, one group of 16: {time.perf_counter() - started:.1f}s = {16 / (time.perf_counter() - started):.1f} sentences/s")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
