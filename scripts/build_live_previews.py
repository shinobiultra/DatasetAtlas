#!/usr/bin/env python3
"""Verify the curated catalogue-to-Hugging-Face mapping against the public dataset-viewer API and write registry/live-previews.yaml.

The static site shows these datasets live: the visitor's browser asks datasets-server.huggingface.co for the first rows and renders them. Nothing is hosted
or copied here. The mapping below is curated by hand: a repository is listed only when it is the dataset's authors' own release or a well-known public
mirror, and `relation` says which. A mirror is not claimed to be byte-identical to the release a paper used. `sensitive` marks previews that show people's
faces or harmful text; the site asks for a click before loading those.

    python scripts/build_live_previews.py            # verify every entry over the network and rewrite the file
    python scripts/build_live_previews.py --check    # report entries that no longer verify, write nothing
"""
from __future__ import annotations

import argparse
import datetime
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
API = "https://datasets-server.huggingface.co"
A, M = "author_release", "public_mirror"
FACES, HARM = "shows photographs of people", "contains harmful or offensive text"

# catalogue id -> (repo, config or None, split or None, relation, sensitive reason or None)
CURATED: dict[str, tuple] = {
    "mnist": ("ylecun/mnist", "mnist", "test", A, None),
    "cifar-10": ("uoft-cs/cifar10", "plain_text", "test", A, None),
    "cifar-100": ("uoft-cs/cifar100", "cifar100", "test", A, None),
    "svhn": ("ufldl-stanford/svhn", "cropped_digits", "test", A, None),
    "food101": ("ethz/food101", None, "validation", A, None),
    "glue-cola": ("nyu-mll/glue", "cola", "validation", A, None),
    "mrpc": ("nyu-mll/glue", "mrpc", "validation", A, None),
    "qnli": ("nyu-mll/glue", "qnli", "validation", A, None),
    "qqp": ("nyu-mll/glue", "qqp", "validation", A, None),
    "sst2": ("nyu-mll/glue", "sst2", "validation", A, None),
    "wnli": ("nyu-mll/glue", "wnli", "validation", A, None),
    "tweeteval": ("cardiffnlp/tweet_eval", "emoji", "test", A, None),
    "language-identification-dataset": ("papluca/language-identification", None, "test", A, None),
    "alpaca": ("tatsu-lab/alpaca", None, "train", A, None),
    "wmdp": ("cais/wmdp", "wmdp-bio", "test", A, HARM),
    "realtoxicityprompts": ("allenai/real-toxicity-prompts", None, "train", A, HARM),
    "mmmu-dev": ("MMMU/MMMU", "Accounting", "dev", A, None),
    "mmstar": ("Lin-Chen/MMStar", None, "val", A, None),
    "algopuzzlevqa": ("declare-lab/AlgoPuzzleVQA", None, None, A, None),
    "puzzlevqa": ("declare-lab/PuzzleVQA", None, None, A, None),
    "blink": ("BLINK-Benchmark/BLINK", "Art_Style", "val", A, None),
    "hc-bench": ("JohnnyZeppelin/HC-Bench", None, None, A, None),
    "illusionvqa": ("csebuetnlp/illusionVQA-Comprehension", None, "test", A, None),
    "illusionmnist": ("VQA-Illusion/MNIST_test", None, None, A, None),
    "illusionbench-3c643c29": ("MingZhangSJTU/IllusionBench", None, None, A, None),
    "exams-v": ("Rocktim/EXAMS-V", None, "test", A, None),
    "hades": ("Monosail/HADES", None, None, A, HARM),
    "naturalbench": ("BaiqiL/NaturalBench", None, None, A, None),
    "realworldqa": ("xai-org/RealworldQA", None, "test", A, None),
    "scienceqa-img": ("derek-thomas/ScienceQA", None, "test", A, None),
    "turing-eye-test": ("HongchengGao/TuringEyeTest", None, None, A, None),
    "vibeeval": ("RekaAI/VibeEval", None, "test", A, None),
    "visual-counterfact": ("mgolov/Visual-Counterfact", None, "color", A, None),
    "visualpuzzle": ("neulab/VisualPuzzles", None, None, A, None),
    "whoops": ("nlphuji/whoops", None, "test", A, None),
    "llava-bench": ("liuhaotian/llava-bench-in-the-wild", None, None, A, None),
    "mathvision": ("MathLLMs/MathVision", None, "testmini", A, None),
    "medical-multimodal-evaluation-data": ("FreedomIntelligence/Medical_Multimodal_Evaluation_Data", None, None, A, None),
    "mm-safetybench": ("PKU-Alignment/MM-SafetyBench", "EconomicHarm", "SD", A, HARM),
    "mme": ("darkyarding/MME", None, "test", M, None),
    "mme-perception": ("darkyarding/MME", None, "test", M, None),
    "causalgym": ("aryaman/causalgym", None, "test", A, None),
    "cebab": ("CEBaB/CEBaB", None, "test", A, None),
    "counterfact": ("azhx/counterfact", None, "test", M, None),
    "bias-in-bios": ("LabHC/bias_in_bios", None, "test", M, None),
    "bbq": ("heegyu/bbq", "Age", "test", M, None),
    "docvqa": ("lmms-lab-encoder/DocVQA", "DocVQA", "validation", M, None),
    "hallusionbench": ("lmms-lab-encoder/HallusionBench", None, "image", M, None),
    "jailbreakv-28k": ("JailbreakV-28K/JailBreakV-28k", "JailBreakV_28K", "mini_JailBreakV_28K", A, HARM),
    "senator-tweets-2021": ("m-newhauser/senator-tweets", None, "test", M, None),
    "ravel": ("hij/ravel", "city_entity", "test", A, None),
    "halueval": ("pminervini/HaluEval", "dialogue", "data", M, None),
    "datacomp-1b": ("mlfoundations/datacomp_1b", None, "train", A, None),
    "the-pile": ("EleutherAI/pile_val_test", None, "test", M, None),
    "sbbench-synthetic-age-crop-false": ("vlmbias/sbbench_synthetic_age_crop_False", None, "train", A, FACES),
    "sbbench-synthetic-age-crop-true": ("vlmbias/sbbench_synthetic_age_crop_True", None, "train", A, FACES),
    "sbbench-synthetic-gender-crop-false": ("vlmbias/sbbench_synthetic_gender_crop_False", None, "train", A, FACES),
    "sbbench-synthetic-gender-crop-true": ("vlmbias/sbbench_synthetic_gender_crop_True", None, "train", A, FACES),
    "socialcounterfactuals": ("Intel/SocialCounterfactuals", None, "train", A, FACES),
    "t2i-compbench": ("NinaKarine/t2i-compbench", "3d_spatial_train", "spatial_train", M, None),
    "tdc2023": ("walledai/TDC23-RedTeaming", None, "train", M, HARM),
    "maliciousinstruct": ("walledai/MaliciousInstruct", None, "train", M, HARM),
    "safebench": ("Zonghao2025/safebench", None, "train", A, HARM),
    "omnisafebench-mm": ("jiaxiaojunQAQ/OmniSafeBench-MM", None, None, A, HARM),
    "cinic-10": ("flwrlabs/cinic10", None, "test", M, None),
    "caltech101": ("flwrlabs/caltech101", None, "train", M, None),
    "dtd": ("tanganke/dtd", None, "test", M, None),
    "eurosat": ("tanganke/eurosat", None, "test", M, None),
    "stl-10": ("tanganke/stl10", None, "test", M, None),
    "stanford-cars": ("tanganke/stanford_cars", None, "test", M, None),
    "sun397": ("tanganke/sun397", None, "test", M, None),
    "flowers102": ("dpdl-benchmark/oxford_flowers102", None, "test", M, None),
    "oxfordpet": ("timm/oxford-iiit-pet", None, "test", M, None),
    "cub-200-2011": ("bentrevett/caltech-ucsd-birds-200-2011", None, "test", M, None),
    "emnist-letters": ("tanganke/emnist_letters", "emnist-letters", "test", M, None),
    "imagenet-a": ("barkermrl/imagenet-a", None, "train", M, None),
    "imagenet-r": ("axiong/imagenet-r", "test", "test", M, None),
    "imagenet-v2": ("vaishaal/ImageNetV2", None, "train", A, None),
    "imagenet-sketch": ("nateraw/imagenet-sketch-data", None, "train", M, None),
    "imagenet-c": ("khanhvinh9/imagenet-c", None, "train", M, None),
    "objectnet": ("clip-benchmark/wds_objectnet", None, "test", M, None),
    "waterbirds": ("grodino/waterbirds", None, "test", M, None),
    "fairface": ("HuggingFaceM4/FairFace", "0.25", "validation", M, FACES),
    "celeba": ("flwrlabs/celeba", None, "test", M, FACES),
    "ffhq": ("marcosv/ffhq-dataset", None, "train", M, FACES),
    "artbench": ("zguo0525/ArtBench", None, "test", M, None),
    "places": ("ljnlonoljpiljm/places365-256px", None, "train", M, None),
    "audioset": ("agkphysics/AudioSet", "balanced", "test", M, None),
    "ucf101": ("quchenyuan/UCF101-ZIP", None, "train", M, None),
    "pope": ("lmms-lab-encoder/POPE", None, "test", M, None),
    "mm-vet": ("lmms-lab-encoder/MMVet", None, "test", M, None),
    "ok-vqa": ("lmms-lab-encoder/OK-VQA", None, "val2014", M, None),
    "textvqa": ("lmms-lab-encoder/textvqa", None, "validation", M, None),
    "vqa-v2": ("lmms-lab-encoder/VQAv2", None, "validation", M, None),
    "nocaps": ("HuggingFaceM4/NoCaps", None, "validation", M, None),
    "iconqa": ("lmms-lab-encoder/ICON-QA", None, "test", M, None),
    "coco": ("lmms-lab-encoder/COCO-Caption2017", None, "val", M, None),
    "coco-2014": ("lmms-lab-encoder/COCO-Caption", None, "val", M, None),
    "tid2013": ("Jorgvt/TID2013", None, "train", M, None),
    "rsicd": ("arampacha/rsicd", None, "test", M, None),
    "roco": ("mdwiratathya/ROCO-radiology", None, "test", M, None),
    "pascal-voc": ("nateraw/pascal-voc-2012", None, "val", M, None),
    "what-s-up": ("amitakamath2/whatsup_vlms", None, "test", A, None),
    "vsr": ("cambridgeltl/vsr_random", None, "test", A, None),
    "mmbench-en-dev": ("lmms-lab/MMBench_EN", None, "dev", M, None),
}
DISPLAYABLE = {"Image", "Audio", "Video", "Value", "ClassLabel", "List", "Sequence"}


