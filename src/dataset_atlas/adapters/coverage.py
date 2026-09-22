"""Generate the coverage matrix from the validated local registry."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from dataset_atlas.models import Dataset


def sync_curated_candidates(candidate_path: Path, evidence_path: Path,
                            registry_dir: Path) -> int:
    """Account for page-audited identities without promoting them to verified releases."""
    candidates = json.loads(candidate_path.read_text(encoding="utf-8"))["candidates"]
    dispositions_path = registry_dir.parent / "candidate_dispositions.yaml"
    dispositions = (yaml.safe_load(dispositions_path.read_text(encoding="utf-8"))
                    if dispositions_path.is_file() else {})
    excluded_ids = {item["id"] for item in dispositions.get("excluded_from_dataset_catalogue", [])}
    excluded_ids.update(item["alias_id"] for item in dispositions.get("alias_redirects", []))
    evidence = {row["evidence_id"]: row for row in
                (json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines())}
    registry_dir.mkdir(parents=True, exist_ok=True)
    changed = 0
    overlay_bases = {"coco-gender": "coco", "cocogender": "coco",
                     "facet": "Segment Anything 1 Billion",
                     "miap": "OpenImages", "phase": "Conceptual Captions"}
    for item in candidates:
        dataset_id = item["proposed_id"]
        if dataset_id in excluded_ids:
            continue
        path = registry_dir / f"{dataset_id}.yaml"
        receipts = []
        for evidence_id in item["evidence_ids"]:
            row = evidence[evidence_id]
            receipts.append({"kind": "corpus_mention", "evidence_id": evidence_id,
                             "paper_id": row["paper_id"],
                             "source_file_hash": row["source_file_hash"],
                             "page": row["page"], "role": row["mention_role"],
                             "excerpt": row["supporting_excerpt"],
                             "review_scope": row["review_scope"],
                             "paper_full_review_complete": bool(row.get("paper_full_review_complete", False))})
        if item.get("paper_source_url_claim"):
            receipts.append({"kind": "paper_source_claim", "url": item["paper_source_url_claim"],
                             "status": "unverified"})
        if path.exists():
            current = Dataset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            # Release, adapter, rights, and source research are curator-owned
            # even while the identity is still a candidate. Merge only paper
            # receipts and written aliases; never reset researched metadata.
            data = current.model_dump(mode="python")
            data["paper_ids"] = list(dict.fromkeys(data["paper_ids"] + item["paper_ids"]))
            data["aliases"] = list(dict.fromkeys(data["aliases"] + item["aliases_as_written"]))
            by_id = {r.get("evidence_id"): r for r in data["evidence"] if r.get("evidence_id")}
            source_claims = {r.get("url") for r in data["evidence"] if r.get("kind") == "paper_source_claim"}
            for receipt in receipts:
                evidence_id = receipt.get("evidence_id")
                if evidence_id and evidence_id in by_id:
                    by_id[evidence_id].update(receipt)
                elif evidence_id:
                    data["evidence"].append(receipt)
                    by_id[evidence_id] = receipt
                elif receipt.get("kind") == "paper_source_claim" and receipt.get("url") not in source_claims:
                    data["evidence"].append(receipt)
                    source_claims.add(receipt["url"])
            if dataset_id in overlay_bases and not any(
                    r.get("type") == "annotation_overlay_of" and r.get("target") == overlay_bases[dataset_id]
                    for r in data["relationships"]):
                data["relationships"].append({"type": "annotation_overlay_of",
                                              "target": overlay_bases[dataset_id],
                                              "status": "paper_claim_only"})
            if data != current.model_dump(mode="python"):
                Dataset.model_validate(data)
                path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
                changed += 1
            continue
        data = {
            "schema_version": "1.0", "id": dataset_id, "name": item["name"],
            "aliases": item["aliases_as_written"],
            "description": "Mention candidate from a focused page audit; the evidence receipts distinguish direct use, comparison, related-work, and citation-only roles. Original source, release, and rights still require independent verification.",
            "paper_ids": item["paper_ids"], "release": "unresolved", "adapter": "structured",
            "adapter_config": {},
            "coverage": {"identity": "candidate", "source": "unverified",
                         "access": "unverified", "adapter": "not_started", "preview": "none",
                         "complete_data": "unimplemented", "publication": "not_reviewed",
                         "preview_count": 0, "unit": "example",
                         "blockers": ["Original release identity and rights need verification.",
                                      "Adapter and preview are not implemented."]},
            "rights": {"records": "not_reviewed", "annotations": "not_reviewed",
                       "images": "not_reviewed"}, "evidence": receipts,
        }
        if dataset_id in overlay_bases:
            data["relationships"] = [{"type": "annotation_overlay_of",
                                      "target": overlay_bases[dataset_id],
                                      "status": "paper_claim_only"}]
        Dataset.model_validate(data)
        rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        if not path.exists() or path.read_text(encoding="utf-8") != rendered:
            path.write_text(rendered, encoding="utf-8")
            changed += 1
    return changed


def write_coverage_csv(registry_dir: Path, target: Path) -> int:
    fields = ["dataset_id", "name", "identity", "source", "access", "adapter",
              "preview", "preview_count", "total_count", "unit", "complete_data",
              "publication", "blocker_type", "blockers", "source_url", "release",
              "snapshot_id", "paper_ids", "evidence_count"]
    rows = []
    for path in sorted(registry_dir.glob("*.yaml")):
        dataset = Dataset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        c = dataset.coverage
        kinds = []
        if c.identity == "candidate":
            kinds.append("identity_review")
        if c.source == "unverified":
            kinds.append("source_research")
        if c.access == "gated":
            kinds.append("external_access_gate")
        elif c.access == "unverified":
            kinds.append("access_research")
        if c.adapter in {"not_started", "unimplemented"}:
            kinds.append("implementation_gap")
        if c.complete_data == "requires_preparation":
            kinds.append("full_release_preparation")
        elif c.complete_data in {"partial", "partial_media"}:
            kinds.append("partial_media_access")
        if c.publication == "metadata_only":
            kinds.append("publication_review")
        blocker_type = " | ".join(kinds) or "none"
        rows.append({"dataset_id": dataset.id, "name": dataset.name,
                     "identity": c.identity, "source": c.source, "access": c.access,
                     "adapter": c.adapter, "preview": c.preview,
                     "preview_count": c.preview_count, "total_count": c.total_count or "",
                     "unit": c.unit, "complete_data": c.complete_data,
                     "publication": c.publication, "blocker_type": blocker_type,
                     "blockers": " | ".join(c.blockers), "source_url": dataset.source_url or "",
                     "release": dataset.release, "snapshot_id": dataset.snapshot_id,
                     "paper_ids": " | ".join(dataset.paper_ids), "evidence_count": len(dataset.evidence)})
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
