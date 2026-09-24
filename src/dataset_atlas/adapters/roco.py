"""Original ROCO annotation tables, with current PMC media resolved on request.

The author's historical FTP package commands are inert source data. PMC moved
its media to a versioned public S3 bucket; a matching filename and the current
PMC metadata MD5 are checked on each fetched image. This establishes present
access, not byte identity with the historical FTP archive.
"""
from __future__ import annotations

from collections import OrderedDict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse, parse_qs
import xml.etree.ElementTree as ET
import zipfile

import httpx

from dataset_atlas.models import Asset, Record, stable_id

from .core import DatasetAdapter, MediaHandle, RecordBatch, SourceDescription, _media_type


_ROOT = 'roco-dataset-a1f0ad6c578ca8801e5a6eccc90af051aee1c326/data'
_PMC = 'https://pmc-oa-opendata.s3.amazonaws.com'
_PMCID = re.compile(r'PMC[0-9]+')
_ID = re.compile(r'ROCO_[0-9]{5}')


class RocoAdapter(DatasetAdapter):
    def probe(self):
        path = Path(self.config['path'])
        return SourceDescription('roco_author_annotations', str(path), path.is_file(), self.revision,
                                 path.stat().st_size if path.is_file() else None,
                                 True, True, True, True, True,
                                 ('Complete original train/validation/test annotations; current PMC image availability checked on request.',))

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        path = Path(self.config['path'])
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != self.config['sha256']:
                raise ValueError('ROCO derived annotation archive checksum changed')
        self._records()
        return source

    @staticmethod
    def _table(archive, base, name):
        data = archive.read(f'{base}/{name}.txt')
        if len(data) > 16_000_000:
            raise ValueError('ROCO annotation table exceeds per-file budget')
        return data.decode('utf-8-sig').splitlines()

    @staticmethod
    def _tabbed(lines, name, *, continuations=False):
        values = {}
        for line in lines:
            key, sep, body = line.partition('\t')
            if not sep or not _ID.fullmatch(key):
                if continuations and values:
                    values[next(reversed(values))] += '\n' + line
                    continue
                raise ValueError(f'ROCO {name} contains a malformed row')
            if key in values:
                raise ValueError(f'ROCO {name} repeats {key}')
            values[key] = body
        return values

    def _records(self):
        if hasattr(self, '_native_records'):
            return self._native_records
        rows = []
        assets = {}
        with zipfile.ZipFile(self.config['path']) as archive:
            names = [item.filename for item in archive.infolist()]
            if len(names) != len(set(names)):
                raise ValueError('ROCO derived archive contains duplicate members')
            for split in ('train', 'validation', 'test'):
                for domain in ('radiology', 'non-radiology'):
                    base = f'{_ROOT}/{split}/{domain}'
                    captions = self._tabbed(self._table(archive, base, 'captions'), 'captions', continuations=True)
                    links = self._tabbed(self._table(archive, base, 'dlinks'), 'dlinks')
                    if set(captions) != set(links):
                        raise ValueError('ROCO caption and source-image IDs differ')
                    extra = {name: self._tabbed(self._table(archive, base, name), name)
                             for name in ('keywords', 'cuis', 'semtypes')}
                    if any(set(table) != set(links) for table in extra.values()):
                        raise ValueError('ROCO annotation IDs differ between tables')
                    licence_rows = list(csv.DictReader(self._table(archive, base, 'licences')))
                    licences = {}
                    for item in licence_rows:
                        key = item.get('ROCO_ID')
                        if not key or key in licences or key not in links:
                            raise ValueError('ROCO licence IDs are duplicated or unjoined')
                        licences[key] = item
                    for key, link in links.items():
                        command, sep, filename = link.rpartition('\t')
                        pmc = _PMCID.search(command)
                        if not sep or not pmc or not filename or '/' in filename or '\\' in filename:
                            raise ValueError('ROCO source-image link is malformed')
                        if not command.startswith('wget -r ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/'):
                            raise ValueError('ROCO source-image command is outside the author release')
                        license_row = licences.get(key)
                        ref = f'roco/{key}/{filename}'
                        asset = Asset(id=stable_id(self.dataset.id, self.revision, 'asset', ref),
                                      dataset_id=self.dataset.id, release_id=self.revision,
                                      modality='image', uri=ref,
                                      metadata={'source_filename': filename, 'pmcid': pmc.group(),
                                                'upstream_status': 'PMC versioned image checked on demand',
                                                'source_license': license_row['CC'] if license_row else 'not_listed'})
                        record = Record(id=stable_id(self.dataset.id, self.revision, 'example', key),
                                        dataset_id=self.dataset.id, release_id=self.revision,
                                        snapshot_id=self.dataset.snapshot_id, text=captions[key].strip(),
                                        asset_ids=[asset.id], assets=[asset],
                                        source={'roco_id': key, 'split': split, 'domain': domain,
                                                'caption': captions[key].strip(),
                                                'keywords': [value for value in extra['keywords'][key].split('\t') if value],
                                                'cuis': [value for value in extra['cuis'][key].split('\t') if value],
                                                'semtypes': [value for value in extra['semtypes'][key].split('\t') if value],
                                                'licence': license_row['CC'] if license_row else None,
                                                'pmc_source_id': license_row['PMC_ID'] if license_row else None,
                                                '_atlas_origin': {'caption_table': f'{base}/captions.txt',
                                                                  'image_link_table': f'{base}/dlinks.txt',
                                                                  'licence_table': f'{base}/licences.txt',
                                                                  'historical_ftp_command': command}})
                        rows.append(record)
                        assets[ref] = (pmc.group(), filename)
        if len(rows) != self.config.get('expected_count', 87927) or len({row.id for row in rows}) != len(rows):
            raise ValueError('ROCO native population count or IDs differ from pinned release')
        self._native_records = rows
        self._assets = assets
        self._metadata = OrderedDict()
        return rows

    @property
    def count(self):
        return len(self._records())

    def source_field_types(self):
        return {'roco_id': 'string', 'split': 'string', 'domain': 'string', 'caption': 'string',
                'keywords': 'array', 'cuis': 'array', 'semtypes': 'array', 'licence': 'string',
                'pmc_source_id': 'string', '_atlas_origin': 'object'}

    def iter_records(self, source, cursor=None, limit=None):
        rows = self._records()
        start = int(cursor or 0)
        if start < 0 or start > len(rows):
            raise ValueError('Invalid ROCO cursor')
        end = min(len(rows), start + min(limit or source.limit, source.limit))
        batch = rows[start:end]
        for row in batch:
            source.charge(len(row.model_dump_json().encode()))
        return RecordBatch(batch, str(end) if end < len(rows) else None, len(batch))

    @staticmethod
    def _json(url):
        response = httpx.get(url, timeout=20)
        response.raise_for_status()
        if len(response.content) > 200_000:
            raise ValueError('PMC metadata exceeds byte budget')
        return response.json()

    def _pmc_metadata(self, pmcid):
        cached = self._metadata.get(pmcid)
        if cached is not None:
            self._metadata.move_to_end(pmcid)
            return cached
        response = httpx.get(f'{_PMC}/metadata/{pmcid}.1.json', timeout=20)
        if response.status_code == 404:
            listing = httpx.get(f'{_PMC}/', params={'list-type': '2', 'prefix': pmcid + '.', 'delimiter': '/'}, timeout=20)
            listing.raise_for_status()
            if len(listing.content) > 50_000:
                raise ValueError('PMC version listing exceeds byte budget')
            root = ET.fromstring(listing.content)
            versions = [item.text.rstrip('/') for item in root.findall('.//{*}CommonPrefixes/{*}Prefix') if item.text]
            if not versions:
                raise FileNotFoundError('PMC article version is unavailable')
            # The oldest surviving version is the nearest available match to
            # the author release; it is still labelled as current PMC media.
            version = min(versions, key=lambda value: int(value.rsplit('.', 1)[1]))
            metadata = self._json(f'{_PMC}/metadata/{version}.json')
        else:
            response.raise_for_status()
            if len(response.content) > 200_000:
                raise ValueError('PMC metadata exceeds byte budget')
            metadata = response.json()
        if metadata.get('pmcid') != pmcid or not isinstance(metadata.get('media_urls'), list):
            raise ValueError('PMC media metadata differs from requested article')
        self._metadata[pmcid] = metadata
        if len(self._metadata) > 128:
            self._metadata.popitem(last=False)
        return metadata

    def resolve_asset(self, source, asset_ref):
        self._records()
        if asset_ref not in self._assets:
            raise ValueError('ROCO asset absent from pinned annotations')
        pmcid, filename = self._assets[asset_ref]
        metadata = self._pmc_metadata(pmcid)
        candidates = []
        for value in metadata['media_urls']:
            parsed = urlparse(value.replace('s3://pmc-oa-opendata/', _PMC + '/', 1))
            if parsed.scheme == 'https' and parsed.netloc == 'pmc-oa-opendata.s3.amazonaws.com' and unquote(parsed.path).rsplit('/', 1)[-1] == filename:
                candidates.append((parsed, parse_qs(parsed.query).get('md5', [])))
        if len(candidates) != 1 or len(candidates[0][1]) != 1 or not re.fullmatch(r'[a-f0-9]{32}', candidates[0][1][0]):
            raise FileNotFoundError('ROCO image is absent or ambiguous in current PMC media')
        parsed, checksums = candidates[0]
        size_limit = min(source.max_bytes - source.bytes_read, 50_000_000)
        data = bytearray()
        with httpx.stream('GET', parsed.geturl(), timeout=30) as response:
            response.raise_for_status()
            if int(response.headers.get('Content-Length', 0)) > size_limit:
                raise ValueError('ROCO image exceeds original-media byte budget')
            for chunk in response.iter_bytes(1 << 20):
                data.extend(chunk)
                if len(data) > size_limit:
                    raise ValueError('ROCO image exceeds original-media byte budget')
        if hashlib.md5(data, usedforsecurity=False).hexdigest() != checksums[0]:
            raise ValueError('Current PMC image differs from its metadata checksum')
        source.charge(len(data))
        return MediaHandle(bytes(data), _media_type(filename), hashlib.sha256(data).hexdigest(), asset_ref)
