import pytest

from dataset_atlas.models import Record,Asset
from dataset_atlas.preparation.filtering import accepts_record,population_counts


def test_image_subset_requires_independent_native_and_output_counts():
    spec={'asset_modality':'image'}
    assert population_counts(10,3,spec,10)==3
    with pytest.raises(ValueError,match='source and selected'):
        population_counts(10,3,spec,None)
    with pytest.raises(ValueError,match='source count'):
        population_counts(11,3,spec,10)
    with pytest.raises(ValueError,match='declared release'):
        population_counts(11,10,None,None)
    plain=Record(id='one',dataset_id='fixture',release_id='r',snapshot_id='s')
    image=plain.model_copy(update={'assets':[Asset(id='a',dataset_id='fixture',release_id='r',modality='image',uri='original.png')]})
    assert not accepts_record(plain,spec) and accepts_record(image,spec)
    assert accepts_record(plain,None)


def test_pinned_native_class_groups_preserve_labels_and_inclusive_endpoints():
    from dataset_atlas.preparation.filtering import filter_record
    spec={'native_class_groups':{'field':'label','groups':[{'name':'dog','start':151,'end':268},{'name':'cat','start':281,'end':285}],
        'provenance':{'revision':'pinned native author mapping'}}}
    assert population_counts(1000,123,spec,1000)==123
    for label,index in ((151,0),(268,0),(281,1),(285,1)):
        record=Record(id=str(label),dataset_id='fixture',release_id='r',snapshot_id='s',source={'label':label})
        assert filter_record(record,spec) and record.source['label']==label
        assert record.source['_atlas_native_class_group']['id']==index
        assert record.source['_atlas_native_class_group']['native_label']==label
        with pytest.raises(ValueError,match='collides'):filter_record(record,spec)
    for label in (150,269,280,286,None,True,'151'):
        record=Record(id='outside',dataset_id='fixture',release_id='r',snapshot_id='s',source={'label':label})
        assert not accepts_record(record,spec)
    overlapping={'native_class_groups':{'field':'label','groups':[{'name':'a','start':1,'end':3},{'name':'b','start':3,'end':5}],'provenance':{}}}
    with pytest.raises(ValueError,match='Overlapping'):population_counts(10,5,overlapping,10)
