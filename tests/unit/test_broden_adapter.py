import io
import zipfile

from PIL import Image
import pytest

from dataset_atlas.adapters.broden import BrodenAdapter
from dataset_atlas.models import Dataset


def native_fixture(root):
    (root/'images').mkdir()
    (root/'category.csv').write_text('name,coverage\nobject,1\ncolor,1\n')
    (root/'label.csv').write_text('number,name\n0,background\n1,fixture\n')
    for name in ('object','color'):(root/f'c_{name}.csv').write_text('number,code,name\n0,0,background\n1,1,fixture\n')
    (root/'index.csv').write_text('image,split,iw,ih,sw,sh,object,color\na.jpg,train,2,2,2,2,1;mask.png,mask.png\n')
    Image.new('RGB',(2,2)).save(root/'images/a.jpg')
    Image.new('RGB',(2,2),(1,0,0)).save(root/'images/mask.png')
    return BrodenAdapter(Dataset(id='broden-fixture',name='fixture',release='fixture',adapter='broden',adapter_config={'path':str(root)}))


def test_native_label_tables_and_shared_category_mask_are_preserved(tmp_path):
    adapter=native_fixture(tmp_path);source=adapter.prepare(adapter.plan(2,1_000_000))
    record=adapter.iter_records(source).records[0]
    assert record.source['native_constant_labels']['object'][0]['name']=='fixture'
    assert len(record.assets)==2
    assert record.assets[1].metadata['categories']==['object','color']
    assert record.assets[1].metadata['native_label_encoding']=='label_id = red + 256 * green'
    assert len(record.source['native_label_tables'])==4
    data=adapter.resolve_asset(source,record.assets[1].uri).data
    with Image.open(io.BytesIO(data)) as image:assert image.getpixel((0,0))==(1,0,0)


def test_broden_rejects_invalid_table_joins_and_duplicate_zip_members(tmp_path):
    adapter=native_fixture(tmp_path)
    (tmp_path/'c_object.csv').write_text('number,code,name\n9,1,absent\n')
    with pytest.raises(ValueError,match='global label'):adapter._rows()
    path=tmp_path/'ambiguous.zip'
    with pytest.warns(UserWarning),zipfile.ZipFile(path,'w') as archive:
        archive.writestr('index.csv','one');archive.writestr('index.csv','two')
    adapter.config['path']=str(path)
    with pytest.raises(ValueError,match='Duplicate'):adapter._read('index.csv',100)
