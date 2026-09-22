from dataset_atlas.models import Artifact,Query
from dataset_atlas.queries.results import attach_results
from dataset_atlas.queries import query_pack

def test_results_pin_status_and_zero_distinct(pack):
    artifact=Artifact(id='run-a',kind='detect.test',snapshot_ids=['s1'],unit='example',ids=['r0','r1'],data={'items':[{'id':'r0','status':'completed','output':{'detections':[]}},{'id':'r1','status':'failed','output':{}}]})
    joined=attach_results(pack,[artifact])
    assert joined.records[0].prediction['run-a.detection_count']==0
    assert 'run-a.detection_count' not in joined.records[1].prediction
    assert not pack.records[0].prediction
    result=query_pack(joined,Query(snapshot_id='s1',result_snapshot_ids=['run-a'],filter={'field_id':'prediction.run-a.detection_count','op':'eq','value':0}))
    assert [r.id for r in result.records]==['r0']
