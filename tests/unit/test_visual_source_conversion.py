import base64,importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('prepare_visual_sources',Path(__file__).parents[2]/'scripts/prepare_visual_sources.py')
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)

def test_circular_eval_references_resolve_original_bytes_without_dropping_variants():
    data=b'original image fixture'*10
    encoded=base64.b64encode(data).decode()
    images={'241':encoded,'1000241':'241','2000241':'1000241'}
    assert source.resolve_reference('2000241',images)==('241',data)
    assert len(images)==3

def test_invalid_circular_eval_reference_is_not_silently_accepted():
    with pytest.raises(ValueError,match='Cyclic'):source.resolve_reference('1',{'1':'2','2':'1'})
    with pytest.raises(ValueError,match='Missing'):source.resolve_reference('1',{'1':'2'})
