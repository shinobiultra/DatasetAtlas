"""Native NIST EMNIST ZIP of gzip IDX partitions, without pickle or extraction."""
from __future__ import annotations

from functools import lru_cache
import gzip
import hashlib
import io
import re
import struct
import zipfile

from PIL import Image
from dataset_atlas.models import Asset, Record, stable_id
from .core import DirectoryArchiveAdapter, RecordBatch, MediaHandle


class EMNISTAdapter(DirectoryArchiveAdapter):
    def _partitions(self):
        if hasattr(self, '_partition_metadata'):
            return self._partition_metadata
        partitions = []
        with zipfile.ZipFile(self._path()) as archive:
            for configuration in self.config['configurations']:
                if not re.fullmatch(r'[a-z]+', configuration):raise ValueError('Invalid EMNIST configuration')
                mapping = {}
                for line in archive.read(f'gzip/emnist-{configuration}-mapping.txt').decode('ascii').splitlines():
                    label, *codes = map(int, line.split())
                    if label in mapping or not codes or any(not 0 <= c <= 127 for c in codes):
                        raise ValueError('Invalid EMNIST character mapping')
                    mapping[label] = codes
                for split in ['train', 'test']:
                    stem = f'gzip/emnist-{configuration}-{split}'
                    with archive.open(stem+'-images-idx3-ubyte.gz') as raw, gzip.GzipFile(fileobj=raw) as stream:
                        header = stream.read(16)
                    if len(header) != 16:raise ValueError('Truncated EMNIST header')
                    magic, count, height, width = struct.unpack('>IIII', header)
                    if magic != 2051 or (height, width) != (28, 28) or not 0 < count <= 1_000_000:
                        raise ValueError('Invalid EMNIST image shape')
                    with archive.open(stem+'-labels-idx1-ubyte.gz') as raw, gzip.GzipFile(fileobj=raw) as stream:
                        data = stream.read(count+9)
                    if len(data) != count+8 or struct.unpack('>II', data[:8]) != (2049, count):
                        raise ValueError('EMNIST image and label counts differ')
                    labels = data[8:]
                    if set(labels) - set(mapping):raise ValueError('EMNIST label absent from native mapping')
                    expected = self.config.get('counts', {}).get(configuration, {}).get(split)
                    if expected is not None and count != expected:raise ValueError('EMNIST population differs from declared split')
                    partitions.append({'configuration': configuration, 'split': split, 'count': count,
                        'stem': stem, 'mapping': mapping, 'labels': labels})
        self._partition_metadata = partitions
        return partitions

    @property
    def count(self):
        return sum(p['count'] for p in self._partitions())

    def iter_records(self, source, cursor=None, limit=None):
        start = int(cursor or 0)
        if start < 0 or start > self.count:raise ValueError('EMNIST cursor outside population')
        stop = min(self.count, start + min(limit or source.limit, source.limit))
        offset, records = 0, []
        for part in self._partitions():
            for index in range(max(0, start-offset), min(part['count'], stop-offset)):
                key = f"{part['configuration']}/{part['split']}/{index}"
                aid = stable_id(self.dataset.id, self.revision, 'asset', key)
                label = part['labels'][index]; codes = part['mapping'][label]
                asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision, modality='image',
                    uri=key+'.png', representation='lossless_png_transposed_from_source_pixels',
                    metadata={'source_encoding':'IDX uint8 28x28', 'display_transform':'transpose', 'source_index':index})
                record = Record(id=stable_id(self.dataset.id, self.revision, 'example', key), dataset_id=self.dataset.id,
                    release_id=self.revision, snapshot_id=self.dataset.snapshot_id, asset_ids=[aid], assets=[asset],
                    source={'configuration':part['configuration'], 'split':part['split'], 'index':index, 'label':label,
                        'character_codes':codes, 'characters':' / '.join(chr(c) for c in codes)})
                source.charge(len(record.model_dump_json().encode()));records.append(record)
            offset += part['count']
            if offset >= stop:break
        return RecordBatch(records, str(stop) if stop < self.count else None, len(records))

    @lru_cache(maxsize=1)
    def _images(self, configuration, split):
        part = next((p for p in self._partitions() if p['configuration']==configuration and p['split']==split), None)
        if not part:raise ValueError('Unknown EMNIST partition')
        expected = 16 + part['count'] * 784
        if expected > self.config.get('max_decoded_partition_bytes', 600_000_000):
            raise ValueError('EMNIST partition exceeds decoded byte budget')
        with zipfile.ZipFile(self._path()) as archive, archive.open(part['stem']+'-images-idx3-ubyte.gz') as raw, gzip.GzipFile(fileobj=raw) as stream:
            data = stream.read(expected+1)
        if len(data) != expected:raise ValueError('EMNIST image payload length differs from header')
        return data

    def resolve_asset(self, source, asset_ref):
        match = re.fullmatch(r'([a-z]+)/(train|test)/(\d+)\.png', asset_ref)
        if not match:raise ValueError('Invalid EMNIST asset reference')
        configuration, split, index = match.group(1), match.group(2), int(match.group(3))
        part = next((p for p in self._partitions() if p['configuration']==configuration and p['split']==split), None)
        if not part or not 0 <= index < part['count']:raise ValueError('EMNIST asset outside partition')
        data = self._images(configuration, split)
        start = 16 + index*784
        image = Image.frombytes('L', (28,28), data[start:start+784]).transpose(Image.Transpose.TRANSPOSE)
        output = io.BytesIO();image.save(output, format='PNG');pixels = output.getvalue()
        source.charge(len(pixels))
        return MediaHandle(pixels, 'image/png', hashlib.sha256(pixels).hexdigest(), asset_ref)
