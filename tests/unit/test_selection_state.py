"""Legacy serialization differences are idempotent; frozen selection contents are immutable."""
import json

from fastapi.testclient import TestClient
import pytest

from dataset_atlas.api import create_app
from dataset_atlas.api.app import State
from dataset_atlas.models import Selection


def selection(**changes):
    return Selection(id='saved', ids=['r0', 'r1'], unit='example', snapshot_ids=['s1'], dataset_ids=['fixture'],
                     created_at='2026-01-01T00:00:00Z', **changes)


def store_legacy(state, value):
    document=value.model_dump(mode='json', exclude_defaults=True)
    raw=json.dumps(document, sort_keys=True, indent=2)
    with state.connection() as db:
        db.execute('INSERT INTO selections VALUES (?,?)', (value.id, raw))
    return raw


def stored_body(state, identity='saved'):
    with state.connection() as db:
        return db.execute('SELECT body FROM selections WHERE id=?', (identity,)).fetchone()[0]


def test_legacy_defaults_and_object_key_order_reimport_without_rewriting_saved_bytes(tmp_path):
    state=State(tmp_path/'atlas.sqlite')
    original=selection(query={'filter':{'op':'eq', 'value':True, 'field_id':'source.flag'}})
    raw=store_legacy(state, original)
    state.put(state.get(original.id))
    reordered=original.model_copy(update={'query':{'filter':{'field_id':'source.flag', 'value':True, 'op':'eq'}}})
    state.put(reordered)
    assert stored_body(state)==raw


@pytest.mark.parametrize('change', [
    {'ids':['r1', 'r0']}, {'ids':['r0', 'r2']}, {'snapshot_ids':['different']},
    {'dataset_ids':['different']}, {'method':'population'}, {'seed':4}, {'name':'Renamed'},
    {'query':{'filter':{'field_id':'source.flag', 'op':'eq', 'value':1}}},
    {'query':{'filter':{'field_id':'source.flag', 'op':'eq', 'value':1.0}}},
])
def test_normalized_legacy_equality_rejects_actual_changes_including_boolean_to_number(tmp_path, change):
    state=State(tmp_path/'atlas.sqlite')
    original=selection(query={'filter':{'field_id':'source.flag', 'op':'eq', 'value':True}})
    raw=store_legacy(state, original)
    with pytest.raises(ValueError, match='immutable'):
        state.put(original.model_copy(update=change))
    assert stored_body(state)==raw


def test_numeric_query_representation_change_is_not_collapsed(tmp_path):
    state=State(tmp_path/'atlas.sqlite')
    original=selection(query={'value':1})
    state.put(original)
    with pytest.raises(ValueError, match='immutable'):
        state.put(original.model_copy(update={'query':{'value':1.0}}))


def test_large_selection_immutability_compares_actual_sidefile_ids(tmp_path):
    state=State(tmp_path/'atlas.sqlite')
    original=selection().model_copy(update={'ids':[f'r{i}' for i in range(10_001)]})
    state.put(original)
    before=stored_body(state)
    path=state.ids_dir/'saved.json'
    payload=path.read_bytes()
    state.put(state.get('saved'))
    changed=original.model_copy(update={'ids':original.ids[:-1]+['other']})
    with pytest.raises(ValueError, match='immutable'):
        state.put(changed)
    assert stored_body(state)==before and path.read_bytes()==payload
    assert state.get('saved').ids==original.ids


def test_export_import_of_existing_legacy_selection_is_idempotent(workspace):
    state=State(workspace/'work/atlas.sqlite')
    raw=store_legacy(state, selection())
    with TestClient(create_app(workspace)) as client:
        payload=client.get('/api/v1/selections/saved/export')
        assert payload.status_code==200, payload.text
        imported=client.post('/api/v1/selections/import', headers={'X-Atlas-Request':'1'}, json=payload.json())
        assert imported.status_code==200, imported.text
        assert imported.json()['ids']==['r0', 'r1']
        assert imported.json()['snapshot_ids']==['s1']
    assert stored_body(state)==raw
