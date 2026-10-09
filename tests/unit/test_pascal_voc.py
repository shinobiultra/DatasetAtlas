"""Synthetic native-format VOC data only; no real coverage from these fixtures."""
import hashlib,io,json,tarfile
from pathlib import Path
import pytest,yaml
from PIL import Image
from dataset_atlas.converters.pascal_voc import pascal_voc_native


def native_fixture(tmp_path,defect=None,auxiliary=False):
    tmp_path.mkdir(parents=True,exist_ok=True);source=tmp_path/'native.tar';members={};prefix='Fixture/'
    for name in (['a','b','c'] if auxiliary else ['a','b']):
        image=io.BytesIO();Image.new('RGB',(5,4),'red').save(image,'JPEG');members[prefix+'JPEGImages/'+name+'.jpg']=image.getvalue()
        xml=f'<annotation><filename>{name}.jpg</filename><size><width>5</width><height>4</height><depth>3</depth></size><object><name>person</name><difficult>1</difficult><bndbox><xmin>0</xmin><ymin>1</ymin><xmax>5</xmax><ymax>4</ymax></bndbox></object></annotation>'
        if defect=='entity':xml='<!DOCTYPE annotation [<!ENTITY x SYSTEM "file:///private">]>'+xml
        members[prefix+'Annotations/'+name+'.xml']=xml.encode()
    for section in ['SegmentationClass','SegmentationObject']:
        image=io.BytesIO();mask=Image.new('P',(5,4),1);mask.putpalette([0,0,0,255,0,0]+[0]*762);mask.save(image,'PNG');members[prefix+section+'/a.png']=image.getvalue()
    members[prefix+'ImageSets/Main/trainval.txt']=b'a\nb\n'
    members[prefix+'ImageSets/Main/cat_trainval.txt']=b'a  0\nb -1\n'
    members[prefix+'ImageSets/Main/person_trainval.txt']=b'a 1\nb 1\n'
    members[prefix+'ImageSets/Action/jumping_trainval.txt']=b'a 1 1\na 2 -1\n'
    if defect=='unjoined':members[prefix+'ImageSets/Main/trainval.txt']=b'a\nmissing\n'
    if defect=='missing-class':members.pop(prefix+'ImageSets/Main/person_trainval.txt')
    with tarfile.open(source,'w') as archive:
        for name,data in members.items():
            info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
        if defect=='duplicate':
            data=members[prefix+'JPEGImages/a.jpg'];info=tarfile.TarInfo(prefix+'JPEGImages/a.jpg');info.size=len(data);archive.addfile(info,io.BytesIO(data))
    return source,members,{'prefix':prefix,'classes':['cat','person']}


def test_exact_native_xml_labels_person_rows_and_palette_masks(tmp_path):
    source,members,params=native_fixture(tmp_path/'source')
    result=pascal_voc_native(params,{'archive_path':source},tmp_path/'converted',lambda:None)
    rows=[json.loads(line) for line in result['path'].read_text().splitlines()]
    assert result['count']==2 and result['native_scope_counts']['classes']==2
    assert rows[0]['class_labels']=={'cat':0,'person':1}
    assert rows[0]['native_xml'].encode()==members['Fixture/Annotations/a.xml']
    assert rows[0]['native_xml_sha256']==hashlib.sha256(members['Fixture/Annotations/a.xml']).hexdigest()
    assert rows[0]['objects'][0]['bndbox']['xmin']=='0'
    assert len([entry for entry in rows[0]['native_image_sets'] if '/Action/' in entry['file']])==2
    assert len(rows[0]['media_refs'])==3 and len(rows[1]['media_refs'])==1


def test_auxiliary_native_images_are_preserved_without_invented_class_labels(tmp_path):
    source,_,params=native_fixture(tmp_path/'source',auxiliary=True)
    result=pascal_voc_native(params,{'archive_path':source},tmp_path/'converted',lambda:None)
    rows=[json.loads(line) for line in result['path'].read_text().splitlines()]
    assert result['count']==3 and result['native_scope_counts']['classification_trainval_images']==2
    extra=rows[2]
    assert extra['image_id']=='c' and extra['native_xml'] and extra['class_labels']=={}
    assert extra['class_cat'] is None and extra['class_person'] is None
    assert extra['main_classification_population']=='outside_main_trainval'


@pytest.mark.parametrize('defect',['entity','unjoined','missing-class','duplicate'])
def test_native_join_and_xml_defects_refuse_activation(tmp_path,defect):
    source,_,params=native_fixture(tmp_path/'source',defect)
    with pytest.raises(ValueError):pascal_voc_native(params,{'archive_path':source},tmp_path/'converted',lambda:None)


def test_native_voc_worker_retains_exact_originals_and_full_record_index(tmp_path,monkeypatch):
    from dataset_atlas.models import Dataset
    from dataset_atlas.preparation import PreparationManager
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry
    source,members,params=native_fixture(tmp_path/'native')
    expected=pascal_voc_native(params,{'archive_path':source},tmp_path/'expected',lambda:None)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    # Register a verified synthetic source object; network access is mocked only
    # for the consistency fingerprint used by the retrieval index.
    objects=tmp_path/'work/source-objects';objects.mkdir(parents=True)
    import os
    os.link(source,objects/sha)
    monkeypatch.setattr('dataset_atlas.storage.ranges.range_fingerprint',lambda *args,**kwargs:'"synthetic"')
    dataset=Dataset(id='synthetic-voc',name='Synthetic VOC',adapter='pascal_voc')
    directory=tmp_path/'registry/datasets';directory.mkdir(parents=True)
    (directory/'synthetic-voc.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipe={'release':'synthetic-native-voc','adapter':'pascal_voc','scope':'Synthetic VOC fixture only','expected_count':2,
            'adapter_config':{'archive_preparation':'indexed-tar','archive_index_key':'archive_path','sequential_index':True,
                'verify_remote_preview_media':True,'preview_group_by':'primary_asset_then_example','media_scope':'partial'},
            'convert':{'name':'pascal_voc_native','params':params,'count':2,'rows_sha256':expected['rows_sha256']},
            'files':[{'source_name':'native.tar','config_key':'archive_path','format':'tar','url':'https://fixture.invalid/native.tar','bytes':source.stat().st_size,'sha256':sha}]}
    recipes=tmp_path/'registry/recipes';recipes.mkdir();(recipes/'synthetic-voc.yaml').write_text(yaml.safe_dump(recipe))
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1_000_000,5_000_000)
    assert plan['ready'];run(tmp_path,plan['id'])
    registry=Registry(tmp_path);pack=registry.pack(dataset.id)
    assert len(pack.records)==2 and registry.dataset(dataset.id).coverage.total_count==2
    assert sum(len(record.assets) for record in pack.records)==4
    active=registry.active_directory(dataset.id)
    for record in pack.records:
        for asset in record.assets:
            assert (active/'pack/media'/asset.sha256).read_bytes()==members[asset.metadata['source_ref']]
