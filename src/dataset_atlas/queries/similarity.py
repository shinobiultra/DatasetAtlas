"""Rebuildable LanceDB exact retrieval over an explicitly eligible population."""
from pathlib import Path
import math
from dataset_atlas.models import Artifact,content_id
from dataset_atlas.processors.analysis import exact_lancedb_search

def similar_records(artifact:Artifact, record_id:str|None, eligible_ids:list[str], limit:int, cache_root:Path, *, query_vector:list[float]|None=None) -> dict:
    if not artifact.kind.startswith('embed.'):raise ValueError('Choose an embedding artifact')
    provenance=artifact.provenance.get('processor_provenance',{})
    space=provenance.get('embedding_space_id')
    if not space:raise ValueError('Embedding space provenance is missing')
    vectors={item['id']:item.get('output',{}).get('vector') for item in artifact.data.get('items',[]) if item.get('status')=='completed'}
    vectors={id:vector for id,vector in vectors.items() if isinstance(vector,list)}
    if query_vector is None and record_id not in vectors:raise ValueError('Query record has no completed vector in this embedding space')
    vector=query_vector if query_vector is not None else vectors[record_id]
    eligible=[id for id in eligible_ids if id in vectors and id!=record_id]
    if len(eligible)>1000:raise ValueError('Exact interactive retrieval currently permits 1000 eligible records; narrow the explicit filter')
    dimension=len(vector)
    if not dimension or any(len(v)!=dimension or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) for v in vectors.values()):raise ValueError('Embedding vectors have invalid dimensions or values')
    if not eligible:return {'mode':'exact','embedding_space_id':space,'artifact_id':artifact.id,'eligible_count':0,'results':[]}
    import lancedb
    database=lancedb.connect(str(cache_root))
    name='atlas_'+content_id({'artifact':artifact.id,'space':space,'vectors':vectors})
    try:table=database.open_table(name)
    except Exception:
        table=database.create_table(name,[{'id':id,'vector':v} for id,v in vectors.items()],exist_ok=True)
    rows=exact_lancedb_search(table,vector,eligible,limit,metric='cosine')
    return {'mode':'exact','embedding_space_id':space,'artifact_id':artifact.id,'eligible_count':len(eligible),'results':[{'id':row['id'],'distance':row['_distance']} for row in rows]}
