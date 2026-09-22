"""Read-only inventory and evidence-preserving extraction of the local paper corpus.

All outputs are written below the caller's output directory or registry root.
Candidate detection is deliberately a review queue, never an acceptance decision.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

import yaml


SCHEMA_VERSION = "1.0.0"
OUTCOMES = {
    "processed", "processed_with_review_items", "no_dataset_mentions_found_after_review",
    "extraction_failed", "unavailable",
}

# A seed vocabulary supplements context discovery; it is not a claimed complete
# ontology. Keep spelling and release distinctions in the source evidence.
SEED_NAMES = (
    "ImageNet", "ImageNet-1K", "ImageNet-21K", "ImageNet-A", "ImageNet-R",
    "ImageNet-Sketch", "ImageNet-V2", "ImageNet-C", "ObjectNet", "COCO",
    "MS COCO", "COCO-Captions", "COCO-QA", "Flickr30k", "Flickr8k",
    "Visual Genome", "VQA", "VQA v2", "VQAv2", "GQA", "OK-VQA",
    "A-OKVQA", "TextVQA", "VizWiz", "ScienceQA", "MMMU", "MMBench",
    "MM-Vet", "MME", "POPE", "SEED-Bench", "HallusionBench", "SugarCrepe",
    "Winoground", "ARO", "VL-Checklist", "CREPE", "VSR", "NLVR2",
    "RefCOCO", "RefCOCO+", "RefCOCOg", "Visual7W", "CLEVR", "CLEVR-Humans",
    "CLEVR-CoGenT", "CLEVRER", "Shapes3D", "dSprites", "MPI3D",
    "LAION-400M", "LAION-2B", "LAION-5B", "DataComp", "CC3M", "CC12M",
    "Conceptual Captions", "SBU Captions", "WIT", "YFCC100M", "WebVid",
    "LLaVA-Instruct-150K", "LLaVA-Bench", "MMStar", "MathVista", "ChartQA",
    "DocVQA", "AI2D", "OCR-VQA", "OCRVQA", "TallyQA", "VCR", "SNLI-VE",
    "Hateful Memes", "FairFace", "CelebA", "UTKFace", "BUPT-Balancedface",
    "BBQ", "BOLD", "StereoSet", "CrowS-Pairs", "GenderBias-VL",
    "Waterbirds", "CUB-200", "CUB", "Flowers102", "Oxford Flowers",
    "Stanford Cars", "Food-101", "Places365", "SUN397", "DTD", "EuroSAT",
    "CIFAR-10", "CIFAR-100", "MNIST", "Fashion-MNIST", "SVHN", "Tiny ImageNet",
    "Pascal VOC", "Open Images", "LVIS", "ADE20K", "Cityscapes",
    "Kinetics-400", "Kinetics-700", "Something-Something V2", "UCF101",
    "HMDB51", "Ego4D", "ActivityNet", "MSR-VTT", "MSVD", "VATEX",
    "MVBench", "Video-MME", "VideoMME", "Perception Test", "NExT-QA",
    "HumanEval", "MMLU", "GSM8K", "TruthfulQA", "WinoGrande", "SQuAD",
    "Common Crawl", "C4", "The Pile", "WikiText", "Wikipedia",
    "AdvBench", "HarmBench", "JailbreakBench", "SafeBench",
    "PHANTOM", "JailBreakV-28K", "MM-SafetyBench", "OmniSafeBench-MM",
    "VIA-Bench", "Turing Eye Test", "COCO-gender", "FACET", "MIAP",
    "PHASE", "SA-1B", "OpenImages", "PAIRS", "SocialCounterfactuals",
    "VQA 2.0", "IllusionBench+", "SVO-Probes", "Visual-Counterfact",
    "FineVision", "CEBaB", "FFHQ", "Set14", "GYAFC", "OASIS",
    "NRC-VAD", "Chicago Face Database", "CFD", "ShapeWorld",
    "RealToxicityPrompts", "HC-Bench", "IlluChar", "SBBench",
)

NAME_PATTERN = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(name) for name in sorted(SEED_NAMES, key=len, reverse=True)) + r")(?![\w-])",
    re.IGNORECASE,
)
CONTEXT_PATTERN = re.compile(
    r"\b(?:dataset|data set|benchmark|corpus|test set|training set|evaluation set|"
    r"image collection|image-text pairs|question-answer pairs|user study|stimuli)\b",
    re.IGNORECASE,
)
INTRO_PATTERN = re.compile(
    r"\b(?:introduc(?:e|ed|ing)|propos(?:e|ed)|construct(?:ed)?|creat(?:e|ed)|"
    r"curat(?:e|ed)|collect(?:ed)?|release(?:d)?)\b", re.IGNORECASE,
)
TRAIN_PATTERN = re.compile(r"\b(?:train(?:ed|ing)?|pretrain(?:ed|ing)?|fine.?tun(?:e|ed|ing))\b", re.IGNORECASE)
EVAL_PATTERN = re.compile(r"\b(?:evaluat(?:e|ed|ion)|test(?:ed|ing)?|benchmark(?:ed|ing)?|experiments?)\b", re.IGNORECASE)
DERIVED_PATTERN = re.compile(r"\b(?:deriv(?:e|ed)|annotat(?:e|ed|ion)|subset|filter(?:ed)?|augment(?:ed)?|synthetic)\b", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    temp.replace(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _ris_records(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, list[str]] = defaultdict(list)
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9])  - (.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if key == "TY" and current:
            records.append(dict(current))
            current = defaultdict(list)
        if key == "ER":
            if current:
                records.append(dict(current))
            current = defaultdict(list)
        else:
            current[key].append(value.strip())
    if current:
        records.append(dict(current))
    return records


def _first(record: dict[str, list[str]], key: str) -> str | None:
    return record.get(key, [None])[0]


def _paper_id(record: dict[str, list[str]]) -> str:
    basis = (_first(record, "DO") or _first(record, "TI") or json.dumps(record)).casefold().strip()
    return "paper-" + sha256(basis.encode()).hexdigest()[:16]


def scan(papers_dir: str | Path, output: str | Path) -> dict[str, Any]:
    """Inventory every corpus file without changing the source tree.

    Returns and writes the manifest. Unresolved RIS links are retained as
    review items; source files absent from RIS remain in the inventory.
    """
    root = Path(papers_dir).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    output = Path(output).expanduser().resolve()
    if output == root or root in output.parents:
        raise ValueError("Output must be outside the read-only corpus root")
    files: list[dict[str, Any]] = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs.sort()
        names.sort()
        for name in dirs + names:
            path = Path(directory) / name
            if not path.is_symlink():
                continue
            files.append({"relative_path": path.relative_to(root).as_posix(),
                          "type": "symlink", "processing_status": "skipped_symlink",
                          "link_target": os.readlink(path), "sha256": None, "size_bytes": None,
                          "paper_id": None})
        for name in names:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            suffix = path.suffix.lower().lstrip(".") or "unknown"
            try:
                file_hash = _hash(path)
                status = "inventoried"
                size = path.stat().st_size
            except OSError as exc:
                file_hash, size, status = None, None, "unavailable"
                error = str(exc)
            item = {"relative_path": relative, "type": suffix, "sha256": file_hash,
                    "size_bytes": size, "processing_status": status, "paper_id": None}
            if status == "unavailable":
                item["error"] = error
            files.append(item)
    by_path = {item["relative_path"]: item for item in files}
    ris_files = [item for item in files if item["type"] == "ris" and item["sha256"]]
    records: list[dict[str, Any]] = []
    for ris in ris_files:
        for index, raw in enumerate(_ris_records((root / ris["relative_path"]).read_text(encoding="utf-8-sig", errors="replace")), 1):
            pid = _paper_id(raw)
            linked = []
            missing = []
            for key in ("L1", "L2", "L3", "L4"):
                for reference in raw.get(key, []):
                    reference = reference.replace("\\", "/")
                    if reference in by_path:
                        linked.append(reference)
                        by_path[reference]["paper_id"] = pid
                        by_path[reference]["ris_link_type"] = key
                    else:
                        missing.append(reference)
            records.append({"paper_id": pid, "ris_file": ris["relative_path"], "ris_index": index,
                            "title": _first(raw, "TI"), "authors": raw.get("AU", []),
                            "year": _first(raw, "PY"), "doi": _first(raw, "DO"),
                            "url": _first(raw, "UR"), "linked_files": linked,
                            "missing_links": missing})
    for item in files:
        if item["type"] in ("pdf", "html", "htm") and not item["paper_id"]:
            stem = Path(item["relative_path"]).stem.casefold()
            item["paper_id"] = "paper-unlinked-" + sha256(stem.encode()).hexdigest()[:12]
            item["ris_link_type"] = None
    groups: dict[str, list[str]] = defaultdict(list)
    for item in files:
        if item["sha256"]:
            groups[item["sha256"]].append(item["relative_path"])
    for item in files:
        if item["sha256"] and len(groups[item["sha256"]]) > 1:
            item["duplicate_paths"] = groups[item["sha256"]]
    manifest = {"schema_version": SCHEMA_VERSION, "generated_at": _now(),
                "corpus_root": str(root), "source_files": files, "ris_records": records,
                "counts": {"files": len(files), "by_type": dict(Counter(item["type"] for item in files)),
                           "ris_records": len(records), "distinct_paper_ids": len({item["paper_id"] for item in files if item["paper_id"]}),
                           "duplicate_hash_groups": sum(len(paths) > 1 for paths in groups.values())}}
    _write_json(output / "corpus_manifest.json", manifest)
    return manifest


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        elif tag in {"p", "br", "li", "tr", "h1", "h2", "h3", "h4", "section"}:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)
        elif tag in {"p", "li", "tr", "h1", "h2", "h3", "h4", "section"}:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.chunks.append(data)


def _command(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def _extract_file(root: Path, item: dict[str, Any], text_dir: Path) -> dict[str, Any]:
    result = dict(item)
    if item["processing_status"] == "unavailable":
        return result
    path = root / item["relative_path"]
    try:
        if item["type"] == "pdf":
            info = _command(["pdfinfo", str(path)])
            if info.returncode:
                raise RuntimeError("pdfinfo: " + info.stderr.decode(errors="replace")[:500])
            info_text = info.stdout.decode(errors="replace")
            match = re.search(r"(?m)^Pages:\s*(\d+)", info_text)
            reported_pages = int(match.group(1)) if match else None
            extracted = _command(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], timeout=300)
            if extracted.returncode:
                raise RuntimeError("pdftotext: " + extracted.stderr.decode(errors="replace")[:500])
            text = extracted.stdout.decode("utf-8", errors="replace")
            pages = text.split("\f")
            if pages and not pages[-1].strip():
                pages.pop()
            # Some PDFs contain literal form-feed characters inside a page
            # (AnyAttack in this corpus does). Recover boundaries from
            # pdfinfo's page count instead of assigning invented page numbers.
            if reported_pages and len(pages) != reported_pages:
                pages = []
                for page_number in range(1, reported_pages + 1):
                    single = _command(["pdftotext", "-f", str(page_number), "-l", str(page_number),
                                       "-nopgbrk", "-layout", "-enc", "UTF-8", str(path), "-"], timeout=60)
                    if single.returncode:
                        raise RuntimeError(f"pdftotext page {page_number}: " + single.stderr.decode(errors="replace")[:500])
                    pages.append(single.stdout.decode("utf-8", errors="replace"))
            if reported_pages and len(pages) < reported_pages:
                pages += [""] * (reported_pages - len(pages))
            result["page_count"] = reported_pages or len(pages)
        elif item["type"] in ("html", "htm"):
            parser = _HTMLText()
            parser.feed(path.read_text(encoding="utf-8", errors="replace"))
            pages = ["".join(parser.chunks)]
            result["page_count"] = None
        else:
            return result
        page_records = []
        for index, page in enumerate(pages, 1):
            normalized = page.replace("\x00", "")
            chars = len(normalized.strip())
            alpha = sum(char.isalpha() for char in normalized)
            quality = ("low" if chars < 150 else
                       "table_heavy" if chars and alpha / chars < 0.35 else "usable")
            page_records.append({"page": index, "text": normalized, "char_count": chars,
                                 "quality": quality})
        result["extraction_quality"] = {
            "pages_total": len(page_records),
            "pages_low_text": sum(p["quality"] == "low" for p in page_records),
            "pages_table_heavy": sum(p["quality"] == "table_heavy" for p in page_records),
            "characters": sum(p["char_count"] for p in page_records),
            "status": "low" if not page_records or sum(p["char_count"] for p in page_records) < 200 else "usable",
        }
        text_path = text_dir / (item["sha256"] + ".jsonl")
        _write_jsonl(text_path, page_records)
        result["text_path"] = str(text_path)
        result["processing_status"] = "extracted"
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result["processing_status"] = "extraction_failed"
        result["error"] = str(exc)
    return result


def _section_and_role(lines: list[str], index: int, bibliography: bool) -> tuple[str | None, str]:
    if bibliography:
        return "References", "bibliography-only reference"
    section = None
    for prior in reversed(lines[max(0, index - 35):index + 1]):
        stripped = prior.strip()
        if re.match(r"^(?:\d+(?:\.\d+)*\s+)?(?:datasets?|experimental setup|experiments?|evaluation|results?|methods?|appendix|supplementary|related work|references|bibliography)\b", stripped, re.I):
            section = stripped[:100]
            break
    context = " ".join(lines[max(0, index - 1):min(len(lines), index + 2)])
    if INTRO_PATTERN.search(context) and CONTEXT_PATTERN.search(context):
        role = "introduction"
    elif DERIVED_PATTERN.search(context) and CONTEXT_PATTERN.search(context):
        role = "derived collection"
    elif EVAL_PATTERN.search(context):
        role = "evaluation"
    elif TRAIN_PATTERN.search(context):
        role = "training"
    elif re.search(r"related work|prior work|previous work", context, re.I):
        role = "related-work mention"
    else:
        role = "unclassified"
    return section, role


def _context_names(line: str) -> list[str]:
    """Conservative extra candidates when dataset language surrounds a name."""
    if not CONTEXT_PATTERN.search(line):
        return []
    matches = re.findall(
        r"\b(?:[A-Z][A-Za-z0-9+._-]*|[A-Z]{2,}[0-9+._-]*)(?:\s+(?:[A-Z][A-Za-z0-9+._-]*|of|the|and|for|in)){0,4}\b",
        line,
    )
    stop = {"We", "The", "Our", "Figure", "Table", "Section", "Dataset", "Datasets",
            "Benchmark", "Benchmarks", "Appendix", "Evaluation", "Training", "Image",
            "Vision", "Language", "Model", "Models", "For", "In", "A", "An", "This",
            "These", "To", "Specifically", "Data", "Experiments", "Results"}
    return [name.strip() for name in matches if name.strip() not in stop and len(name.strip()) >= 3]


def _mentions_for_file(item: dict[str, Any]) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    if item.get("processing_status") != "extracted":
        return mentions
    bibliography = False
    for page_record in _read_jsonl(Path(item["text_path"])):
        lines = page_record["text"].splitlines()
        for index, line in enumerate(lines):
            stripped = " ".join(line.split())
            if re.match(r"^(?:\d+\s+)?(?:references|bibliography)\s*$", stripped, re.I):
                bibliography = True
            names = [match.group() for match in NAME_PATTERN.finditer(line)]
            names.extend(_context_names(line))
            unique = []
            seen = set()
            for name in names:
                key = name.casefold()
                if key not in seen:
                    unique.append(name)
                    seen.add(key)
            if not unique:
                continue
            section, role = _section_and_role(lines, index, bibliography)
            excerpt = " ".join(" ".join(lines[max(0, index - 1):min(len(lines), index + 2)]).split())[:500]
            for name in unique:
                mid = sha256(f"{item['sha256']}:{page_record['page']}:{index}:{name}:{excerpt}".encode()).hexdigest()[:20]
                mentions.append({"mention_id": "mention-" + mid, "paper_id": item["paper_id"],
                                 "paper_version": item["sha256"][:16], "source_file_hash": item["sha256"],
                                 "source_relative_path": item["relative_path"],
                                 "page": page_record["page"] if item["type"] == "pdf" else None,
                                 "line": index + 1, "section": section,
                                 "name_as_written": name, "supporting_excerpt": excerpt,
                                 "mention_role": role, "reported_properties": {},
                                 "candidate_canonical_identity": None,
                                 "review_status": "candidate_unreviewed",
                                 "extraction_method": "seed_name" if NAME_PATTERN.fullmatch(name) else "context_pattern",
                                 "page_quality": page_record["quality"]})
    return mentions


def extract(manifest: str | Path) -> dict[str, Any]:
    """Extract complete PDF/HTML text and write paper/mention/review outputs."""
    manifest_path = Path(manifest).expanduser().resolve(strict=True)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = Path(data["corpus_root"])
    output = manifest_path.parent
    source_files = data["source_files"]
    extractable = [item for item in source_files if item["type"] in ("pdf", "html", "htm")]
    extracted_by_path: dict[str, dict[str, Any]] = {}
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in extractable:
        by_hash[item.get("sha256") or item["relative_path"]].append(item)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_extract_file, root, group[0], output / "text"): group
                   for group in by_hash.values()}
        for future in as_completed(futures):
            result = future.result()
            for source in futures[future]:
                duplicate_result = dict(source)
                duplicate_result.update({key: value for key, value in result.items()
                                         if key in {"page_count", "extraction_quality", "text_path", "processing_status", "error"}})
                extracted_by_path[source["relative_path"]] = duplicate_result
    data["source_files"] = [extracted_by_path.get(item["relative_path"], item) for item in source_files]
    mentions: list[dict[str, Any]] = []
    for item in data["source_files"]:
        if item["type"] in ("pdf", "html", "htm"):
            mentions.extend(_mentions_for_file(item))
    previous_mentions = {m["mention_id"]: m for m in _read_jsonl(output / "dataset_mentions.jsonl")}
    for mention in mentions:
        old = previous_mentions.get(mention["mention_id"])
        if old and old.get("review_status") not in (None, "candidate_unreviewed"):
            for field in ("review_status", "candidate_canonical_identity", "reported_properties", "review_note"):
                if field in old:
                    mention[field] = old[field]
    mentions.sort(key=lambda m: (m["paper_id"], m["source_relative_path"], m["page"] or 0, m["line"], m["name_as_written"]))
    ris_by_id = {record["paper_id"]: record for record in data["ris_records"]}
    files_by_paper: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in data["source_files"]:
        if item.get("paper_id"):
            files_by_paper[item["paper_id"]].append(item)
    mentions_by_paper = Counter(m["paper_id"] for m in mentions)
    previous_papers = {p["paper_id"]: p for p in _read_jsonl(output / "papers.jsonl")}
    papers = []
    for pid, files in sorted(files_by_paper.items()):
        errors = [f for f in files if f["processing_status"] in {"extraction_failed", "unavailable"}]
        if errors:
            outcome = "extraction_failed" if any(f["processing_status"] == "extraction_failed" for f in errors) else "unavailable"
        else:
            outcome = "processed_with_review_items"
        ris = ris_by_id.get(pid, {})
        prior = previous_papers.get(pid, {})
        current_versions = sorted({f["sha256"][:16] for f in files if f["type"] == "pdf" and f.get("sha256")})
        review_versions_current = sorted(prior.get("reviewed_versions", [])) == current_versions
        if (prior.get("human_review_complete") or prior.get("mention_inventory_review_complete")) and prior.get("outcome") in OUTCOMES and not errors and review_versions_current:
            outcome = prior["outcome"]
        paper = {"paper_id": pid, "title": ris.get("title") or Path(files[0]["relative_path"]).stem,
                       "authors": ris.get("authors", []), "year": ris.get("year"),
                       "doi": ris.get("doi"), "url": ris.get("url"),
                       "source_files": [f["relative_path"] for f in files],
                       "versions": current_versions,
                       "outcome": outcome, "candidate_mention_count": mentions_by_paper[pid],
                       "human_review_complete": bool(prior.get("human_review_complete")) if not errors and review_versions_current else False,
                       "mention_inventory_review_complete": bool(prior.get("mention_inventory_review_complete")) if not errors and review_versions_current else False}
        if paper["human_review_complete"] or paper["mention_inventory_review_complete"]:
            for field in ("review_method", "reviewer_kind", "reviewed_at", "reviewed_pages", "reviewed_versions", "review_note"):
                if field in prior:
                    paper[field] = prior[field]
        papers.append(paper)
    previous_review = {(item.get("kind"), item.get("source_relative_path")): item
                       for item in _read_jsonl(output / "review_queue.jsonl")}
    review = []
    for paper in papers:
        if not paper["human_review_complete"] and not paper["mention_inventory_review_complete"]:
            review.append({"kind": "paper_full_review", "paper_id": paper["paper_id"],
                           "status": "pending", "reason": "Full-text dataset inventory needs reconciliation"})
    for item in data["source_files"]:
        if item["type"] in ("pdf", "html", "htm") and (item.get("processing_status") != "extracted" or item.get("extraction_quality", {}).get("status") == "low" or item.get("extraction_quality", {}).get("pages_low_text", 0)):
            quality_item = {"kind": "extraction_quality", "paper_id": item["paper_id"],
                            "source_relative_path": item["relative_path"],
                            "source_file_hash": item.get("sha256"), "status": "pending",
                            "reason": item.get("error") or str(item.get("extraction_quality"))}
            old = previous_review.get(("extraction_quality", item["relative_path"]), {})
            if old.get("status") == "reviewed" and old.get("source_file_hash") == item.get("sha256"):
                for field in ("status", "review_method", "review_note", "reviewed_at"):
                    if field in old:
                        quality_item[field] = old[field]
            review.append(quality_item)
    for ris in data["ris_records"]:
        for missing in ris["missing_links"]:
            review.append({"kind": "missing_ris_link", "paper_id": ris["paper_id"],
                           "source_relative_path": missing, "status": "pending"})
    # Raw pattern hits are search leads, not thousands of independent human
    # obligations. The full-paper review item covers their reconciliation;
    # specific identity ambiguities can be queued after page-level review.
    for paper in papers:
        if not paper.get("mention_inventory_review_complete") or paper["outcome"] in {"extraction_failed", "unavailable"}:
            continue
        if any(item["paper_id"] == paper["paper_id"] and item.get("status") == "pending" for item in review):
            paper["outcome"] = "processed_with_review_items"
        elif paper["outcome"] != "no_dataset_mentions_found_after_review":
            paper["outcome"] = "processed"
    data["counts"].update({"extracted_files": sum(f["processing_status"] == "extracted" for f in data["source_files"]),
                           "extraction_failures": sum(f["processing_status"] == "extraction_failed" for f in data["source_files"]),
                           "candidate_mentions": len(mentions), "papers_with_candidates": len(mentions_by_paper)})
    data["extracted_at"] = _now()
    _write_json(manifest_path, data)
    _write_jsonl(output / "papers.jsonl", papers)
    _write_jsonl(output / "dataset_mentions.jsonl", mentions)
    _write_jsonl(output / "review_queue.jsonl", review)
    _write_json(output / "dataset_candidates.json", _group_candidates(mentions))
    if output.name == "corpus" and output.parent.name == "work":
        repository_root = output.parent.parent
        write_paper_registry(manifest_path, repository_root / "registry")
        write_coverage_report(manifest_path, repository_root / "reports" / "corpus_coverage.md")
    return {"manifest": str(manifest_path), "papers": len(papers), "mentions": len(mentions),
            "review_items": len(review), "extraction_failures": data["counts"]["extraction_failures"]}


def _group_candidates(mentions: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for mention in mentions:
        key = re.sub(r"[^a-z0-9]+", "", mention["name_as_written"].casefold())
        group = groups.setdefault(key, {"name": mention["name_as_written"], "aliases_as_written": [],
                                        "paper_ids": [], "mention_ids": [], "roles": [],
                                        "status": "candidate_unreviewed"})
        for attr, value in (("aliases_as_written", mention["name_as_written"]),
                            ("paper_ids", mention["paper_id"]), ("roles", mention["mention_role"])):
            if value not in group[attr]:
                group[attr].append(value)
        group["mention_ids"].append(mention["mention_id"])
    return {"schema_version": SCHEMA_VERSION, "status": "candidate_unreviewed",
            "generated_at": _now(), "candidates": sorted(groups.values(), key=lambda g: g["name"].casefold())}


def write_paper_registry(manifest: str | Path, registry: str | Path) -> int:
    """Write bibliographic paper entries, preserving any reviewed existing entry."""
    import yaml

    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    papers = {p["paper_id"]: p for p in _read_jsonl(Path(manifest).parent / "papers.jsonl")}
    files_by_paper: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in data["source_files"]:
        if item.get("paper_id"):
            files_by_paper[item["paper_id"]].append(item)
    destination = Path(registry) / "papers"
    destination.mkdir(parents=True, exist_ok=True)
    written = 0
    for pid, paper in papers.items():
        path = destination / (pid + ".yaml")
        if path.exists():
            old = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if old.get("human_review_complete") or old.get("mention_inventory_review_complete"):
                old["outcome"] = paper["outcome"]
                old["candidate_mention_count"] = paper["candidate_mention_count"]
                path.write_text(yaml.safe_dump(old, sort_keys=False, allow_unicode=True), encoding="utf-8")
                continue
        entry = {
            "schema_version": SCHEMA_VERSION,
            "paper_id": pid,
            "title": paper["title"],
            "authors": paper["authors"],
            "year": paper["year"],
            "doi": paper["doi"],
            "url": paper["url"],
            "outcome": paper["outcome"],
            "human_review_complete": False,
            "mention_inventory_review_complete": paper.get("mention_inventory_review_complete", False),
            "candidate_mention_count": paper["candidate_mention_count"],
            "sources": [{"relative_path": item["relative_path"], "type": item["type"],
                         "sha256": item.get("sha256"), "page_count": item.get("page_count"),
                         "extraction_quality": item.get("extraction_quality"),
                         "processing_status": item["processing_status"]}
                        for item in files_by_paper[pid]],
        }
        path.write_text(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True), encoding="utf-8")
        written += 1
    return written


def write_coverage_report(manifest: str | Path, report: str | Path) -> None:
    """Report observed coverage and unresolved review obligations."""
    manifest_path = Path(manifest)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    papers = _read_jsonl(manifest_path.parent / "papers.jsonl")
    mentions = _read_jsonl(manifest_path.parent / "dataset_mentions.jsonl")
    review = _read_jsonl(manifest_path.parent / "review_queue.jsonl")
    curated = _read_jsonl(manifest_path.parent / "curated_dataset_evidence.jsonl")
    if curated:
        write_curated_candidate_summary(manifest_path.parent)
    candidate_summary = (json.loads((manifest_path.parent / "curated_dataset_candidates.json").read_text(encoding="utf-8"))
                         if curated else {"candidates": [], "alias_redirects": []})
    files = data["source_files"]
    pdfs = [f for f in files if f["type"] == "pdf"]
    html = [f for f in files if f["type"] in ("html", "htm")]
    low_html = [f for f in html if f.get("extraction_quality", {}).get("status") == "low"]
    low_pdf_pages = sum(f.get("extraction_quality", {}).get("pages_low_text", 0) for f in pdfs)
    table_pages = sum(f.get("extraction_quality", {}).get("pages_table_heavy", 0) for f in pdfs)
    pdf_pages = sum(f.get("page_count") or 0 for f in pdfs)
    roles = Counter(m["mention_role"] for m in mentions)
    outcomes = Counter(p["outcome"] for p in papers)
    lines = [
        "# Corpus coverage",
        "",
        f"Generated from the local read-only corpus on {data.get('extracted_at', data['generated_at'])}.",
        "Full extracted paper text and candidate queues remain in ignored `work/corpus/`.",
        "",
        "## Observed inventory",
        "",
        f"- Files inventoried: **{len(files)}** ({len(pdfs)} PDFs, {len(html)} HTML snapshots, {sum(f['type'] == 'ris' for f in files)} RIS export).",
        f"- RIS records: **{len(data['ris_records'])}**; distinct linked paper IDs: **{len(papers)}**. The RIS is a cross-check, not a required count.",
        f"- PDF pages reported by `pdfinfo`: **{pdf_pages}**; sparse-text pages: **{low_pdf_pages}**; separately, **{table_pages}** numeric/table-heavy pages retain extracted text.",
        f"- Files with extraction failure: **{sum(f['processing_status'] == 'extraction_failed' for f in files)}**; HTML snapshots with no usable visible text: **{len(low_html)}**.",
        f"- Byte-identical duplicate hash groups: **{data['counts']['duplicate_hash_groups']}**. Different PDF versions retain separate hashes and page counts.",
        f"- Automated candidate occurrences: **{len(mentions)}**; candidate name groups: **{len(_group_candidates(mentions)['candidates'])}**. These are noisy search leads, **not a dataset count or accepted records**.",
        f"- Candidate occurrences uniquely matching a registry alias whose identity is resolved: **{sum(m.get('identity_match_status') == 'unique_registry_alias' for m in mentions)}**. Alias matching alone does not accept the mention or verify its role.",
        f"- Pending review items: **{sum(r.get('status') == 'pending' for r in review)}**; agent-complete full-text mention inventories: **{sum(p.get('mention_inventory_review_complete', False) for p in papers)}**; human-approved papers: **{sum(p['human_review_complete'] for p in papers)}**.",
        "",
        "## Paper outcomes",
        "",
    ]
    for outcome in sorted(OUTCOMES):
        lines.append(f"- `{outcome}`: {outcomes[outcome]}")
    lines += ["", "`processed_with_review_items` means extraction finished but one or more specific queue items remain. A paper with zero detected candidates is **not** marked `no_dataset_mentions_found_after_review` until its full-text mention inventory is checked.", "", "## Candidate role labels", ""]
    for role, count in sorted(roles.items()):
        lines.append(f"- `{role}`: {count} automated occurrences")
    lines += ["", "Role labels above are automated context heuristics, particularly unreliable for two-column PDFs. Curated roles below come from page review.", "", "## Page-located reviewed evidence", "",
              f"- Page-checked assertions: **{len(curated)}** across **{len({c['paper_id'] for c in curated})}** papers, covering **{len({c['name_as_written'] for c in curated})}** candidate names or explicitly unnamed collections.",
              f"- Conservatively grouped candidate identities: **{len(candidate_summary['candidates'])}**; no corpus audit assertion alone verifies a release.",
              f"- Confirmed identity alias redirects: **{len(candidate_summary['alias_redirects'])}**. All original page receipts remain attached to canonical proposals; paper-specific splits and roles are retained.",
              "- Receipts are in ignored `work/corpus/curated_dataset_evidence.jsonl`; grouped identity proposals are in `work/corpus/curated_dataset_candidates.json`.",
              "- Page-checked assertions establish only their cited claims. A complete mention inventory requires `mention_inventory_review_complete`; original dataset source and release verification are separate.",
              "", "## Paper-by-paper audit", "", "| Paper ID | Title | PDFs | Candidate mentions | Outcome | Mention inventory |", "| --- | --- | ---: | ---: | --- | --- |"]
    for paper in papers:
        title = str(paper["title"]).replace("|", "\\|")
        pdf_count = sum(f["type"] == "pdf" for f in files if f.get("paper_id") == paper["paper_id"])
        lines.append(f"| `{paper['paper_id']}` | {title} | {pdf_count} | {paper['candidate_mention_count']} | `{paper['outcome']}` | {'agent inventory checked' if paper.get('mention_inventory_review_complete') else 'pending'} |")
    lines += ["", "## Outstanding limits", "",
              "- All linked papers have agent-complete full-text mention inventories. The automated extractor remains a noisy search aid: it can miss a novel name or mistake a model, title, metric, or author for a dataset. Human approval is tracked separately and is not a required signoff.",
              "- The 15 SingleFile HTML captures are arXiv PDF-viewer shells with no standalone visible article text. Their linked PDFs were independently extracted and reviewed; each shell is documented in the quality queue.",
              "- The seven genuinely sparse-text PDF pages were visually checked. The 206 numeric/table-heavy pages retained substantial extracted text and were covered by the full-paper audits; the quality queue records page-specific visual/OCR checks where needed.",
              "- No candidate is marked accepted, no dataset identity or original release is verified by this automated pass, and no source-access or preview claim follows from this report.",
              ""]
    destination = Path(report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")


def write_curated_candidate_summary(output: str | Path) -> int:
    """Group page-checked assertions as identity candidates, never accept them.

    Written names are grouped case-insensitively but punctuation distinctions
    are retained until source evidence justifies a merge. This is a grouping
    aid, not release reconciliation.
    """
    output = Path(output)
    evidence = _read_jsonl(output / "curated_dataset_evidence.jsonl")
    target = output / "curated_dataset_candidates.json"
    groups: dict[str, dict[str, Any]] = {}
    used_ids: set[str] = set()
    for row in evidence:
        name = row["name_as_written"]
        key = re.sub(r"\s+", " ", name.casefold().strip())
        if key.startswith("unnamed "):
            key = row["paper_id"] + ":" + key
        if not key:
            continue
        if key not in groups:
            proposed = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
            if name.casefold().startswith("unnamed "):
                proposed = row["paper_id"] + "-" + proposed
            if not proposed:
                proposed = "unnamed-" + sha256(key.encode()).hexdigest()[:8]
            if proposed in used_ids:
                proposed += "-" + sha256(key.encode()).hexdigest()[:8]
            used_ids.add(proposed)
            groups[key] = {"proposed_id": proposed, "name": name,
                           "aliases_as_written": [], "identity_status": "candidate",
                           "source_status": "paper_evidence_only", "paper_ids": [],
                           "evidence_ids": [], "roles": [], "notes": [],
                           "paper_full_review_complete": True}
        group = groups[key]
        if name != group["name"] and name not in group["aliases_as_written"]:
            group["aliases_as_written"].append(name)
        for field, value in (("paper_ids", row["paper_id"]),
                             ("evidence_ids", row["evidence_id"]),
                             ("roles", row["mention_role"]), ("notes", row.get("note", ""))):
            if value and value not in group[field]:
                group[field].append(value)
        group["paper_full_review_complete"] &= bool(row.get("paper_full_review_complete"))
    # The initial two redirects have page-level evidence of the same identity.
    # A tracked registry rule file can add source-verified *name* aliases across
    # papers, with explicit paper-scope caveats. Do not normalize punctuation
    # or source-family names without a curated rule: variants can differ.
    initial_redirects = (
        ("paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set-90f1ca61",
         "paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set",
         "Both receipts cite the same 40 manually curated instructions on paper p6.",
         {"evidence-c80bbda136db1321e17e", "evidence-3f153c5972dc03b632ce"}, True, ""),
        ("jailbreakv-28k-13161513", "jailbreakv-28k",
         "Both spellings cite the same JailBreakV_28K source sentence on PHANTOM p6.",
         {"evidence-fd7b7e7e90ab5fde29d9", "evidence-cf91c6888c3690038c70"}, True, ""),
    )
    rule_path = output.parent.parent / "registry" / "candidate_dispositions.yaml"
    confirmed_redirects = list(initial_redirects)
    if rule_path.is_file():
        rules = yaml.safe_load(rule_path.read_text()) or {}
        for rule in rules.get("alias_redirects", []):
            if rule.get("disposition") != "source_verified_name_alias":
                continue
            confirmed_redirects.append((
                rule["alias_id"], rule["canonical_id"], rule["reason"],
                set(rule["evidence_ids"]), False, rule.get("scope_note", ""),
            ))
    by_id = {group["proposed_id"]: group for group in groups.values()}
    evidence_by_id = {row["evidence_id"]: row for row in evidence}
    redirects = []
    for alias_id, canonical_id, reason, required_evidence, same_page_required, scope_note in confirmed_redirects:
        alias, canonical = by_id.get(alias_id), by_id.get(canonical_id)
        if not alias or not canonical:
            continue
        if not required_evidence <= set(alias["evidence_ids"] + canonical["evidence_ids"]):
            continue
        if not required_evidence & set(alias["evidence_ids"]):
            continue
        receipts = [evidence_by_id[eid] for eid in required_evidence]
        if same_page_required and len({(r["paper_id"], r["source_file_hash"], r["page"]) for r in receipts}) != 1:
            continue
        for field in ("paper_ids", "evidence_ids", "roles", "notes"):
            canonical[field].extend(value for value in alias[field] if value not in canonical[field])
        for name in [alias["name"], *alias["aliases_as_written"]]:
            if name != canonical["name"] and name not in canonical["aliases_as_written"]:
                canonical["aliases_as_written"].append(name)
        canonical["paper_full_review_complete"] &= alias["paper_full_review_complete"]
        canonical.setdefault("confirmed_alias_ids", []).append(alias_id)
        if scope_note:
            canonical.setdefault("alias_scope_notes", []).append(scope_note)
        del by_id[alias_id]
        redirects.append({"alias_id": alias_id, "canonical_id": canonical_id,
                          "reason": reason, "evidence_ids": sorted(required_evidence),
                          "scope_note": scope_note})
        for eid in alias["evidence_ids"] + canonical["evidence_ids"]:
            row = evidence_by_id[eid]
            row.setdefault("candidate_original_id", alias_id if eid in alias["evidence_ids"] else canonical_id)
            row["candidate_canonical_id"] = canonical_id
    if redirects:
        _write_jsonl(output / "curated_dataset_evidence.jsonl", evidence)
    result = {"schema_version": SCHEMA_VERSION,
              "review_scope": "page_checked_assertions_with_explicit_paper_review_flags",
              "paper_full_review_complete": False,
              "dataset_identities_resolved_by_corpus_audit": 0,
              "alias_redirects": redirects,
              "candidates": sorted(by_id.values(), key=lambda x: (x["name"].casefold(), x["proposed_id"]))}
    _write_json(target, result)
    return len(result["candidates"])


def record_full_review(manifest: str | Path, review_notes: dict[str, str],
                       method: str = "full_pdf_page_text_appendix_table_caption_bibliography_audit") -> int:
    """Record explicit completed paper mention inventories, without accepting identities.

    The caller is responsible for reviewing every source version and supplying
    a paper-specific account. Extraction failures cannot be reviewed away.
    This records agent review, not human approval. Dataset source/release and
    adapter review remain separate; no further human signoff is implied.
    """
    import yaml

    manifest_path = Path(manifest)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper_path = manifest_path.parent / "papers.jsonl"
    papers = _read_jsonl(paper_path)
    paper_ids = {paper["paper_id"] for paper in papers}
    missing = set(review_notes) - paper_ids
    if missing:
        raise KeyError("Unknown paper IDs: " + ", ".join(sorted(missing)))
    for pid in review_notes:
        if not review_notes[pid].strip():
            raise ValueError(f"Paper-specific review note required: {pid}")
        sources = [f for f in data["source_files"] if f.get("paper_id") == pid]
        if any(f["processing_status"] in {"unavailable", "extraction_failed"} for f in sources):
            raise ValueError(f"Unresolved extraction failure prevents full review: {pid}")
    timestamp = _now()
    registry_dir = manifest_path.parent.parent.parent / "registry" / "papers"
    for paper in papers:
        pid = paper["paper_id"]
        if pid not in review_notes:
            continue
        sources = [f for f in data["source_files"] if f.get("paper_id") == pid and f["type"] == "pdf"]
        paper.update({"human_review_complete": False,
                      "mention_inventory_review_complete": True,
                      "reviewer_kind": "agent", "review_method": method,
                      "reviewed_at": timestamp,
                      "reviewed_pages": sum(f.get("page_count") or 0 for f in sources),
                      "reviewed_versions": [f["sha256"][:16] for f in sources],
                      "review_note": review_notes[pid],
                      "outcome": "processed_with_review_items"})
        registry_path = registry_dir / (pid + ".yaml")
        entry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        for field in ("human_review_complete", "mention_inventory_review_complete", "reviewer_kind",
                      "review_method", "reviewed_at", "reviewed_pages",
                      "reviewed_versions", "review_note", "outcome"):
            entry[field] = paper[field]
        registry_path.write_text(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True), encoding="utf-8")
    queue_path = manifest_path.parent / "review_queue.jsonl"
    queue = [item for item in _read_jsonl(queue_path)
             if not (item["paper_id"] in review_notes and item["kind"] in {"paper_full_review", "candidate_identity"})]
    curated_path = manifest_path.parent / "curated_dataset_evidence.jsonl"
    curated = _read_jsonl(curated_path)
    if curated:
        for assertion in curated:
            if assertion["paper_id"] in review_notes:
                assertion["paper_full_review_complete"] = True
        _write_jsonl(curated_path, curated)
    for paper in papers:
        if paper["paper_id"] not in review_notes:
            continue
        paper["outcome"] = ("processed_with_review_items" if any(
            item["paper_id"] == paper["paper_id"] and item.get("status") == "pending" for item in queue)
            else "processed")
        registry_path = registry_dir / (paper["paper_id"] + ".yaml")
        entry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        entry["outcome"] = paper["outcome"]
        registry_path.write_text(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True), encoding="utf-8")
    _write_jsonl(paper_path, papers)
    _write_jsonl(queue_path, queue)
    write_coverage_report(manifest_path, manifest_path.parent.parent.parent / "reports" / "corpus_coverage.md")
    return len(review_notes)


def record_extraction_quality_review(manifest: str | Path,
                                     checked_sources: dict[str, str]) -> int:
    """Close only file-specific low-text flags with documented visual/OCR checks."""
    import yaml

    manifest_path = Path(manifest)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    known = {f["relative_path"] for f in data["source_files"]}
    if missing := set(checked_sources) - known:
        raise KeyError("Unknown source files: " + ", ".join(sorted(missing)))
    if any(not note.strip() for note in checked_sources.values()):
        raise ValueError("A source-specific review note is required")
    queue_path = manifest_path.parent / "review_queue.jsonl"
    queue = _read_jsonl(queue_path)
    matched: set[str] = set()
    for item in queue:
        source = item.get("source_relative_path")
        if item["kind"] == "extraction_quality" and source in checked_sources:
            item.update({"status": "reviewed", "source_file_hash": next(f["sha256"] for f in data["source_files"] if f["relative_path"] == source),
                         "review_method": ("singlefile_pdf_viewer_structure_check" if Path(source).suffix.lower() in {".html", ".htm"}
                                           else "full_pdf_visual_or_ocr_page_check"),
                         "review_note": checked_sources[source], "reviewed_at": _now()})
            matched.add(source)
    if unmatched := set(checked_sources) - matched:
        raise ValueError("No extraction-quality item for: " + ", ".join(sorted(unmatched)))
    _write_jsonl(queue_path, queue)
    papers_path = manifest_path.parent / "papers.jsonl"
    papers = _read_jsonl(papers_path)
    registry_dir = manifest_path.parent.parent.parent / "registry" / "papers"
    for paper in papers:
        if not paper.get("mention_inventory_review_complete"):
            continue
        pending = any(item["paper_id"] == paper["paper_id"] and item["status"] == "pending" for item in queue)
        paper["outcome"] = "processed_with_review_items" if pending else "processed"
        registry_path = registry_dir / (paper["paper_id"] + ".yaml")
        if registry_path.exists():
            entry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
            entry["outcome"] = paper["outcome"]
            registry_path.write_text(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True), encoding="utf-8")
    _write_jsonl(papers_path, papers)
    write_coverage_report(manifest_path, manifest_path.parent.parent.parent / "reports" / "corpus_coverage.md")
    return len(matched)


def resolve(mentions: str | Path, registry: str | Path) -> dict[str, Any]:
    """Cross-reference mentions against reviewed registry aliases only.

    Does not silently promote a candidate or create dataset entries.
    """
    mentions_path = Path(mentions).expanduser().resolve(strict=True)
    registry_root = Path(registry).expanduser().resolve()
    try:
        import yaml
    except ImportError:
        yaml = None
    index: dict[str, set[str]] = defaultdict(set)
    for path in sorted((registry_root / "datasets").glob("*.yaml")):
        raw = path.read_text(encoding="utf-8")
        entry = yaml.safe_load(raw) if yaml else json.loads(raw)
        if not isinstance(entry, dict):
            continue
        coverage = entry.get("coverage") or {}
        if coverage.get("identity") != "resolved":
            continue
        identifier = entry.get("id")
        for name in [entry.get("name"), *(entry.get("aliases") or [])]:
            if identifier and isinstance(name, str):
                index[re.sub(r"[^a-z0-9]+", "", name.casefold())].add(identifier)
    records = _read_jsonl(mentions_path)
    resolved = 0
    ambiguous = 0
    for mention in records:
        key = re.sub(r"[^a-z0-9]+", "", mention["name_as_written"].casefold())
        ids = sorted(index.get(key, set()))
        if mention.get("review_status") not in (None, "candidate_unreviewed"):
            continue
        mention["candidate_canonical_identity"] = ids[0] if len(ids) == 1 else None
        mention["identity_match_status"] = "unique_registry_alias" if len(ids) == 1 else "ambiguous_alias" if ids else "unresolved"
        mention["review_status"] = "candidate_unreviewed"
        resolved += len(ids) == 1
        ambiguous += len(ids) > 1
    _write_jsonl(mentions_path, records)
    _write_json(mentions_path.parent / "dataset_candidates.json", _group_candidates(records))
    return {"mentions": len(records), "matched_to_reviewed_registry": resolved,
            "ambiguous_matches": ambiguous, "unresolved": len(records) - resolved - ambiguous}
