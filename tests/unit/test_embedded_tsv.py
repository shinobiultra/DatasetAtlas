import base64
import csv
import io
import pytest
from PIL import Image
from dataset_atlas.models import Dataset
from dataset_atlas.adapters import get_adapter


def adapter(tmp_path, rows, **config):
    path = tmp_path / 'samples.tsv'
    with path.open('w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['index', 'image', 'question', 'A', 'B', 'answer'])
        writer.writerows(rows)
    return get_adapter(Dataset(id='tsv', name='TSV test', release='r', snapshot_id='s', adapter='embedded_tsv',
        adapter_config={'path': str(path), 'tables': [{'path_key': 'path', 'split': 'dev', 'language': 'EN'}], **config}))


def image():
    out = io.BytesIO(); Image.new('RGB', (5, 7), 'red').save(out, 'PNG')
    return out.getvalue()


def test_native_tsv_references_quoted_multiline_and_payload_boundaries(tmp_path):
    data = image()
    a = adapter(tmp_path, [['1', '2', 'Question\nwith a tab\tand quotes "here"', 'one', 'two', 'A'],
        ['2', base64.b64encode(data).decode(), 'Other question', 'two', 'one', 'B'], ['3', '1', 'Chain', 'one', 'two', 'A']])
    source = a.prepare(a.plan(10, 100000))
    rows = a.iter_records(source).records
    assert a.count == 3 and len({r.id for r in rows}) == 3
    assert len({r.assets[0].id for r in rows}) == 1
    assert rows[0].question == 'Question\nwith a tab\tand quotes "here"'
    assert rows[0].choices == ['A. one', 'B. two']
    assert rows[0].source['answer'] == 'A'
    assert 'image' not in rows[1].source
    assert a.resolve_asset(source, rows[0].assets[0].uri).data == data
    assert base64.b64encode(data).decode() not in str(a._metadata_rows)
    tiny = a.prepare(a.plan(1, 1))
    with pytest.raises(ValueError, match='budget'): a.resolve_asset(tiny, rows[0].assets[0].uri)


@pytest.mark.parametrize('rows,error', [
    ([['1','2','q','a','b','A'],['2','1','q','a','b','B']], 'Cyclic'),
    ([['1','99','q','a','b','A']], 'Missing'),
    ([['1','2','q','a','b','A'],['1','2','q','a','b','A']], 'unique'),
    ([['1','','q','a','b','A']], 'empty'),
])
def test_bad_tsv_references_fail_before_indexing(tmp_path, rows, error):
    with pytest.raises(ValueError, match=error): adapter(tmp_path, rows)._rows()


def test_tsv_read_is_bounded(tmp_path):
    with pytest.raises(ValueError, match='byte limit'):
        adapter(tmp_path, [['1','x'*1000,'q','a','b','A']], max_row_bytes=100)._rows()
