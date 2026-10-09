from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from dataset_atlas.adapters.vhd11k import VHD11KAdapter
from dataset_atlas.models import Dataset
from dataset_atlas.registry import Registry

ROOT = Path(__file__).parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_zip_media_is_bounded_and_restricted_to_annotated_references(tmp_path: Path):
    rows = [
        {"source_id": "image:a.jpeg", "modality": "image", "media_ref": "images/a.jpeg",
         "imagePath": "a.jpeg", "decision": "yes"},
        {"source_id": "video:b.mp4", "modality": "video", "media_ref": "videos/b.mp4",
         "videoPath": "b.mp4", "decision": "no"},
    ]
    source_file = tmp_path / "records.jsonl"
    source_file.write_text("".join(json.dumps(row) + "\n" for row in rows))
    images = tmp_path / "images.zip"
    videos = tmp_path / "videos.zip"
    with zipfile.ZipFile(images, "w") as archive:
        archive.writestr("original_images/a.jpeg", b"image-bytes")
        archive.writestr("original_images/unlisted.jpeg", b"unlisted")
    with zipfile.ZipFile(videos, "w") as archive:
        archive.writestr("original_videos/b.mp4", b"video-bytes")
    dataset = Dataset(id="vhd11k", name="test", release="fixture-1", snapshot_id="fixture-1",
                      adapter="vhd11k", adapter_config={
                          "path": str(source_file), "format": "jsonl", "sha256": _sha(source_file),
                          "images_archive": str(images), "images_sha256": _sha(images),
                          "videos_archive": str(videos), "videos_sha256": _sha(videos)})
    adapter = VHD11KAdapter(dataset)
    source = adapter.prepare(adapter.plan(2, 1_000))
    batch = adapter.iter_records(source, limit=2)
    assert len(batch.records) == 2 and batch.next_cursor is None
    assert [r.assets[0].modality for r in batch.records] == ["image", "video"]
    assert [r.source["decision"] for r in batch.records] == ["yes", "no"]
    image_source = adapter.prepare(adapter.plan(1, 11))
    assert adapter.resolve_asset(image_source, "images/a.jpeg").data == b"image-bytes"
    assert adapter.resolve_asset(adapter.prepare(adapter.plan(1, 11)), "videos/b.mp4").media_type == "video/mp4"
    with pytest.raises(ValueError, match="not referenced"):
        adapter.resolve_asset(adapter.prepare(adapter.plan(1, 100)), "images/unlisted.jpeg")
    with pytest.raises(ValueError, match="byte budget"):
        adapter.resolve_asset(adapter.prepare(adapter.plan(1, 10)), "images/a.jpeg")


def test_real_vhd11k_full_source_and_media_when_present():
    registry = Registry(ROOT)
    dataset = registry.dataset("vhd11k")
    source_file = Path(dataset.adapter_config.get("path", "missing"))
    image_zip = Path(dataset.adapter_config.get("images_archive", "missing"))
    video_zip = Path(dataset.adapter_config.get("videos_archive", "missing"))
    if not all(path.is_file() for path in (source_file, image_zip, video_zip)):
        pytest.skip("Optional native VHD11K archives are not retained locally; original-on-demand access is checked separately")
    adapter = VHD11KAdapter(dataset)
    source = adapter.prepare(adapter.plan(101, 160_000_000))
    first = adapter.iter_records(source, limit=101)
    boundary = adapter.iter_records(source, cursor="9999", limit=2)
    final = adapter.iter_records(source, cursor="10999", limit=101)
    assert len(first.records) == 101
    assert all(record.assets[0].modality == "image" for record in first.records)
    assert [record.assets[0].modality for record in boundary.records] == ["image", "video"]
    assert len(final.records) == 1 and final.records[0].assets[0].modality == "video"
    assert final.next_cursor is None
    preview = registry.pack("vhd11k")
    assert len(preview.records) == len({record.assets[0].uri for record in preview.records}) == 100
    assert all(record.assets[0].modality == "image" for record in preview.records)
    assert {label: sum(record.source["decision"] == label for record in preview.records)
            for label in ("yes", "no")} == {"yes": 50, "no": 50}
    first_media = adapter.resolve_asset(adapter.prepare(adapter.plan(1, 10_000_000)),
                                        preview.records[0].assets[0].uri)
    Image.open(BytesIO(first_media.data)).verify()
    last_video = adapter.resolve_asset(adapter.prepare(adapter.plan(1, 100_000_000)),
                                       final.records[0].assets[0].uri)
    assert last_video.data[:4] != b"" and last_video.media_type == "video/mp4"
    recoded_name = "videos/Real_animated_alcohol_Animation:_SalSphere®_Even_Skin___SalSphere®_Salicylic_Acid_segment_001.mp4"
    recoded_video = adapter.resolve_asset(adapter.prepare(adapter.plan(1, 10_000_000)), recoded_name)
    assert len(recoded_video.data) == 4_537_985 and recoded_video.media_type == "video/mp4"


def test_remote_membership_and_original_image_video_reads(tmp_path, monkeypatch):
    import io
    from contextlib import contextmanager
    rows=[{'source_id':'image:a.jpeg','modality':'image','media_ref':'images/a.jpeg','imagePath':'a.jpeg','decision':'yes'},
          {'source_id':'video:b.mp4','modality':'video','media_ref':'videos/b.mp4','videoPath':'b.mp4','decision':'no'}]
    annotations=tmp_path/'records.jsonl';annotations.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    payloads={}; originals={'images':b'original-image','videos':b'original-video'}
    for key,name in [('images','a.jpeg'),('videos','b.mp4')]:
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('native/'+name,originals[key])
        payloads[key]=stream.getvalue()
    dataset=Dataset(id='vhd11k',name='test',release='fixture-remote',snapshot_id='fixture-remote',adapter='vhd11k',adapter_config={
        'path':str(annotations),'format':'jsonl','sha256':_sha(annotations),
        'remote_archives':{key:{'url':'https://example.org/'+key+'.zip','bytes':len(value),'etag':'"'+key+'"'} for key,value in payloads.items()}})
    adapter=VHD11KAdapter(dataset)
    class Ranges(io.BytesIO):
        def __init__(self,payload):super().__init__(payload);self.size=len(payload);self.bytes_fetched=0
        def read(self,size=-1):
            value=super().read(size);self.bytes_fetched+=len(value);return value
    @contextmanager
    def remote(key,budget):
        with Ranges(payloads[key]) as stream:yield stream
    monkeypatch.setattr(adapter,'_remote',remote)
    assert adapter.validate_media(10000)['referenced_assets']==2
    for key,ref in [('images','images/a.jpeg'),('videos','videos/b.mp4')]:
        handle=adapter.resolve_asset(adapter.prepare(adapter.plan(1,100)),ref)
        assert handle.data==originals[key] and handle.sha256==hashlib.sha256(originals[key]).hexdigest()
    with pytest.raises(ValueError,match='not referenced'):
        adapter.resolve_asset(adapter.prepare(adapter.plan(1,100)),'images/unlisted.jpeg')
    with pytest.raises(ValueError,match='budget'):
        adapter.resolve_asset(adapter.prepare(adapter.plan(1,1)),'images/a.jpeg')
    rows.append({'media_ref':'images/missing.jpeg'})
    adapter._refs={row['media_ref'] for row in rows}
    with pytest.raises(ValueError,match='membership differs'):
        adapter.validate_media(10000)
