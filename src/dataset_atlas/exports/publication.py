"""Build a static catalogue only from explicitly approved local preview packs."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from pydantic import ValidationError

from dataset_atlas.models import Artifact, Dataset, Pack, Record
from dataset_atlas.queries.results import attach_results

from .security import MAX_EXCHANGE_BYTES, ExchangeError, compact_json, contained_file, digest, read_json, scan_public, validate_image

PublicationError = ExchangeError
_APPROVED = {"approved", "public", "redistributable"}
_POLICY_KEYS = {"records", "annotations", "derived_artifacts", "derived_artifact_ids", "derived_artifacts_sha256", "media_asset_ids", "sensitive_media_reviewed"}
_MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MAX_MEDIA_BYTES = 10_000_000


@dataclass(frozen=True)
class PublicationReport:
    catalogue_count: int
    published_packs: tuple[str, ...]
    metadata_only: tuple[str, ...]
    total_bytes: int
    output_dir: Path


def _registry(registry_dir: Path) -> list[Dataset]:
    directory = Path(registry_dir) / "datasets"
    datasets: list[Dataset] = []
    if not directory.exists():
        return datasets
    for path in sorted([*directory.glob("*.yaml"), *directory.glob("*.yml"), *directory.glob("*.json")]):
        if path.is_symlink() or path.stat().st_size > 1_000_000:
            raise PublicationError(f"Unsafe registry file: {path.name}")
        try:
            value = json.loads(path.read_text()) if path.suffix == ".json" else yaml.safe_load(path.read_text())
            dataset = Dataset.model_validate(value)
        except (ValueError, ValidationError, yaml.YAMLError) as exc:
            raise PublicationError(f"Invalid registry dataset: {path.name}") from exc
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", dataset.id):
            raise PublicationError(f"Unsafe dataset ID: {dataset.id}")
        datasets.append(dataset)
    if len({dataset.id for dataset in datasets}) != len(datasets):
        raise PublicationError("Duplicate dataset ID in registry")
    return datasets


def _profile(path: Path, ids: set[str]) -> dict[str, dict[str, Any]]:
    value = read_json(Path(path), limit=1_000_000)
    if not isinstance(value, dict) or value.get("schema_version") != "1.0" or not isinstance(value.get("datasets"), dict):
        raise PublicationError("Invalid publication profile")
    if set(value) != {"schema_version", "datasets"}:
        raise PublicationError("Unknown publication profile fields")
    if set(value["datasets"]) - ids:
        raise PublicationError("Publication profile names an unregistered dataset")
    policies: dict[str, dict[str, Any]] = {}
    for dataset_id, policy in value["datasets"].items():
        if not isinstance(policy, dict) or set(policy) - _POLICY_KEYS:
            raise PublicationError(f"Invalid publication policy: {dataset_id}")
        for key in ("records", "annotations", "derived_artifacts", "sensitive_media_reviewed"):
            if key in policy and not isinstance(policy[key], bool):
                raise PublicationError(f"Publication policy {key} must be boolean: {dataset_id}")
        media_ids = policy.get("media_asset_ids", [])
        if not isinstance(media_ids, list) or any(not isinstance(item, str) or not item for item in media_ids) or len(set(media_ids)) != len(media_ids):
            raise PublicationError(f"Invalid media asset allowlist: {dataset_id}")
        if not policy.get("records", False) and (policy.get("annotations", False) or policy.get("derived_artifacts", False) or media_ids):
            raise PublicationError(f"Records must be approved before annotations, results, or media: {dataset_id}")
        artifact_ids = policy.get("derived_artifact_ids", [])
        if not isinstance(artifact_ids, list) or any(not isinstance(item, str) or not item for item in artifact_ids) or len(set(artifact_ids)) != len(artifact_ids):
            raise PublicationError(f"Invalid derived artifact allowlist: {dataset_id}")
        if policy.get("derived_artifacts", False):
            checksum = policy.get("derived_artifacts_sha256")
            if not artifact_ids or not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
                raise PublicationError(f"Derived artifacts need IDs and a pinned SHA-256: {dataset_id}")
        elif artifact_ids or policy.get("derived_artifacts_sha256"):
            raise PublicationError(f"Derived artifact IDs need approval: {dataset_id}")
        policies[dataset_id] = policy
    return policies


def _public_dataset(dataset: Dataset) -> dict[str, Any]:
    # Construct explicitly; registry evidence, adapter config and paper text never enter output.
    value = dataset.model_dump(mode="json", exclude={"adapter_config", "evidence", "relationships"})
    value["adapter_config"] = {}
    value["evidence"] = []
    # Publish navigable relationships without private alias receipts or excerpts.
    relationship_keys = {"type", "target", "target_id", "status", "scope"}
    value["relationships"] = [
        {key: item for key, item in relation.items() if key in relationship_keys and isinstance(item, str)}
        for relation in dataset.relationships
        if isinstance(relation, dict) and (relation.get("target") or relation.get("target_id"))
    ]
    source_url = value.get("source_url")
    if source_url:
        parts = urlsplit(source_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise PublicationError(f"Unsafe source URL: {dataset.id}")
    scan_public({key: item for key, item in value.items() if key not in {"adapter_config", "evidence"}}, label=f"catalogue.{dataset.id}")
    return value


def _require_right(dataset: Dataset, category: str) -> None:
    if dataset.rights.get(category, "").strip().lower() not in _APPROVED:
        raise PublicationError(f"{dataset.id}: {category} publication right is not approved")


def _load_pack(path: Path, dataset: Dataset) -> Pack:
    try:
        pack = Pack.model_validate(read_json(path))
    except ValidationError as exc:
        raise PublicationError(f"Invalid pack schema: {dataset.id}") from exc
    if pack.dataset.id != dataset.id or pack.dataset.release != dataset.release or pack.dataset.snapshot_id != dataset.snapshot_id:
        raise PublicationError(f"Pack identity differs from registry: {dataset.id}")
    if pack.population_scope != "preview" or not pack.sampling:
        raise PublicationError(f"Public pack needs explicit preview scope and sampling: {dataset.id}")
    ids = [record.id for record in pack.records]
    if len(ids) != len(set(ids)):
        raise PublicationError(f"Duplicate record IDs: {dataset.id}")
    for record in pack.records:
        if record.dataset_id != dataset.id or record.snapshot_id != dataset.snapshot_id or record.release_id != dataset.release:
            raise PublicationError(f"Record identity differs from pack: {record.id}")
    for member, expected in pack.checksums.items():
        file = contained_file(path.parent, member)
        if file.stat().st_size > MAX_EXCHANGE_BYTES or digest(file.read_bytes()) != expected:
            raise PublicationError(f"Pack checksum mismatch: {member}")
    return pack


def _attach_approved_artifacts(pack: Pack, source_dir: Path, policy: dict[str, Any]) -> Pack:
    if pack.artifacts:
        raise PublicationError("Source pack must keep derived artifacts in a separate approved overlay")
    overlay = source_dir / "analysis-artifacts.json"
    if overlay.is_symlink() or not overlay.is_file() or overlay.stat().st_size > 20_000_000:
        raise PublicationError("Approved analysis overlay is missing or oversized")
    if digest(overlay.read_bytes()) != policy["derived_artifacts_sha256"]:
        raise PublicationError("Approved analysis overlay checksum mismatch")
    values = read_json(overlay, limit=20_000_000)
    if not isinstance(values, list):
        raise PublicationError("Analysis overlay must be an array")
    try:
        artifacts = [Artifact.model_validate(value) for value in values]
    except ValidationError as exc:
        raise PublicationError("Invalid analysis artifact schema") from exc
    if {artifact.id for artifact in artifacts} != set(policy["derived_artifact_ids"]) or len(artifacts) != len(policy["derived_artifact_ids"]):
        raise PublicationError("Analysis artifact IDs do not match publication allowlist")
    record_ids = {record.id for record in pack.records}
    for artifact in artifacts:
        if artifact.unit != "example" or artifact.snapshot_ids != [pack.dataset.snapshot_id] or not set(artifact.ids).issubset(record_ids) or artifact.files:
            raise PublicationError(f"Unsafe analysis artifact identity or file reference: {artifact.id}")
        if artifact.coverage.get("status") != "completed" or artifact.coverage.get("failed") or artifact.coverage.get("completed") != len(artifact.ids):
            raise PublicationError(f"Incomplete analysis artifact: {artifact.id}")
        items = artifact.data.get("items")
        if not isinstance(items, list) or len(items) != len(artifact.ids) or {item.get("id") for item in items if isinstance(item, dict) and item.get("status") == "completed"} != set(artifact.ids):
            raise PublicationError(f"Analysis item coverage differs from artifact IDs: {artifact.id}")
        points = artifact.data.get("points", [])
        if not isinstance(points, list) or any(not isinstance(point, dict) or point.get("id") not in record_ids for point in points):
            raise PublicationError(f"Analysis point identity differs from pack: {artifact.id}")
        scan_public(artifact.model_dump(mode="json"), label=f"artifact.{artifact.id}")
    return attach_results(pack, artifacts)


def _public_record(record: Record, *, annotations: bool, derived: bool, media_ids: set[str], source_dir: Path, source_checksums: dict[str, str], dataset_id: str, media: dict[str, bytes]) -> dict[str, Any]:
    value = record.model_dump(mode="json")
    value["human"] = {}
    value["source"] = value["source"] if annotations else {}
    value["prediction"] = value["prediction"] if derived else {}
    value["relations"] = value["relations"] if annotations else []
    value["annotations"] = [item for item in value["annotations"] if (item["namespace"] == "source" and annotations) or (item["namespace"] == "prediction" and derived)]
    for asset in value["assets"]:
        original_uri = asset.get("uri")
        asset["uri"] = None
        asset["metadata"] = {}
        if asset["id"] not in media_ids:
            continue
        if not original_uri or not isinstance(original_uri, str):
            raise PublicationError(f"Approved media has no local source: {asset['id']}")
        if original_uri not in source_checksums or not asset.get("sha256"):
            raise PublicationError(f"Approved media needs manifest and asset checksums: {asset['id']}")
        source = contained_file(source_dir, original_uri)
        suffix = source.suffix.lower()
        if suffix not in _MEDIA_SUFFIXES or source.stat().st_size > _MAX_MEDIA_BYTES:
            raise PublicationError(f"Approved media has unsupported type or size: {asset['id']}")
        data = source.read_bytes()
        if digest(data) != asset["sha256"] or digest(data) != source_checksums[original_uri]:
            raise PublicationError(f"Approved media checksum mismatch: {asset['id']}")
        validate_image(data, suffix)
        name = f"media/{dataset_id}/{digest(data)}{suffix}"
        media[name] = data
        asset["uri"] = f"data/{name}"
    scan_public(value, label=f"record.{record.id}")
    return value


def _prepare(registry_dir: Path, packs_dir: Path, output_dir: Path, profile_path: Path, max_bytes: int) -> tuple[PublicationReport, dict[str, bytes]]:
    datasets = _registry(Path(registry_dir))
    policies = _profile(Path(profile_path), {dataset.id for dataset in datasets})
    files: dict[str, bytes] = {}
    catalogue: list[dict[str, Any]] = []
    published: list[str] = []
    metadata_only: list[str] = []
    for dataset in datasets:
        public_dataset = _public_dataset(dataset)
        catalogue.append(public_dataset)
        policy = policies.get(dataset.id, {})
        if not policy.get("records", False):
            metadata_only.append(dataset.id)
            continue
        _require_right(dataset, "records")
        annotations = policy.get("annotations", False)
        derived = policy.get("derived_artifacts", False)
        if annotations:
            _require_right(dataset, "annotations")
        if derived:
            _require_right(dataset, "derived_artifacts")
        media_ids = set(policy.get("media_asset_ids", []))
        if media_ids:
            _require_right(dataset, "images")
            if not policy.get("sensitive_media_reviewed", False):
                raise PublicationError(f"Sensitive-media review is required: {dataset.id}")
        pack_path = Path(packs_dir) / dataset.id / "pack.json"
        pack = _load_pack(pack_path, dataset)
        if derived:
            pack = _attach_approved_artifacts(pack, pack_path.parent, policy)
        media: dict[str, bytes] = {}
        records = [_public_record(record, annotations=annotations, derived=derived, media_ids=media_ids, source_dir=pack_path.parent, source_checksums=pack.checksums, dataset_id=dataset.id, media=media) for record in pack.records]
        present_media = {asset["id"] for record in records for asset in record["assets"] if asset["uri"]}
        if present_media != media_ids:
            raise PublicationError(f"Media allowlist does not match preview assets: {dataset.id}")
        if derived:
            record_ids = {record["id"] for record in records}
            for artifact in pack.artifacts:
                if artifact.snapshot_ids != [dataset.snapshot_id] or not set(artifact.ids).issubset(record_ids) or artifact.files:
                    raise PublicationError(f"Artifact identity or file references are unsafe: {artifact.id}")
                if artifact.coverage.get("status") not in {"complete", "completed"}:
                    raise PublicationError(f"Artifact lacks complete coverage status: {artifact.id}")
        public_pack = Pack(
            dataset=Dataset.model_validate(public_dataset),
            fields=[field for field in pack.fields if field.namespace == "record" or (field.namespace == "source" and annotations) or (field.namespace == "prediction" and derived)],
            records=[Record.model_validate(record) for record in records],
            artifacts=pack.artifacts if derived else [], population_scope="preview",
            sampling=pack.sampling, checksums={},
        ).model_dump(mode="json")
        scan_public({"fields": public_pack["fields"], "artifacts": public_pack["artifacts"], "sampling": public_pack["sampling"]}, label=f"pack.{dataset.id}")
        files[f"{dataset.id}.json"] = compact_json(public_pack)
        files.update(media)
        published.append(dataset.id)
    files["catalogue.json"] = compact_json(catalogue)
    total = sum(len(content) for content in files.values())
    if total > max_bytes:
        raise PublicationError(f"Static data exceeds {max_bytes} byte budget ({total})")
    report = PublicationReport(len(catalogue), tuple(published), tuple(metadata_only), total, Path(output_dir) / "data")
    return report, files


def validate_publication(registry_dir: Path, packs_dir: Path, output_dir: Path, profile_path: Path, *, max_bytes: int = MAX_EXCHANGE_BYTES) -> PublicationReport:
    """Validate and size the exact data that a build would write, without writing it."""
    return _prepare(registry_dir, packs_dir, output_dir, profile_path, max_bytes)[0]


def build_publication(registry_dir: Path, packs_dir: Path, output_dir: Path, profile_path: Path, *, max_bytes: int = MAX_EXCHANGE_BYTES) -> PublicationReport:
    """Replace the static data directory after all approval and content checks pass."""
    report, files = _prepare(registry_dir, packs_dir, output_dir, profile_path, max_bytes)
    target = report.output_dir
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise PublicationError("Static data destination is a symlink")
    with tempfile.TemporaryDirectory(prefix=".atlas-publication-", dir=target.parent) as temp:
        stage = Path(temp) / "data"
        stage.mkdir()
        for name, content in files.items():
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        backup = Path(temp) / "previous-data"
        had_target = target.exists()
        if had_target:
            os.replace(target, backup)
        try:
            os.replace(stage, target)
        except BaseException:
            if had_target:
                os.replace(backup, target)
            raise
        if had_target:
            shutil.rmtree(backup)
    return report