def fetch(client: httpx.Client, path: str, **params) -> httpx.Response:
    """One request, politely: pause between calls and wait out a rate limit instead of failing the whole run."""
    for attempt in range(6):
        time.sleep(0.4)
        response = client.get(f"{API}/{path}", params=params)
        if response.status_code != 429 and response.status_code < 500:
            return response
        time.sleep(min(60, float(response.headers.get("retry-after", 10)) + attempt * 5))
    return response


def verify(client: httpx.Client, repo: str, config: str | None, split: str | None):
    splits = fetch(client, "splits", dataset=repo)
    if splits.status_code != 200:
        return None, f"splits {splits.status_code}"
    available = [(s["config"], s["split"]) for s in splits.json().get("splits", [])]
    if config is None:
        configs = [c for c, _ in available]
        config = next((c for c in ("default", "plain_text") if c in configs), configs[0] if configs else None)
    own = [s for c, s in available if c == config]
    if split is None:
        split = next((s for s in ("test", "validation", "val", "dev", "train") if s in own), own[0] if own else None)
    if (config, split) not in available:
        return None, f"no {config}/{split}; has {available[:6]}"
    rows = fetch(client, "rows", dataset=repo, config=config, split=split, offset=0, length=3)
    if rows.status_code != 200:
        return None, f"rows {rows.status_code}"
    body = rows.json()
    features = [(f["name"], f["type"].get("_type") or "Value") for f in body.get("features", [])]
    kinds = {kind for _, kind in features}
    if not body.get("rows") or not kinds & {"Image", "Audio", "Video", "Value", "ClassLabel"}:
        return None, "no displayable rows"
    # An Image feature is only worth listing when the cached asset really is served by the viewer, not an arbitrary URL.
    if "Image" in kinds:
        first = body["rows"][0]["row"]
        name = next(n for n, k in features if k == "Image")
        cell = first.get(name)
        if isinstance(cell, list):
            cell = cell[0] if cell else None
        src = cell.get("src", "") if isinstance(cell, dict) else ""
        if not src.startswith("https://datasets-server.huggingface.co/"):
            return None, "image is not served by the viewer"
    return {"config": config, "split": split, "rows_total": body.get("num_rows_total"), "media": "image" if "Image" in kinds else "video" if "Video" in kinds else "audio" if "Audio" in kinds else "text"}, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--missing", action="store_true", help="only verify entries absent from the current file (after a transient failure)")
    args = parser.parse_args()
    catalogue = {p.stem for p in (ROOT / "registry/datasets").glob("*.yaml")}
    client = httpx.Client(timeout=40, headers={"User-Agent": "DatasetAtlas-live-previews/1.0"})
    today = datetime.date.today().isoformat()
    entries, failed = {}, {}
    current = (yaml.safe_load((ROOT / "registry/live-previews.yaml").read_text()) or {}).get("previews", {}) if args.missing else {}
    for dataset_id, (repo, config, split, relation, sensitive) in CURATED.items():
        if dataset_id not in catalogue:
            failed[dataset_id] = "not a catalogue entry"
            continue
        if dataset_id in current:
            entries[dataset_id] = current[dataset_id]
            continue
        found, why = verify(client, repo, config, split)
        if found is None:
            failed[dataset_id] = why
            continue
        entry = {"repo": repo, **found, "relation": relation}
        if sensitive:
            entry["sensitive"] = sensitive
        entries[dataset_id] = entry
    print(f"{len(entries)} verified, {len(failed)} not")
    for dataset_id, why in failed.items():
        print(f"  skipped {dataset_id}: {why}")
    if args.check:
        return 1 if failed else 0
    document = {"schema_version": "1.0", "checked_on": today, "source": API, "previews": dict(sorted(entries.items()))}
    (ROOT / "registry/live-previews.yaml").write_text("# Generated by scripts/build_live_previews.py from its curated table; edit that table, not this file.\n" + yaml.safe_dump(document, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
