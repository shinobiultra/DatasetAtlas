import json
import hashlib
from pathlib import Path

import pytest
from PIL import Image

from dataset_atlas.exports import (
    PublicationError, build_publication, export_pack, export_selection,
    import_pack, import_selection, validate_publication,
)
from dataset_atlas.exports.security import ExchangeError
from dataset_atlas.models import Artifact, Asset, Dataset, FieldDescriptor, Pack, Record, Relation, Selection


def dataset(**kwargs):
    return Dataset(id="toy", name="Toy", release="r1", snapshot_id="s1", **kwargs)


def record(**kwargs):
    return Record(**{"id": "toy:example:1", "dataset_id": "toy", "release_id": "r1", "snapshot_id": "s1", "text": "sample", **kwargs})


def selection():
    return Selection(id="sel1", ids=["toy:example:1"], unit="example", snapshot_ids=["s1"], dataset_ids=["toy"], created_at="2026-09-22T00:00:00Z")


def setup_publication(tmp_path: Path, *, rights=None, policy=None, bad_text=None):
    registry = tmp_path / "registry"
    packs = tmp_path / "work" / "packs"
    output = tmp_path / "public"
    (registry / "datasets").mkdir(parents=True, exist_ok=True)
    (packs / "toy").mkdir(parents=True, exist_ok=True)
    entry = dataset(rights=rights or {}, adapter_config={"local_path": "/home/researcher/private"}, evidence=[{"excerpt": "private paper text"}])
    (registry / "datasets" / "toy.json").write_text(entry.model_dump_json())
    (registry / "publication.json").write_text(json.dumps({"schema_version": "1.0", "datasets": {"toy": policy or {}}}))
    pack = Pack(dataset=entry, fields=[], records=[record(text=bad_text)] if bad_text else [record()], sampling={"method": "first", "population": "synthetic fixture"})
    (packs / "toy" / "pack.json").write_text(pack.model_dump_json())
    return registry, packs, output, registry / "publication.json"


def test_selection_export_roundtrip_and_tampering(tmp_path):
    target = export_selection(selection(), [record()], tmp_path / "selection")
    loaded_selection, loaded_records = import_selection(target)
    assert loaded_selection.ids == [loaded_records[0].id]
    (target / "records.json").write_text("[]")
    with pytest.raises(ExchangeError, match="Checksum"):
        import_selection(target)
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["checksums"] = None
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ExchangeError, match="unexpected files"):
        import_selection(target)


def test_selection_rejects_wrong_identity_and_oversize(tmp_path):
    with pytest.raises(ExchangeError, match="Record IDs"):
        export_selection(selection(), [record(id="other")], tmp_path / "bad")
    target = export_selection(selection(), [record()], tmp_path / "small")
    with pytest.raises(ExchangeError, match="size limit"):
        import_selection(target, max_bytes=30)


def test_selection_includes_only_approved_bounded_media(tmp_path):
    media_root = tmp_path / "source"
    media_root.mkdir()
    Image.new("RGB", (2, 2), (10, 20, 30)).save(media_root / "image.png")
    item = record(assets=[Asset(id="a1", dataset_id="toy", release_id="r1", modality="image", uri="image.png")])
    target = export_selection(selection(), [item], tmp_path / "with-media", media_root=media_root, approved_media_ids={"a1"})
    _, loaded = import_selection(target)
    assert loaded[0].assets[0].uri.startswith("media/")
    assert len(list((target / "media").iterdir())) == 1
    with pytest.raises(ExchangeError, match="escapes|Unsafe"):
        export_selection(selection(), [record(assets=[Asset(id="a1", dataset_id="toy", release_id="r1", modality="image", uri="../escape.png")])], tmp_path / "unsafe", media_root=media_root, approved_media_ids={"a1"})


