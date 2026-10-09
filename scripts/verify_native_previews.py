"""Verify real immutable indices and retained originals through a local API.

No source acquisition or external provider request is permitted. Receipts contain
counts and hashes; native text and media remain in the local workspace.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import zlib

import httpx
from PIL import Image
import pyarrow.parquet as pq

from dataset_atlas.jobs.limits import install
from dataset_atlas.registry import Registry
from dataset_atlas.storage.compact import read_compact
from dataset_atlas.storage.glb import verify_glb
from dataset_atlas.storage.audio import verify_audio


def verify_native_identity(record, asset, data: bytes, sha: str) -> str:
    """Compare retained bytes with the strongest native checksum the preview carries and return which check was made.

    A pack asset normally carries the native SHA-256. Adapters that resolve media lazily leave it empty, so fall back to what the source
    itself pinned: a Git blob SHA-1 in the asset's source checksum (inventory-backed releases) or a SHA-256 field in the native row. A member of
    an ETag-pinned remote ZIP has no independent hash at all; its integrity is the ZIP CRC and ETag verified when the bytes were retrieved, and the
    receipt says so instead of implying a content hash. A preview with none of these cannot be verified against its source and is refused."""
    if asset.sha256:
        if sha != asset.sha256: raise ValueError('Retained preview differs from its native original hash')
        return 'asset-sha256'
    checksum = (asset.metadata or {}).get('source_checksum') or {}
    if checksum.get('git_blob_sha1'):
        if hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest() != checksum['git_blob_sha1']:
            raise ValueError('Retained preview differs from its pinned Git object')
        return 'git-blob-sha1'
    native = record.source.get('image_sha256')
    if native:
        if sha != native: raise ValueError('Retained preview differs from the native row checksum')
        return 'native-row-sha256'
    metadata=asset.metadata or {}
    native_ref=metadata.get('source_ref') or getattr(asset,'uri',None) or ''
    if metadata.get('representation') == 'original ZIP member' and str(native_ref).startswith('zip/'):
        crc=metadata.get('zip_crc32');length=metadata.get('native_member_bytes')
        etag=metadata.get('source_etag');parts=metadata.get('source_part_etags')
        etag_valid=isinstance(etag,str) and re.fullmatch(r'"[^"\r\n]+"',etag) is not None
        parts_valid=isinstance(parts,list) and bool(parts) and all(isinstance(value,str) and re.fullmatch(r'"[^"\r\n]+"',value) for value in parts)
        parent_sha=metadata.get('source_archive_sha256')
        parent_valid=isinstance(parent_sha,str) and re.fullmatch(r'[0-9a-f]{64}',parent_sha) is not None
        if type(crc) is not int or not 0<=crc<=0xffffffff or type(length) is not int or length!=len(data):
            raise ValueError('Preview lacks matching native ZIP CRC and length evidence')
        if zlib.crc32(data)&0xffffffff!=crc:raise ValueError('Retained preview differs from its native ZIP CRC')
        if not (etag_valid or parts_valid or parent_valid):raise ValueError('Preview lacks pinned ZIP parent integrity evidence')
        if parent_valid:return 'zip-crc32-and-full-parent-sha256 (no independent member content hash)'
        return 'zip-crc32-and-etag-at-retrieval (no independent content hash)'
    raise ValueError('Preview asset carries no native checksum to verify against')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--dataset', action='append', required=True)
    parser.add_argument('--api', default='http://127.0.0.1:8766')
    parser.add_argument('--max-index-bytes', type=int, default=10_000_000_000)
    parser.add_argument('--max-preview-bytes', type=int, default=2_000_000_000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    host = urlparse(args.api).hostname
    if host != 'localhost' and not (host and ipaddress.ip_address(host).is_loopback):
        raise ValueError('Verification requires a loopback workbench API')
    root = args.root.resolve(); stage = root/'work/native-preview-verification'
    stage.mkdir(parents=True, exist_ok=True)
    install({'max_rss_bytes':8_000_000_000,'max_cpu_seconds':900,'max_wall_seconds':1800},stage)
    registry = Registry(root)
    receipt = {'checked_at_utc':datetime.now(timezone.utc).isoformat(),'datasets':[],
               'scope':'Immutable native-population index integrity and retained preview originals; paper membership is not inferred.',
               'source_acquisition_requests':0,'external_model_requests':0}
    index_bytes = 0; preview_bytes = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=args.api, timeout=90) as client:
        for dataset_id in args.dataset:
            dataset = registry.dataset(dataset_id); pack = registry.pack(dataset_id)
            snapshot = registry.snapshot_path(dataset_id)
            manifest = json.loads((snapshot/'manifest.json').read_text())
            records = snapshot/'records.parquet'; index_bytes += records.stat().st_size
            if index_bytes > args.max_index_bytes: raise ValueError('Index verification exceeds input budget')
            with records.open('rb') as stream: digest = hashlib.file_digest(stream,'sha256').hexdigest()
            if digest != manifest['checksums']['records.parquet']: raise ValueError('Immutable index checksum changed')
            selected = {record.id:record for record in pack.records}; found = set(); seen = set(); count = 0
            for batch in pq.ParquetFile(records).iter_batches(columns=['record_json'],batch_size=512):
                for value in batch.column(0).to_pylist():
                    record = json.loads(value); identity = record['id']
                    if identity in seen: raise ValueError('Duplicate native record ID')
                    seen.add(identity); count += 1
                    if (record['dataset_id'],record['release_id'],record['snapshot_id'],record['unit']) != (
                            dataset.id,dataset.release,dataset.snapshot_id,dataset.coverage.unit):
                        raise ValueError('Native record identity differs from its prepared release')
                    if identity in selected:
                        preview = selected[identity]
                        if preview.source != record['source']: raise ValueError('Preview changed native source fields')
                        found.add(identity)
            if count != dataset.coverage.total_count or found != set(selected):
                raise ValueError('Native index count or preview membership differs')
            response = client.get('/api/v1/datasets/'+dataset.id+'/pack'); response.raise_for_status()
            exposed = response.json()
            api_assets = {(record['id'],asset['id']):asset for record in exposed['records'] for asset in record['assets']}
            assets = []; dimensions = []
            active = registry.active_directory(dataset.id)
            pack_directory = active/'pack' if active else root/'work/packs'/dataset.id
            for record in pack.records:
                for asset in record.assets:
                    if not asset.uri or asset.modality not in {'image','model3d','audio','video'}: continue
                    original_limit = 250_000_000 if asset.modality == 'video' else 100_000_000 if asset.modality == 'audio' else 32_000_000
                    if asset.uri in pack.checksums:
                        path = (pack_directory/asset.uri).resolve()
                        if not path.is_relative_to(pack_directory.resolve()) or path.stat().st_size > original_limit:
                            raise ValueError('Retained preview file exceeds its path or byte bounds')
                        data = path.read_bytes()
                    else:
                        original = read_compact(root,dataset.id,dataset.snapshot_id,asset.uri,original_limit)
                        if not original or original[2]['representation'] != 'original' or not original[2]['protected_preview']:
                            raise ValueError('Preview original is not retained locally')
                        data = original[0]
                    preview_bytes += len(data)
                    if preview_bytes > args.max_preview_bytes: raise ValueError('Original preview verification exceeds byte budget')
                    sha = hashlib.sha256(data).hexdigest()
                    check_kind = verify_native_identity(record, asset, data, sha)
                    technical_metadata = {}
                    if asset.modality == 'image':
                        with Image.open(io.BytesIO(data)) as image:
                            if image.width*image.height > 50_000_000: raise ValueError('Preview exceeds the decoded-pixel budget')
                            dimensions.append([image.width,image.height]); image.load()
                    elif asset.modality == 'model3d': verify_glb(data)
                    elif asset.modality == 'video':
                        from dataset_atlas.storage.video import verify_avi,verify_mp4
                        video=verify_avi(data) if data[:4]==b'RIFF' else verify_mp4(data)
                        technical_metadata={'actual_decoded_video_frames':video.get('actual_decoded_video_frames'),
                                            'native_video_container_checked':True}
                    else:
                        audio = verify_audio(data)
                        technical_metadata = {key:audio[key] for key in (
                            'full_audio_decode_checked','decoded_sample_count','decoded_duration_seconds')}
                    uri = api_assets[(record.id,asset.id)]['uri']
                    if not uri.startswith('/api/v1/media/'): raise ValueError('Local media API reference changed')
                    media = client.get(uri); media.raise_for_status()
                    if hashlib.sha256(media.content).hexdigest() != sha: raise ValueError('Live API original differs from retained bytes')
                    if asset.modality == 'audio':
                        if not media.headers.get('content-type','').startswith('audio/'):
                            raise ValueError('Live API native audio MIME type differs')
                        end = min(len(data),4096)-1
                        part = client.get(uri,headers={'Range':f'bytes=0-{end}'})
                        if part.status_code != 206 or part.content != data[:end+1] or part.headers.get('content-range') != f'bytes 0-{end}/{len(data)}':
                            raise ValueError('Live API native audio byte-range playback differs')
                        technical_metadata['http_range_playback_checked'] = True
                    assets.append({'asset_id':asset.id,'sha256':sha,'bytes':len(data),'modality':asset.modality,
                                   'native_check':check_kind,**technical_metadata})
            result = {'dataset_id':dataset.id,'snapshot_id':dataset.snapshot_id,'native_records':count,
                      'records_sha256':digest,'unique_record_ids':len(seen),'preview_records':len(selected),
                      'preview_native_source_fields_unchanged':True,'original_assets':assets,
                      'verified_live_originals':len(assets),'maximum_image_pixels':max((w*h for w,h in dimensions),default=0),
                      'status':'passed'}
            receipt['datasets'].append(result)
            args.output.write_text(json.dumps(receipt,indent=2)+'\n')
            print(json.dumps({key:value for key,value in result.items() if key != 'original_assets'}),flush=True)
    receipt.update(completed=True,index_bytes_verified=index_bytes,preview_bytes_verified=preview_bytes)
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__ == '__main__': main()
