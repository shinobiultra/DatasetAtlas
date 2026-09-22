"""Bounded typed queries with identical static-provider semantics."""
from __future__ import annotations
import base64
import json
import math
from functools import cmp_to_key
from typing import Any
from dataset_atlas.models import Pack, Query, QueryResult, Record, content_id

OPS = {'eq','ne','in','contains','gt','gte','lt','lte','is_null'}

def fnv1a(value: str) -> int:
    result = 2166136261
    for byte in value.encode():
        result = ((result ^ byte) * 16777619) & 0xffffffff
    return result

def field_value(record: Record, field: str) -> Any:
    if field in {'id','text','question','unit','dataset_id','release_id','snapshot_id'}:
        return getattr(record,field)
    namespace, _, name = field.partition('.')
    if namespace not in {'source','prediction','human'}:
        raise ValueError(f'Unsupported field {field}')
    return getattr(record,namespace).get(name)

def validate_filter(node: dict | None, fields: set[str], depth=0, counter=None) -> None:
    if node is None: return
    if counter is None: counter=[0]
    counter[0]+=1
    if depth>8 or counter[0]>64: raise ValueError('Filter exceeds depth 8 or 64 nodes')
    if not isinstance(node,dict): raise ValueError('Filter must be an object')
    for boolean in ['and','or','not']:
        if boolean in node:
            if set(node)!={boolean}: raise ValueError('Boolean filter has extra keys')
            children=node[boolean] if boolean!='not' else [node[boolean]]
            if not isinstance(children,list) or not children: raise ValueError('Boolean filter needs operands')
            for child in children: validate_filter(child,fields,depth+1,counter)
            return
    if not set(node)<= {'field_id','op','value'}: raise ValueError('Unknown filter keys')
    if node.get('field_id') not in fields: raise ValueError('Unknown field: '+str(node.get('field_id')))
    if node.get('op') not in OPS: raise ValueError('Unsupported filter operation')
    if node['op']=='in' and (not isinstance(node.get('value'),list) or len(node['value'])>1000): raise ValueError('Membership expects at most 1000 values')
    if node['op']=='is_null' and not isinstance(node.get('value'),bool): raise ValueError('is_null expects boolean value')
    if node['op']=='contains' and not isinstance(node.get('value'),str): raise ValueError('contains expects literal text')
    if len(json.dumps(node))>16000: raise ValueError('Filter operand too large')

def matches(record: Record, node: dict | None) -> bool:
    if node is None:return True
    if 'and' in node:return all(matches(record,n) for n in node['and'])
    if 'or' in node:return any(matches(record,n) for n in node['or'])
    if 'not' in node:return not matches(record,node['not'])
    value=field_value(record,node['field_id']); expected=node.get('value'); op=node['op']
    if op=='is_null':return (value is None)==expected
    if value is None or expected is None:return False
    if op=='eq':return type(value) is type(expected) and value==expected or isinstance(value,(float,int)) and not isinstance(value,bool) and isinstance(expected,(float,int)) and not isinstance(expected,bool) and value==expected
    if op=='ne':return not matches(record,{**node,'op':'eq'})
    if op=='in':return any(matches(record,{**node,'op':'eq','value':v}) for v in expected)
    if op=='contains':return isinstance(value,str) and expected.lower() in value.lower()
    if isinstance(value,bool) or isinstance(expected,bool):return False
    if not ((isinstance(value,(int,float)) and isinstance(expected,(int,float))) or (isinstance(value,str) and isinstance(expected,str))):return False
    if op=='gt':return value>expected
    if op=='gte':return value>=expected
    if op=='lt':return value<expected
    if op=='lte':return value<=expected
    return False

def sample_records(records: list[Record], sample: dict | None, fields: set[str]) -> list[Record]:
    if not sample:return records
    if not set(sample)<={'method','seed','size','field_id'}:raise ValueError('Unknown sampling options')
    method=sample.get('method','source');size=sample.get('size',100);seed=sample.get('seed',0)
    if type(size) is not int or not 1<=size<=10000:raise ValueError('Sample size must be 1..10000')
    if type(seed) is not int:raise ValueError('Sampling seed must be integer')
    if method=='source':return records[:size]
    ranked=sorted(records,key=lambda r:(fnv1a(f'{seed}:{r.id}'),r.id))
    if method=='random':return ranked[:size]
    if method!='stratified':raise ValueError('Unknown sampling method')
    field=sample.get('field_id')
    if field not in fields:raise ValueError('Stratified sampling requires registered field_id')
    groups={}
    for row in ranked:groups.setdefault(json.dumps(field_value(row,field),sort_keys=True,separators=(',',':'),ensure_ascii=False),[]).append(row)
    output=[];keys=sorted(groups)
    while len(output)<size:
        added=False
        for key in keys:
            if groups[key] and len(output)<size:output.append(groups[key].pop(0));added=True
        if not added:break
    return output