def test_portable_pack_roundtrip_rejects_traversal_and_private_data(tmp_path):
    pack = Pack(dataset=dataset(), fields=[], records=[record()], sampling={"method": "first"})
    target = export_pack(pack, tmp_path / "pack")
    assert import_pack(target).records[0].id == "toy:example:1"
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["checksums"]["../escape"] = "0" * 64
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ExchangeError, match="unexpected|Unexpected"):
        import_pack(target)
    with pytest.raises(ExchangeError, match="Private"):
        export_pack(Pack(dataset=dataset(), fields=[], records=[record(text="Bearer abcdefghijklmnop")]), tmp_path / "leak")


def test_publication_metadata_only_removes_private_registry_fields(tmp_path):
    args = setup_publication(tmp_path)
    report = build_publication(*args)
    assert report.catalogue_count == 1
    assert report.published_packs == ()
    catalogue = json.loads((report.output_dir / "catalogue.json").read_text())
    assert catalogue[0]["adapter_config"] == {}
    assert catalogue[0]["evidence"] == []
    assert not (report.output_dir / "toy.json").exists()
    assert "/home/researcher/private" not in (report.output_dir / "catalogue.json").read_text()


def test_publication_requires_profile_and_rights_and_rejects_private_content(tmp_path):
    args = setup_publication(tmp_path, policy={"records": True})
    with pytest.raises(PublicationError, match="right is not approved"):
        validate_publication(*args)
    args = setup_publication(tmp_path, rights={"records": "approved"}, policy={"records": True}, bad_text="file:///home/researcher/private.pdf")
    with pytest.raises(PublicationError, match="Private, local, or PDF"):
        build_publication(*args)
    assert not (args[2] / "data").exists()


def test_publication_approved_records_strip_unapproved_annotations_and_media(tmp_path):
    args = setup_publication(tmp_path, rights={"records": "approved"}, policy={"records": True})
    path = args[1] / "toy" / "pack.json"
    value = json.loads(path.read_text())
    value["records"][0]["human"] = {"private_notes": "confidential"}
    value["records"][0]["source"] = {"label": "unreviewed"}
    value["records"][0]["relations"] = [Relation(subject_id="toy:example:1", object_id="other", type="unreviewed").model_dump()]
    value["records"][0]["assets"] = [Asset(id="a1", dataset_id="toy", release_id="r1", modality="image", uri="/home/researcher/image.png").model_dump()]
    value["fields"] = [FieldDescriptor(id="source.label", name="Label").model_dump()]
    path.write_text(json.dumps(value))
    report = build_publication(*args)
    public = json.loads((report.output_dir / "toy.json").read_text())
    assert public["records"][0]["human"] == {}
    assert public["records"][0]["source"] == {}
    assert public["records"][0]["relations"] == []
    assert public["fields"] == []
    assert public["records"][0]["assets"][0]["uri"] is None


def test_publication_media_needs_explicit_review_and_local_file(tmp_path):
    args = setup_publication(tmp_path, rights={"records": "approved", "images": "approved"}, policy={"records": True, "media_asset_ids": ["a1"]})
    path = args[1] / "toy" / "pack.json"
    value = json.loads(path.read_text())
    Image.new("RGB", (2, 2), (10, 20, 30)).save(path.parent / "photo.png")
    checksum = hashlib.sha256((path.parent / "photo.png").read_bytes()).hexdigest()
    value["records"][0]["assets"] = [Asset(id="a1", dataset_id="toy", release_id="r1", modality="image", uri="photo.png", sha256=checksum).model_dump()]
    value["checksums"] = {"photo.png": checksum}
    path.write_text(json.dumps(value))
    with pytest.raises(PublicationError, match="review"):
        validate_publication(*args)
    profile = json.loads(args[3].read_text())
    profile["datasets"]["toy"]["sensitive_media_reviewed"] = True
    args[3].write_text(json.dumps(profile))
    report = build_publication(*args)
    public = json.loads((report.output_dir / "toy.json").read_text())
    assert public["records"][0]["assets"][0]["uri"].startswith("data/media/toy/")
    assert len(list((report.output_dir / "media" / "toy").iterdir())) == 1
    original_catalogue = (report.output_dir / "catalogue.json").read_bytes()
    (path.parent / "photo.png").write_bytes(b"%PDF-1.7 disguised")
    with pytest.raises(PublicationError, match="checksum"):
        build_publication(*args)
    assert (report.output_dir / "catalogue.json").read_bytes() == original_catalogue


