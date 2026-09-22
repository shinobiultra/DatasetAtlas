import json
from pathlib import Path

import yaml

from dataset_atlas.corpus.pipeline import (
    _mentions_for_file, extract, record_full_review, resolve, scan,
    write_curated_candidate_summary,
)


def test_scan_accounts_for_copies_ris_links_and_external_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "papers"
    root.mkdir()
    (root / "a.pdf").write_bytes(b"fake-pdf")
    (root / "b.pdf").write_bytes(b"fake-pdf")
    (root / "outside.html").symlink_to(tmp_path / "outside.html")
    (root / "library.ris").write_text(
        "TY  - JOUR\nTI  - Example paper\nDO  - 10.0/example\nL1  - a.pdf\nER  -\n",
        encoding="utf-8",
    )
    manifest = scan(root, tmp_path / "out")
    assert manifest["counts"]["files"] == 4
    assert manifest["counts"]["duplicate_hash_groups"] == 1
    files = {entry["relative_path"]: entry for entry in manifest["source_files"]}
    assert files["a.pdf"]["paper_id"] == manifest["ris_records"][0]["paper_id"]
    assert files["b.pdf"]["paper_id"].startswith("paper-unlinked-")
    assert files["a.pdf"]["duplicate_paths"] == ["a.pdf", "b.pdf"]
    assert files["outside.html"]["processing_status"] == "skipped_symlink"
    assert files["outside.html"]["sha256"] is None


def test_extract_keeps_failure_distinct_from_no_mentions(tmp_path: Path) -> None:
    root = tmp_path / "papers"
    root.mkdir()
    (root / "broken.pdf").write_bytes(b"not really a PDF")
    scan(root, tmp_path / "out")
    result = extract(tmp_path / "out" / "corpus_manifest.json")
    paper = json.loads((tmp_path / "out" / "papers.jsonl").read_text().strip())
    assert result["extraction_failures"] == 1
    assert paper["outcome"] == "extraction_failed"
    assert paper["human_review_complete"] is False


def test_mentions_keep_page_hash_excerpt_and_bibliography_role(tmp_path: Path) -> None:
    text = tmp_path / "pages.jsonl"
    text.write_text(
        json.dumps({"page": 1, "text": "We evaluate on ImageNet dataset.\nReferences\nImageNet dataset paper.", "quality": "usable"}) + "\n",
        encoding="utf-8",
    )
    source = {"paper_id": "paper-example", "sha256": "0" * 64,
              "relative_path": "example.pdf", "type": "pdf",
              "processing_status": "extracted", "text_path": str(text)}
    mentions = _mentions_for_file(source)
    assert len(mentions) == 2
    assert mentions[0]["paper_version"] == "0" * 16
    assert mentions[0]["page"] == 1
    assert "ImageNet" in mentions[0]["supporting_excerpt"]
    assert mentions[1]["mention_role"] == "bibliography-only reference"
    assert all(mention["review_status"] == "candidate_unreviewed" for mention in mentions)


def test_resolve_uses_reviewed_registry_identity_without_accepting_mention(tmp_path: Path) -> None:
    mentions = tmp_path / "mentions.jsonl"
    mentions.write_text(json.dumps({"mention_id": "m1", "paper_id": "p1", "mention_role": "unclassified",
                                   "name_as_written": "ImageNet", "review_status": "candidate_unreviewed"}) + "\n")
    datasets = tmp_path / "registry" / "datasets"
    datasets.mkdir(parents=True)
    (datasets / "imagenet.yaml").write_text(yaml.safe_dump({
        "id": "imagenet-1k", "name": "ImageNet", "coverage": {"identity": "resolved"},
    }))
    result = resolve(mentions, tmp_path / "registry")
    row = json.loads(mentions.read_text().strip())
    assert result["matched_to_reviewed_registry"] == 1
    assert row["candidate_canonical_identity"] == "imagenet-1k"
    assert row["review_status"] == "candidate_unreviewed"


def test_agent_full_review_is_distinct_from_human_approval(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    root = repo / "papers"
    root.mkdir(parents=True)
    (root / "paper.html").write_text("<html><body>We evaluate on ImageNet.</body></html>")
    output = repo / "work" / "corpus"
    scan(root, output)
    extract(output / "corpus_manifest.json")
    paper = json.loads((output / "papers.jsonl").read_text().strip())
    pid = paper["paper_id"]
    assert record_full_review(output / "corpus_manifest.json", {pid: "Page text and source checked."}) == 1
    paper = json.loads((output / "papers.jsonl").read_text().strip())
    assert paper["mention_inventory_review_complete"] is True
    assert paper["reviewer_kind"] == "agent"
    assert paper["human_review_complete"] is False
    assert paper["outcome"] == "processed_with_review_items"
    queue = [json.loads(line) for line in (output / "review_queue.jsonl").read_text().splitlines()]
    assert not any(item["kind"] == "paper_full_review" for item in queue)
    assert any(item["kind"] == "extraction_quality" for item in queue)


def test_confirmed_candidate_redirects_keep_both_page_receipts(tmp_path: Path) -> None:
    rows = [
        ("paper-12e8bd34b4a2f2a8", "unnamed harmful-instruction evaluation set",
         "evidence-3f153c5972dc03b632ce", "evaluation"),
        ("paper-12e8bd34b4a2f2a8", "unnamed harmful instruction evaluation set",
         "evidence-c80bbda136db1321e17e", "human evaluation"),
        ("paper-2df1203e2d3767bb", "JailBreakV-28K",
         "evidence-cf91c6888c3690038c70", "source data"),
        ("paper-2df1203e2d3767bb", "JailBreakV_28K",
         "evidence-fd7b7e7e90ab5fde29d9", "harmful intent source"),
        # An unrelated punctuation variant must remain separate.
        ("paper-other", "JailBreakV 28K", "evidence-other", "citation"),
    ]
    evidence = [{"paper_id": pid, "name_as_written": name, "evidence_id": eid,
                 "mention_role": role, "paper_full_review_complete": True,
                 "source_file_hash": pid, "page": 6} for pid, name, eid, role in rows]
    path = tmp_path / "curated_dataset_evidence.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in evidence), encoding="utf-8")
    assert write_curated_candidate_summary(tmp_path) == 3
    result = json.loads((tmp_path / "curated_dataset_candidates.json").read_text())
    assert len(result["alias_redirects"]) == 2
    groups = {row["proposed_id"]: row for row in result["candidates"]}
    harmful = groups["paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set"]
    assert len(harmful["evidence_ids"]) == 2
    assert set(harmful["roles"]) == {"evaluation", "human evaluation"}
    jailbreak = groups["jailbreakv-28k"]
    assert set(jailbreak["evidence_ids"]) == {
        "evidence-cf91c6888c3690038c70", "evidence-fd7b7e7e90ab5fde29d9"}
    assert "JailBreakV_28K" in jailbreak["aliases_as_written"]
    assert "jailbreakv-28k-13161513" not in groups
    assert any(group["name"] == "JailBreakV 28K" for group in groups.values())
    after = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(after) == 5
    assert after[3]["candidate_original_id"] == "jailbreakv-28k-13161513"
    assert after[3]["candidate_canonical_id"] == "jailbreakv-28k"
    assert "candidate_canonical_id" not in after[4]
    assert write_curated_candidate_summary(tmp_path) == 3
