"""Rebuildable LanceDB exact retrieval over an explicitly eligible population."""
from pathlib import Path
import math
import heapq
import importlib
import sys
from collections import OrderedDict
from threading import RLock
from dataset_atlas.models import Artifact,content_id
from dataset_atlas.processors.analysis import exact_lancedb_search
from .embedding_space import bulk_directory,embedding_vectors

_matrices=OrderedDict()  # Verified mappings and identity lookups, least recently used first.
_MATRIX_CACHE=2
_MATRIX_CACHE_BYTES=1024**3
_DISTANCE_BLOCK_BYTES=16*1024*1024
_matrix_lock=RLock()

def _bulk_matrix(artifact:Artifact, artifact_dir:Path):
    import numpy as np
    from dataset_atlas.storage import arrays as store
    bulk=artifact.data['bulk']
    directory=bulk_directory(artifact,artifact_dir)
    key=(str(directory),artifact.id,content_id(bulk))
    with _matrix_lock:
        entry=_matrices.get(key)
        if entry is not None:
            _matrices.move_to_end(key)
            return entry[0]
        ids=store.read_ids(directory,bulk)
        # Keep the verified file mapped; a whole-matrix dtype conversion defeats
        # bounded retrieval for float16/float64 inputs. Convert only each scored block.
        matrix=store.read_array(directory,bulk['arrays']['vector'],verify=True)
        if matrix.ndim!=2 or matrix.shape[0]!=len(ids) or not matrix.shape[1] or len(set(ids))!=len(ids):
            raise ValueError('Embedding vectors have invalid dimensions or values')
        rows={item_id:row for row,item_id in enumerate(ids)}
        cached=(ids,rows,matrix)
        # This cap counts mapped numeric bytes plus the Python identity lookup,
        # not process RSS (file-backed pages are managed by the operating system).
        size=(matrix.nbytes+sys.getsizeof(matrix)+sys.getsizeof(ids)+sys.getsizeof(rows)
              +sum(sys.getsizeof(item_id)+sys.getsizeof(index) for item_id,index in rows.items()))
        if size<=_MATRIX_CACHE_BYTES and _MATRIX_CACHE>0:
            while _matrices and (len(_matrices)>=_MATRIX_CACHE or sum(entry[1] for entry in _matrices.values())+size>_MATRIX_CACHE_BYTES):
                _matrices.popitem(last=False)
            _matrices[key]=(cached,size)
        return cached


def _top_indices(distance, ids, limit):
    """Select exact top-k, including the ID tie-break at the partition boundary."""
    import numpy as np
    if len(distance)<=limit:
        best=np.arange(len(distance))
    else:
        cutoff=np.partition(distance,limit-1)[limit-1]
        best=np.flatnonzero(distance<cutoff)
        tied=np.flatnonzero(distance==cutoff)
        remaining=limit-len(best)
        if len(tied)>remaining:
            tied=np.asarray(heapq.nsmallest(remaining,tied,key=ids.__getitem__),dtype=np.int64)
        best=np.concatenate((best,tied))
    return best[np.lexsort((np.asarray([ids[i] for i in best],dtype=object),distance[best]))]

def similar_records_bulk(artifact:Artifact, record_id:str|None, eligible_ids:list[str], limit:int, artifact_dir:Path, *, query_vector:list[float]|None=None) -> dict:
    """Exhaustively score eligible rows in bounded blocks, retaining exact top-k."""
    import numpy as np
    provenance=artifact.provenance.get('processor_provenance',{})
    space=provenance.get('embedding_space_id')
    if not space:raise ValueError('Embedding space provenance is missing')
    metric=provenance.get('embedding_space',{}).get('metric','cosine')
    ids,row,matrix=_bulk_matrix(artifact,artifact_dir)
    if query_vector is None:
        if record_id not in row:raise ValueError('Query record has no completed vector in this embedding space')
        query=np.asarray(matrix[row[record_id]],dtype=np.float32)
    else:query=np.asarray(query_vector,dtype=np.float32)
    if query.ndim!=1 or query.shape[0]!=matrix.shape[1] or not np.isfinite(query).all():raise ValueError('Embedding vectors have invalid dimensions or values')
    if metric=='cosine' and not query.any():raise ValueError('Cosine query vector must be nonzero')
    eligible=[item_id for item_id in dict.fromkeys(eligible_ids) if item_id in row and item_id!=record_id]
    base={'mode':'exact','metric':metric,'retrieval_dtype':'float32','embedding_space_id':space,'artifact_id':artifact.id,'eligible_count':len(eligible)}
    if not eligible or limit<1:return {**base,'results':[]}
    take=min(limit,len(eligible))
    # Account for either the stored or retrieval dtype. One very wide row is the
    # minimum unit; no gather grows with the eligible population's total size.
    block_rows=max(1,_DISTANCE_BLOCK_BYTES//(matrix.shape[1]*max(matrix.dtype.itemsize,4)))
    query_norm=np.linalg.norm(query) if metric=='cosine' else None
    best_ids=[]
    best_distance=np.empty(0,dtype=np.float32)
    for start in range(0,len(eligible),block_rows):
        block_ids=eligible[start:start+block_rows]
        rows=np.fromiter((row[item_id] for item_id in block_ids),dtype=np.int64,count=len(block_ids))
        block=np.asarray(matrix[rows],dtype=np.float32)
        if not np.isfinite(block).all():raise ValueError('Embedding vectors have invalid dimensions or values')
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
            if metric=='cosine':
                norms=np.sqrt(np.einsum('ij,ij->i',block,block))
                norms[norms==0]=1
                distance=np.einsum('ij,j->i',block,query)
                distance/=norms*query_norm
                np.subtract(1,distance,out=distance)
                np.maximum(distance,0,out=distance)
            else:
                block-=query
                distance=np.sqrt(np.einsum('ij,ij->i',block,block))
        del block  # Do not retain the preceding gather while allocating the next one.
        if not np.isfinite(distance).all():raise ValueError('Embedding vectors have invalid dimensions or values')
        local=_top_indices(distance,block_ids,take)
        candidates=best_ids+[block_ids[i] for i in local]
        candidate_distance=np.concatenate((best_distance,distance[local]))
        best=_top_indices(candidate_distance,candidates,take)
        best_ids=[candidates[i] for i in best]
        best_distance=candidate_distance[best]
    return {**base,'results':[{'id':item_id,'distance':float(distance)} for item_id,distance in zip(best_ids,best_distance)]}

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
    lancedb=importlib.import_module('lancedb')
    database=lancedb.connect(str(cache_root))
    name='atlas_'+content_id({'artifact':artifact.id,'space':space,'vectors':vectors})
    try:table=database.open_table(name)
    except Exception:
        table=database.create_table(name,[{'id':id,'vector':v} for id,v in vectors.items()],exist_ok=True)
    rows=exact_lancedb_search(table,vector,eligible,limit,metric='l2' if metric=='euclidean' else metric)
    return {'mode':'exact','metric':metric,'retrieval_dtype':'float32','embedding_space_id':space,'artifact_id':artifact.id,'eligible_count':len(eligible),'results':[{'id':row['id'],'distance':row['_distance']} for row in rows]}