def test_derived_overlay_is_pinned_and_joins_by_snapshot_and_id(tmp_path):
    args = setup_publication(tmp_path, rights={"records": "approved", "derived_artifacts": "approved"}, policy={"records": True})
    artifact = Artifact(
        id="art-1", kind="project.umap", snapshot_ids=["s1"], unit="example", ids=["toy:example:1"],
        coverage={"status": "completed", "completed": 1, "failed": 0},
        data={"items": [{"id": "toy:example:1", "status": "completed", "output": {"x": 1.5, "y": 2.5}}],
              "points": [{"id": "toy:example:1", "x": 1.5, "y": 2.5}]},
    )
    overlay = args[1] / "toy" / "analysis-artifacts.json"
    overlay.write_text(json.dumps([artifact.model_dump(mode="json")]))
    policy = json.loads(args[3].read_text())
    policy["datasets"]["toy"].update({"derived_artifacts": True, "derived_artifact_ids": ["art-1"], "derived_artifacts_sha256": hashlib.sha256(overlay.read_bytes()).hexdigest()})
    args[3].write_text(json.dumps(policy))
    report = build_publication(*args)
    public = json.loads((report.output_dir / "toy.json").read_text())
    assert public["artifacts"][0]["id"] == "art-1"
    assert public["records"][0]["prediction"]["art-1.x"] == 1.5
    assert any(field["id"] == "prediction.art-1.x" for field in public["fields"])
    overlay.write_text("[]")
    with pytest.raises(PublicationError, match="checksum"):
        validate_publication(*args)
    incomplete = artifact.model_dump(mode="json")
    incomplete["coverage"]["status"] = "partial"
    overlay.write_text(json.dumps([incomplete]))
    policy["datasets"]["toy"]["derived_artifacts_sha256"] = hashlib.sha256(overlay.read_bytes()).hexdigest()
    args[3].write_text(json.dumps(policy))
    with pytest.raises(PublicationError, match="Incomplete"):
        validate_publication(*args)


def test_user_origin_datasets_and_workspace_availability_never_reach_a_public_build(tmp_path):
    import json
    import yaml
    from dataset_atlas.exports import build_publication, validate_publication
    from dataset_atlas.exports.publication import PublicationError
    from dataset_atlas.models import Availability, Coverage, Dataset
    registry = tmp_path / 'registry'
    (registry / 'datasets').mkdir(parents=True)
    shipped = Dataset(id='shipped', name='Shipped', coverage=Coverage(preview_count=3), availability=Availability(preview='local'))
    (registry / 'datasets/shipped.yaml').write_text(yaml.safe_dump(shipped.model_dump(mode='json')))
    (tmp_path / 'profile.json').write_text(json.dumps({'schema_version': '1.0', 'datasets': {}}))
    report = build_publication(registry, tmp_path / 'packs', tmp_path / 'site', tmp_path / 'profile.json')
    catalogue = json.loads((tmp_path / 'site/data/catalogue.json').read_text())
    assert report.catalogue_count == 1 and 'availability' not in catalogue[0]
    mine = Dataset(id='mine', name='Mine', origin='user')
    (registry / 'datasets/mine.yaml').write_text(yaml.safe_dump(mine.model_dump(mode='json')))
    import pytest
    with pytest.raises(PublicationError, match='never published'):
        validate_publication(registry, tmp_path / 'packs', tmp_path / 'site2', tmp_path / 'profile.json')
