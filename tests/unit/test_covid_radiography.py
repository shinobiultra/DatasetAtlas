import hashlib
import io
import zipfile

import pytest
from PIL import Image


def _xlsx(category):
    names = ['FILE NAME', 'FORMAT', 'SIZE', 'URL', category + '-1', 'PNG', '256*256', 'https://example.org/source']
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    shared = '<sst xmlns="' + ns + '">' + ''.join('<si><t>' + name + '</t></si>' for name in names) + '</sst>'
    rows = '<sheetData><row r="1">' + ''.join(f'<c r="{col}1" t="s"><v>{idx}</v></c>' for idx, col in enumerate('ABCD')) + '</row>'
    rows += '<row r="2">' + ''.join(f'<c r="{col}2" t="s"><v>{idx}</v></c>' for idx, col in enumerate('ABCD', 4)) + '</row></sheetData>'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('xl/sharedStrings.xml', shared)
        archive.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="' + ns + '">' + rows + '</worksheet>')
    return stream.getvalue()


def _fixture(tmp_path, dataset, *, omit_mask=False):
    from dataset_atlas.adapters import covid_radiography as native
    png = io.BytesIO(); Image.new('L', (256, 256), 20).save(png, 'PNG')
    path = tmp_path / 'release.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for category in native._CLASSES:
            stem = 'Normal' if category == 'Normal' else category
            archive.writestr(native._ROOT + category + '.metadata.xlsx', _xlsx('NORMAL' if category == 'Normal' else category))
            archive.writestr(native._ROOT + category + '/images/' + stem + '-1.png', png.getvalue())
            if not omit_mask or category != 'Normal':
                archive.writestr(native._ROOT + category + '/masks/' + stem + '-1.png', png.getvalue())
        archive.writestr(native._ROOT + 'README.md.txt', 'Fixture')
    dataset.id = 'covid-fixture'; dataset.release = 'v5'; dataset.snapshot_id = 'fixture'
    dataset.adapter = 'covid_radiography'
    dataset.adapter_config = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return path


def test_covid_native_pairs_and_table_join(tmp_path, pack, monkeypatch):
    from dataset_atlas.adapters import covid_radiography as native
    monkeypatch.setattr(native, '_EXPECTED', dict.fromkeys(native._CLASSES, 1))
    _fixture(tmp_path, pack.dataset)
    adapter = native.CovidRadiographyAdapter(pack.dataset)
    source = adapter.prepare(adapter.plan(1000, 10_000_000))
    assert adapter.count == 4
    rows = adapter.iter_records(source, limit=4).records
    assert len(rows) == 4 and all(len(row.assets) == 2 for row in rows)
    normal = next(row for row in rows if row.source['category'] == 'Normal')
    assert normal.source['filename'] == 'Normal-1.png'
    assert normal.source['metadata_file_name'] == 'NORMAL-1'
    assert normal.source['source_table_size'] == '256*256'
    assert 'width' not in normal.assets[0].metadata
    assert adapter.resolve_asset(source, normal.assets[1].uri).media_type == 'image/png'


def test_covid_rejects_unpaired_mask(tmp_path, pack, monkeypatch):
    from dataset_atlas.adapters import covid_radiography as native
    monkeypatch.setattr(native, '_EXPECTED', dict.fromkeys(native._CLASSES, 1))
    _fixture(tmp_path, pack.dataset, omit_mask=True)
    with pytest.raises(ValueError, match='image/mask'):
        native.CovidRadiographyAdapter(pack.dataset).count
