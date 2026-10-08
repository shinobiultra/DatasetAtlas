"""Rebuildable LanceDB exact retrieval over an explicitly eligible population."""
from pathlib import Path
import math
from dataset_atlas.models import Artifact,content_id
from dataset_atlas.processors.analysis import exact_lancedb_search
from .embedding_space import embedding_vectors

def similar_records(artifact:Artifact, record_id:str|None, eligible_ids:list[str], limit:int, cache_root:Path, *, query_vector:list[float]|None=None) -> dict:
    vectors,provenance,metric=embedding_vectors(artifact)
    space=provenance.get('embedding_space_id')
    if not space:raise ValueError('Embedding space provenance is missing')
    if query_vector is None and record_id not in vectors:raise ValueError('Query record has no completed vector in this embedding space')
    vector=query_vector if query_vector is not None else vectors[record_id]
    eligible=[id for id in eligible_ids if id in vectors and id!=record_id]
    dimension=len(vector)
    if not dimension or any(type(x) not in (int,float) or not math.isfinite(x) for x in vector) or any(len(v)!=dimension for v in vectors.values()):raise ValueError('Embedding vectors have invalid dimensions or values')
    if metric=='cosine' and not any(x != 0 for x in vector):raise ValueError('Cosine query vector must be nonzero')
    if not eligible:return {'mode':'exact','embedding_space_id':space,'artifact_id':artifact.id,'eligible_count':0,'results':[]}
    import lancedb
    database=lancedb.connect(str(cache_root))
    name='atlas_'+content_id({'artifact':artifact.id,'space':space,'vectors':vectors})
    try:table=database.open_table(name)
    except Exception:
        table=database.create_table(name,[{'id':id,'vector':v} for id,v in vectors.items()],exist_ok=True)
    rows=exact_lancedb_search(table,vector,eligible,limit,metric='l2' if metric=='euclidean' else metric)
    return {'mode':'exact','metric':metric,'retrieval_dtype':'float32','embedding_space_id':space,'artifact_id':artifact.id,'eligible_count':len(eligible),'results':[{'id':row['id'],'distance':row['_distance']} for row in rows]}
