"""Selective, ETag-pinned access to ObjectNet's original encrypted ZIP."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile

from dataset_atlas.models import Asset, Record, stable_id
from dataset_atlas.storage.remote_zip import REMOTE_ZIP_MEMBERS
from .core import DatasetAdapter, MediaHandle, RecordBatch, SourceDescription
from .remote_zip import PinnedHTTPRangeReader

_IMAGE = re.compile(r'objectnet-1\.0/images/([^/]+)/([^/]+\.png)\Z')
_MAPPING = 'objectnet-1.0/mappings/folder_to_objectnet_label.json'


class ObjectNetAdapter(DatasetAdapter):
    def __init__(self, dataset):
        super().__init__(dataset)
        self.bytes_fetched = 0
        self.metadata_bytes_fetched = 0

    def _spec(self):
        config = self.config
        return {'url': config['url'], 'bytes': config['bytes'], 'etag': config['etag']}

    def _reader(self, budget):
        return PinnedHTTPRangeReader(self.config['url'], allowed_host='objectnet.dev',
            expected_size=self.config['bytes'], expected_etag=self.config['etag'],
            max_transfer=budget, block_size=2 << 20, max_requests=100)

    def probe(self):
        return SourceDescription('remote_zip_selective', self.config['url'], True,
            self.revision, self.config['bytes'], True, True, True, False, True,
            ('All 50,273 native image names indexed from an ETag-bound ZIP directory; encrypted original PNGs fetched on demand.',))

    def _inventory(self):
        if hasattr(self, '_native_inventory'):
            return self._native_inventory
        with self._reader(25_000_000) as reader:
            with zipfile.ZipFile(reader) as archive:
                infos = archive.infolist()
                if len(infos) != len(archive.NameToInfo) or len(infos) != 50_595:
                    raise ValueError('ObjectNet source member inventory changed')
                mapping_info = archive.getinfo(_MAPPING)
                if mapping_info.file_size > 100_000:
                    raise ValueError('ObjectNet class mapping exceeds byte budget')
                mapping_bytes = archive.read(mapping_info, pwd=b'objectnetisatestset')
                if hashlib.sha256(mapping_bytes).hexdigest() != self.config['mapping_sha256']:
                    raise ValueError('ObjectNet folder labels changed')
                labels = json.loads(mapping_bytes)
                if not isinstance(labels, dict) or len(labels) != 313:
                    raise ValueError('ObjectNet class mapping changed')
                images = []
                folders = set()
                for info in infos:
                    if info.is_dir():
                        continue
                    match = _IMAGE.fullmatch(info.filename)
                    if match:
                        if not (info.flag_bits & 1) or not 1 <= info.file_size <= 50_000_000:
                            raise ValueError('ObjectNet original image encryption or size changed')
                        folders.add(match[1])
                        images.append((info.filename, match[1], labels.get(match[1]), info.file_size, info.CRC))
                    elif info.filename not in {_MAPPING, 'objectnet-1.0/README', 'objectnet-1.0/LICENSE',
                            'objectnet-1.0/mappings/imagenet_to_label_2012_v2',
                            'objectnet-1.0/mappings/objectnet_to_imagenet_1k.json',
                            'objectnet-1.0/mappings/pytorch_to_imagenet_2012_id.json'}:
                        raise ValueError('Unexpected ObjectNet native member')
                if len(images) != 50_273 or folders != set(labels) or any(not isinstance(label, str) for _, _, label, _, _ in images):
                    raise ValueError('ObjectNet image and class population changed')
                images.sort()
                self._native_inventory = images
                self._member_names = {item[0] for item in images}
                self._class_count = len(folders)
            self.bytes_fetched += reader.bytes_transferred
            self.metadata_bytes_fetched += reader.bytes_transferred
            self._check_transfer_budget()
        return self._native_inventory

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        if approved_plan.limit >= 1000:
            self._transfer_cap = self.config.get('remote_transfer_budget_bytes')
        self._inventory()
        return source

    def _check_transfer_budget(self):
        cap = getattr(self, '_transfer_cap', None)
        if cap is not None and self.bytes_fetched > cap:
            raise ValueError('ObjectNet remote transfer exceeded approved budget')

    @property
    def count(self):
        return len(self._inventory())

    def source_field_types(self):
        return {'folder': 'string', 'label': 'string', 'member': 'string',
                'source_member_bytes': 'number', 'zip_crc32': 'number', '_atlas_origin': 'object'}

    def iter_records(self, source, cursor=None, limit=None):
        inventory = self._inventory(); start = int(cursor or 0)
        if not 0 <= start <= len(inventory):
            raise ValueError('Invalid ObjectNet cursor')
        end = min(len(inventory), start + min(limit or source.limit, source.limit))
        records = []
        for member, folder, label, size, crc in inventory[start:end]:
            aid = stable_id(self.dataset.id, self.revision, 'asset', member)
            asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                modality='image', uri=member, metadata={'source_role': 'original ObjectNet image',
                    'label': label, 'native_member_bytes': size})
            record = Record(id=stable_id(self.dataset.id, self.revision, 'example', member),
                dataset_id=self.dataset.id, release_id=self.revision,
                snapshot_id=self.dataset.snapshot_id, asset_ids=[aid], assets=[asset],
                source={'folder': folder, 'label': label, 'member': member,
                    'source_member_bytes': size, 'zip_crc32': crc,
                    '_atlas_origin': {'identity': member, 'remote_zip_etag': self.config['etag']}})
            source.charge(len(record.model_dump_json().encode()))
            records.append(record)
        return RecordBatch(records, str(end) if end < len(inventory) else None, len(records))

    def resolve_asset(self, source, asset_ref):
        self._inventory()
        if asset_ref not in self._member_names:
            raise ValueError('ObjectNet asset is absent from the pinned native inventory')
        remaining = source.max_bytes - source.bytes_read
        if remaining < 1:
            raise ValueError('ObjectNet media budget exhausted')
        with self._reader(min(55_000_000, remaining + 10_000_000)) as reader:
            data = REMOTE_ZIP_MEMBERS.read(reader, self._spec(), asset_ref,
                min(remaining, 50_000_000), password=b'objectnetisatestset')
            transferred = reader.bytes_transferred
        self.bytes_fetched += transferred
        self._check_transfer_budget()
        source.charge(max(len(data), transferred))
        return MediaHandle(data, 'image/png', hashlib.sha256(data).hexdigest(), asset_ref)