def materialize_records(pack: Pack, unit: str) -> list[Record]:
    direct=[r for r in pack.records if r.unit==unit]
    if direct or unit!='asset':return direct
    assets={}
    for row in pack.records:
        for asset in row.assets:
            if asset.id not in assets:
                assets[asset.id]=Record(id=asset.id,dataset_id=asset.dataset_id,release_id=asset.release_id,snapshot_id=row.snapshot_id,unit='asset',assets=[asset.model_copy(deep=True)],asset_ids=[asset.id],text=asset.text,source=dict(asset.metadata))
    return list(assets.values())

def query_pack(pack: Pack, query: Query) -> QueryResult:
    if query.population_scope!=pack.population_scope:raise ValueError('Requested population scope is unavailable in this pack')
    if query.snapshot_id!=pack.dataset.snapshot_id:raise ValueError('Snapshot mismatch; reload dataset before querying')
    fields={f.id for f in pack.fields}|{'id','text','question','unit','dataset_id','release_id','snapshot_id'}
    if query.unit=='asset':
        fields={'id','text','question','unit','dataset_id','release_id','snapshot_id'}|{f'source.{key}' for row in materialize_records(pack,'asset') for key in row.source}|{f.id for f in pack.fields if f.unit=='asset'}
    validate_filter(query.filter,fields)
    for sort in query.sort:
        if set(sort)!={'field_id','direction'} or sort['field_id'] not in fields or sort['direction'] not in {'asc','desc'}:raise ValueError('Invalid sort field or direction')
    if len(query.search)>4000:raise ValueError('Search exceeds 4000 characters')
    rows=materialize_records(pack,query.unit)
    available=len(rows)
    if not rows and pack.records:raise ValueError('This pack does not support the requested record unit')
    needle=query.search.lower()
    rows=[r for r in rows if matches(r,query.filter) and (not needle or needle in '\n'.join([r.text or '',r.question or '',json.dumps(r.source,ensure_ascii=False,separators=(',',':'))]).lower())]
    matched=len(rows)
    if query.sort:
        def compare(a,b):
            for sort in query.sort:
                x=field_value(a,sort['field_id']);y=field_value(b,sort['field_id'])
                if x is None or y is None:
                    if x is None and y is None:continue
                    return 1 if x is None else -1
                if type(x)!=type(y) and not isinstance(x,(int,float)) and not isinstance(y,(int,float)):
                    x=json.dumps(x,sort_keys=True);y=json.dumps(y,sort_keys=True)
                try: result=(x>y)-(x<y)
                except TypeError: result=(str(x)>str(y))-(str(x)<str(y))
                if result:return result * (1 if sort['direction']=='asc' else -1)
            return (a.id>b.id)-(a.id<b.id)
        rows.sort(key=cmp_to_key(compare))
    rows=sample_records(rows,query.sample,fields)
    fingerprint=content_id(query.model_dump(exclude={'cursor'}))
    offset=0
    if query.cursor:
        try:
            if len(query.cursor)>1024:raise ValueError()
            cursor=json.loads(base64.urlsafe_b64decode(query.cursor.encode()))
            if cursor['query']!=fingerprint or type(cursor['offset']) is not int or cursor['offset']<0:raise ValueError()
            offset=cursor['offset']
        except Exception as exc:raise ValueError('Invalid cursor or query changed; restart pagination') from exc
    page=rows[offset:offset+query.limit]
    next_offset=offset+len(page)
    cursor=base64.urlsafe_b64encode(json.dumps({'query':fingerprint,'offset':next_offset}).encode()).decode() if next_offset<len(rows) else None
    warnings=[]
    if pack.population_scope=='preview':warnings.append('Counts describe the available preview, not the complete release.')
    if query.sample and query.sample.get('method')=='stratified':warnings.append('Stratified samples do not estimate population prevalence.')
    return QueryResult(snapshot_id=query.snapshot_id,unit=query.unit,population_scope=pack.population_scope,records=page,returned_count=len(page),matched_count=matched,coverage={'available_count':available,'sampled_count':len(rows),'sampling':query.sample},ordering=query.sort,cursor=cursor,warnings=warnings)
