"""Embedded images are media whatever the column is called and however the bytes are stored."""
import hashlib
import io
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from PIL import Image
from dataset_atlas.adapters.columnar import ColumnarAdapter
from dataset_atlas.models import Dataset


def _png(colour):
    stream = io.BytesIO(); Image.new('RGB', (4, 4), colour).save(stream, format='PNG'); return stream.getvalue()


def _dataset(path):
    return Dataset(id='binary-columns', name='Binary columns', release='r', snapshot_id='s', adapter='columnar',
                   adapter_config={'files': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'format': 'parquet'}]})


def test_list_of_raw_binary_named_anything_becomes_assets(tmp_path):
    path = tmp_path / 'shard.parquet'
    pq.write_table(pa.table({'question': ['q0', 'q1'], 'figure': [[_png('red'), _png('blue')], [_png('green')]]}), path)
    adapter = ColumnarAdapter(_dataset(path))
    assert adapter.media_columns == ['figure']
    source = adapter.prepare(adapter.plan(10, 10_000_000))
    records = adapter.iter_records(source).records
    assert [len(r.assets) for r in records] == [2, 1]
    assert all(asset.modality == 'image' and asset.uri.startswith('embedded/') for r in records for asset in r.assets)
    # The original bytes never appear in the JSON-facing source fields.
    for record in records:
        record.model_dump_json()
        assert isinstance(record.source['figure'], list) and record.source['figure'][0]['status'] == 'embedded'
    assert adapter.resolve_asset(source, records[0].assets[1].uri).data == _png('blue')


def test_plain_binary_struct_without_image_in_name_is_media_too(tmp_path):
    path = tmp_path / 'shard.parquet'
    pq.write_table(pa.table({'scene': pa.array([{'bytes': _png('red'), 'path': None}], type=pa.struct([('bytes', pa.binary()), ('path', pa.string())]))}), path)
    adapter = ColumnarAdapter(_dataset(path))
    assert adapter.media_columns == ['scene']


def test_undeclared_bytes_fail_on_the_first_row_with_the_column_named(tmp_path):
    path = tmp_path / 'shard.parquet'
    pq.write_table(pa.table({'blob': [b'\xff\xfe not utf-8'], 'text': ['t']}), path)
    dataset = _dataset(path)
    dataset.adapter_config['media_columns'] = ['_atlas_no_embedded_images']  # caller explicitly opted out of detection
    adapter = ColumnarAdapter(dataset)
    source = adapter.prepare(adapter.plan(10, 10_000_000))
    with pytest.raises(ValueError, match='blob.*raw bytes'):
        adapter.iter_records(source)
