"""Rebuildable LanceDB exact retrieval over an explicitly eligible population."""
from pathlib import Path
import math
from dataset_atlas.models import Artifact,content_id
from dataset_atlas.processors.analysis import exact_lancedb_search
from .embedding_space import bulk_directory,embedding_vectors

_matrices={}  # artifact id -> (ids, row by id, float32 matrix); artifacts are immutable, so entries never go stale
_MATRIX_CACHE=2

def _bulk_matrix(artifact:Artifact, artifact_dir:Path):
    import numpy as np
    from dataset_atlas.storage import arrays as store
    cached=_matrices.get(artifact.id)
    if cached is None:
        directory=bulk_directory(artifact,artifact_dir);bulk=artifact.data['bulk']
        ids=store.read_ids(directory,bulk)
        matrix=np.ascontiguousarray(store.read_array(directory,bulk['arrays']['vector'],verify=True),dtype=np.float32)
        cached=(ids,{item_id:row for row,item_id in enumerate(ids)},matrix)
        while len(_matrices)>=_MATRIX_CACHE:_matrices.pop(next(iter(_matrices)))
        _matrices[artifact.id]=cached
    return cached

def similar_records_bulk(artifact:Artifact, record_id:str|None, eligible_ids:list[str], limit:int, artifact_dir:Path, *, query_vector:list[float]|None=None) -> dict:
    """Exact search over an array-backed embedding: one matrix-vector product over the eligible rows."""
    import numpy as np
    provenance=artifact.provenance.get('processor_provenance',{})
    space=provenance.get('embedding_space_id')
    if not space:raise ValueError('Embedding space provenance is missing')
    metric=provenance.get('embedding_space',{}).get('metric','cosine')
    ids,row,matrix=_bulk_matrix(artifact,artifact_dir)
    if query_vector is None:
        if record_id not in row:raise ValueError('Query record has no completed vector in this embedding space')
        query=matrix[row[record_id]]
    else:query=np.asarray(query_vector,dtype=np.float32)
    if query.ndim!=1 or query.shape[0]!=matrix.shape[1] or not np.isfinite(query).all():raise ValueError('Embedding vectors have invalid dimensions or values')
    if metric=='cosine' and not query.any():raise ValueError('Cosine query vector must be nonzero')
    eligible=[item_id for item_id in dict.fromkeys(eligible_ids) if item_id in row and item_id!=record_id]
    base={'mode':'exact','metric':metric,'retrieval_dtype':'float32','embedding_space_id':space,'artifact_id':artifact.id,'eligible_count':len(eligible)}
    if not eligible or limit<1:return {**base,'results':[]}
    rows=np.fromiter((row[item_id] for item_id in eligible),dtype=np.int64,count=len(eligible))
    block=matrix[rows]
    if metric=='cosine':
        norms=np.linalg.norm(block,axis=1);norms[norms==0]=1
        distance=1-(block@query)/(norms*np.linalg.norm(query))
    else:distance=np.linalg.norm(block-query,axis=1)
    take=min(limit,len(eligible))
    best=np.argpartition(distance,take-1)[:take]
    best=best[np.lexsort((np.asarray(eligible,dtype=object)[best],distance[best]))]
    return {**base,'results':[{'id':eligible[i],'distance':float(distance[i])} for i in best]}

def similar_records(artifact:Artifact, record_id:str|None, eligible_ids:list[str], limit:int, cache_root:Path, *, query_vector:list[float]|None=None, artifact_dir:Path|None=None) -> dict:
    if artifact.data.get('bulk'):
        if artifact_dir is None:raise ValueError('Array-backed embeddings need the artifact store')
        return similar_records_bulk(artifact,record_id,eligible_ids,limit,artifact_dir,query_vector=query_vector)
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
