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
