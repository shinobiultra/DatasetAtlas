import pytest
from dataset_atlas.models import Query,Record, stable_id,Pack
from dataset_atlas.queries import query_pack,fnv1a

def query(pack,**kwargs):return query_pack(pack,Query(snapshot_id='s1',**kwargs))
def test_null_distinct_from_zero(pack):
    assert [r.id for r in query(pack,filter={'field_id':'source.score','op':'is_null','value':True}).records]==['r2']
    assert [r.id for r in query(pack,filter={'field_id':'source.score','op':'ne','value':0}).records]==['r0','r1','r3']
def test_filter_typed_and_literal(pack):
    assert query(pack,filter={'field_id':'source.score','op':'eq','value':'1'}).matched_count==0
    assert query(pack,filter={'field_id':'source.label','op':'contains','value':'.*'}).matched_count==0
    assert query(pack,filter={'or':[{'field_id':'source.label','op':'eq','value':'A'},{'field_id':'source.score','op':'gt','value':3}]}).matched_count==3

def test_cursor_pins_query_and_snapshot(pack):
    first=query(pack,limit=2);second=query(pack,limit=2,cursor=first.cursor)
    assert [r.id for r in first.records+second.records]==['r0','r1','r2','r3']
    with pytest.raises(ValueError,match='cursor'):query(pack,limit=1,cursor=first.cursor)
    with pytest.raises(ValueError,match='Snapshot'):query_pack(pack,Query(snapshot_id='changed'))

def test_sort_null_last_both_directions(pack):
    assert [r.id for r in query(pack,sort=[{'field_id':'source.score','direction':'desc'}]).records]==['r3','r1','r0','r2']
    assert query(pack,sort=[{'field_id':'source.score','direction':'asc'}]).records[-1].id=='r2'

def test_sampling_frozen_and_scope(pack):
    a=query(pack,sample={'method':'random','seed':42,'size':2});b=query(pack,sample={'method':'random','seed':42,'size':2})
    assert a==b and a.population_scope=='preview' and a.matched_count==4
    assert len(query(pack,sample={'method':'stratified','field_id':'source.label','seed':1,'size':3}).records)==3
    assert fnv1a('hello')==1335831723

def test_hostile_filters(pack):
    with pytest.raises(ValueError,match='Unknown field'):query(pack,filter={'field_id':'source.x; DROP TABLE a','op':'eq','value':1})
    tree={'field_id':'source.label','op':'eq','value':'A'}
    for _ in range(10):tree={'not':tree}
    with pytest.raises(ValueError,match='depth'):query(pack,filter=tree)

def test_roundtrip_preserves_structure(pack):
    assert Pack.model_validate_json(pack.model_dump_json())==pack
    assert len({a.id for r in pack.records for a in r.assets})==1
    assert stable_id('a','v1','example','original')==stable_id('a','v1','example','original')
    with pytest.raises(ValueError,match='Unsupported schema'):Pack.model_validate({**pack.model_dump(),'schema_version':'2.0'})

def test_asset_unit_deduplicates_questions_without_label_leakage(pack):
    result=query(pack,unit='asset')
    assert result.matched_count==1
    assert result.records[0].id=='asset-1'
    assert result.records[0].question is None
    assert result.records[0].source=={}
    with pytest.raises(ValueError,match='Unknown field'):query(pack,unit='asset',filter={'field_id':'source.label','op':'eq','value':'A'})
