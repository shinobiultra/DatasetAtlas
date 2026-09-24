"""Kaggle v5 COVID-19 Radiography images, paired masks and native source tables."""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile

from dataset_atlas.models import Asset, Record, stable_id
from .core import DirectoryArchiveAdapter, RecordBatch, _safe_relative

_ROOT = 'COVID-19_Radiography_Dataset/'
_CLASSES = ('COVID', 'Lung_Opacity', 'Normal', 'Viral Pneumonia')
_IMAGE = re.compile(r'^COVID-19_Radiography_Dataset/(COVID|Lung_Opacity|Normal|Viral Pneumonia)/(images|masks)/([^/]+\.png)$')
_NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
_EXPECTED = {'COVID': 3616, 'Lung_Opacity': 6012, 'Normal': 10192, 'Viral Pneumonia': 1345}


def _source_table(payload: bytes):
    """Read only the four native string columns from the depositor's XLSX."""
    with zipfile.ZipFile(io.BytesIO(payload)) as workbook:
        if 'xl/sharedStrings.xml' not in workbook.namelist():
            raise ValueError('COVID source table has no shared strings')
        if any(workbook.getinfo(member).file_size > 3_000_000
               for member in ('xl/sharedStrings.xml', 'xl/worksheets/sheet1.xml')):
            raise ValueError('COVID source table XML exceeds budget')
        strings = [''.join(item.itertext()) for item in
                   ET.fromstring(workbook.read('xl/sharedStrings.xml')).findall('x:si', _NS)]
        sheet = ET.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
        rows = []
        for row in sheet.findall('.//x:sheetData/x:row', _NS):
            values = {}
            for cell in row.findall('x:c', _NS):
                column = re.match(r'[A-Z]+', cell.attrib['r']).group()
                if column not in {'A', 'B', 'C', 'D'} or cell.attrib.get('t') != 's':
                    raise ValueError('COVID source table has unexpected cell type')
                values[column] = strings[int(cell.findtext('x:v', namespaces=_NS))]
            if set(values) != {'A', 'B', 'C', 'D'}:
                raise ValueError('COVID source table row has missing columns')
            rows.append(values)
    if rows.pop(0) != {'A': 'FILE NAME', 'B': 'FORMAT', 'C': 'SIZE', 'D': 'URL'}:
        raise ValueError('COVID source table headings changed')
    return rows


class CovidRadiographyAdapter(DirectoryArchiveAdapter):
    def _inventory(self):
        if hasattr(self, '_native_inventory'):
            return self._native_inventory
        images = {}; masks = {}; tables = {}
        with zipfile.ZipFile(self._path()) as archive:
            infos = [item for item in archive.infolist() if not item.is_dir()]
            if len(infos) != len({item.filename for item in infos}):
                raise ValueError('Duplicate COVID native member')
            for item in infos:
                name = _safe_relative(item.filename)
                match = _IMAGE.fullmatch(name)
                if match:
                    if item.file_size > 10_000_000:
                        raise ValueError('COVID image exceeds media budget')
                    (images if match[2] == 'images' else masks)[(match[1], match[3])] = name
                elif name in {_ROOT + category + '.metadata.xlsx' for category in _CLASSES}:
                    if item.file_size > 2_000_000:
                        raise ValueError('COVID source table exceeds budget')
                    tables[name.removeprefix(_ROOT).removesuffix('.metadata.xlsx')] = _source_table(archive.read(item))
                elif name != _ROOT + 'README.md.txt':
                    raise ValueError(f'Unexpected COVID native member: {name}')
        if set(tables) != set(_CLASSES) or set(images) != set(masks):
            raise ValueError('COVID native image/mask or table inventory differs')
        for category, count in _EXPECTED.items():
            keys = {name for label, name in images if label == category}
            if len(keys) != count or len(tables[category]) != count:
                raise ValueError('COVID native class population changed')
            indexed = {}
            for row in tables[category]:
                if row['B'] != 'PNG' or row['C'] != '256*256' or not row['D'].startswith('https://'):
                    raise ValueError('COVID native source row changed')
                # The native Normal table spells its stem NORMAL, while its
                # image and mask members use Normal. Preserve both spellings.
                stem = row['A']
                if category == 'Normal':
                    if not stem.startswith('NORMAL-'):
                        raise ValueError('COVID Normal source stem changed')
                    stem = 'Normal-' + stem.removeprefix('NORMAL-')
                filename = stem + '.png'
                if filename in indexed:
                    raise ValueError('Duplicate COVID source-table filename')
                indexed[filename] = row
            if set(indexed) != keys:
                raise ValueError('COVID source table and image filenames do not join')
            tables[category] = indexed
        self._native_inventory = [(category, filename, images[(category, filename)],
                                   masks[(category, filename)], tables[category][filename])
                                  for category, filename in sorted(images)]
        return self._native_inventory

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        self._inventory()
        return source

    @property
    def count(self):
        return len(self._inventory())

    def source_field_types(self):
        return {'category': 'string', 'filename': 'string', 'metadata_file_name': 'string', 'source_url': 'string',
                'source_format': 'string', 'source_table_size': 'string', 'image_path': 'string',
                'mask_path': 'string', '_atlas_origin': 'object'}

    def iter_records(self, source, cursor=None, limit=None):
        inventory = self._inventory(); start = int(cursor or 0)
        if not 0 <= start <= len(inventory):
            raise ValueError('Invalid COVID cursor')
        end = min(len(inventory), start + min(limit or source.limit, source.limit))
        rows = []
        for category, filename, image_ref, mask_ref, row in inventory[start:end]:
            assets = [Asset(id=stable_id(self.dataset.id, self.revision, 'asset', ref),
                            dataset_id=self.dataset.id, release_id=self.revision,
                            modality='image', uri=ref, metadata={'condition': condition,
                                'source_role': condition})
                      for condition, ref in (('radiograph', image_ref), ('segmentation mask', mask_ref))]
            record = Record(id=stable_id(self.dataset.id, self.revision, 'example', category + ':' + filename),
                            dataset_id=self.dataset.id, release_id=self.revision,
                            snapshot_id=self.dataset.snapshot_id, asset_ids=[asset.id for asset in assets],
                            assets=assets, source={'category': category, 'filename': filename,
                                'metadata_file_name': row['A'],
                                'source_url': row['D'], 'source_format': row['B'], 'source_table_size': row['C'],
                                'image_path': image_ref, 'mask_path': mask_ref,
                                '_atlas_origin': {'metadata_member': _ROOT + category + '.metadata.xlsx',
                                    'identity': category + ':' + filename}})
            source.charge(len(record.model_dump_json().encode()))
            rows.append(record)
        return RecordBatch(rows, str(end) if end < len(inventory) else None, len(rows))
