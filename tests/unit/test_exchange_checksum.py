import pytest
from dataset_atlas.api.checksums import exchange_checksum

def test_browser_numeric_roundtrip_and_object_order():
    python={'x':[2.0,-0.0,1e-7,1e20,0.1],'nested':{'b':'value','a':True}}
    browser={'nested':{'a':True,'b':'value'},'x':[2,0,0.0000001,100000000000000000000,0.1]}
    assert exchange_checksum(python)==exchange_checksum(browser)
    assert exchange_checksum([True])!=exchange_checksum([1])
    assert exchange_checksum(['0x1.0000000000000p+1'])!=exchange_checksum([2])
    assert exchange_checksum({'a':2})!=exchange_checksum({'a':3})

def test_nonportable_numbers_are_explicit():
    for number in (float('nan'),float('inf'),2**53+1):
        with pytest.raises(ValueError):exchange_checksum({'value':number})
