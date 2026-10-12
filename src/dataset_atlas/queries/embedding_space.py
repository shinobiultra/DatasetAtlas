"""Registered local embedding artifacts, including explicitly described vector imports."""
from __future__ import annotations

import math
from pathlib import Path

from dataset_atlas.models import Artifact, content_id


def is_embedding_artifact(artifact: Artifact) -> bool:
    provenance = artifact.provenance.get('processor_provenance', {})
    return artifact.kind.startswith('embed.') or (artifact.kind == 'import.research' and
           provenance.get('kind') == 'vector' and provenance.get('registered_embedding_space') is True)


def bulk_directory(artifact: Artifact, artifact_dir: Path | None = None) -> Path:
    """The array bundle directory of an array-backed artifact, confined to the artifact store."""
    bulk = artifact.data.get('bulk')
    if not isinstance(bulk, dict) or not isinstance(bulk.get('dir'), str):
        raise ValueError('Artifact is not array-backed')
    store = artifact_dir or artifact._store_root
    if store is None:
        raise ValueError('Array-backed artifact was not loaded from an artifact store')
    root = Path(store).resolve()
    directory = (root / bulk['dir']).resolve()
    if directory.parent != root / 'arrays' or not directory.is_dir():
        raise ValueError('Array bundle is missing or outside the artifact store')
    return directory


def embedding_source(artifact: Artifact, artifact_dir: Path):
    """Reference (not copy) to an array-backed embedding artifact's vectors for an analysis run.

    Returns ``(vector_source, provenance, metric)``; the source is checksum-verified when a worker reads it.
    """
    if not is_embedding_artifact(artifact):
        raise ValueError('Choose an embedding artifact or an explicitly registered vector import')
    provenance = artifact.provenance.get('processor_provenance', {})
    if not provenance.get('embedding_space_id'):
        raise ValueError('Embedding space provenance is missing')
    bulk = artifact.data['bulk']
    if 'vector' not in bulk.get('arrays', {}):
        raise ValueError('Array-backed embedding artifact has no vector array')
    metric = provenance.get('embedding_space', {}).get('metric', 'cosine')
    if metric not in {'cosine', 'euclidean'}:
        raise ValueError('Embedding space metric is unsupported')
    source = {'artifact_id': artifact.id, 'dir': str(bulk_directory(artifact, artifact_dir)), 'array': 'vector',
              'manifest': {key: bulk[key] for key in ('count', 'ids', 'arrays')}}
    return source, provenance, metric


def embedding_vectors(artifact: Artifact):
    if artifact.data.get('bulk'):
        raise ValueError('This embedding is array-backed; read it with embedding_source or bulk_matrix, not as a dict of lists')
    if not is_embedding_artifact(artifact):
        raise ValueError('Choose an embedding artifact or an explicitly registered vector import')
    provenance = artifact.provenance.get('processor_provenance', {})
    if not provenance.get('embedding_space_id'):
        raise ValueError('Embedding space provenance is missing')
    vectors = {}
    imported = artifact.kind == 'import.research'
    space = provenance.get('embedding_space', {})
    if imported:
        if not isinstance(space, dict) or set(space) != {'model_revision', 'representation', 'metric', 'normalized', 'dimension', 'sample_unit'}:
            raise ValueError('Registered embedding space schema is invalid')
        if any(not isinstance(space[key], str) or not space[key].strip() or len(space[key]) > 2048 for key in ('model_revision', 'representation')):
            raise ValueError('Embedding model revision and representation must be explicit')
        if type(space['dimension']) is not int or not 1 <= space['dimension'] <= 4096 or space['sample_unit'] != artifact.unit or type(space['normalized']) is not bool:
            raise ValueError('Embedding space dimension, unit or normalization is invalid')
        if content_id(space, 'embedding-space:') != provenance['embedding_space_id']:
            raise ValueError('Registered embedding space identity does not match its recipe')
    allowed = set(artifact.ids)
    if len(allowed) != len(artifact.ids):
        raise ValueError('Embedding artifact subject IDs must be unique')
    seen = set()
    dimension = None
    for item in artifact.data.get('items', []):
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in seen or item['id'] not in allowed:
            raise ValueError('Embedding artifact requires unique stable item IDs')
        seen.add(item['id'])
        if item.get('status') != 'completed':
            continue
        vector = (item.get('output') or {}).get('vector')
        if not isinstance(vector, list) or not 1 <= len(vector) <= 4096 or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
            raise ValueError('Completed embedding vectors must have bounded finite dimensions')
        if dimension is not None and len(vector) != dimension:
            raise ValueError('Embedding vectors have inconsistent dimensions')
        dimension = len(vector)
        if imported and (dimension != space['dimension'] or any(abs(value) > 3.4028234663852886e38 for value in vector)):
            raise ValueError('Registered vectors disagree with their dimension or exceed the float32 retrieval range')
        if imported and space['normalized'] and not math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0, abs_tol=1e-5):
            raise ValueError('Registered vectors disagree with declared normalization')
        vectors[item['id']] = vector
    metric = space.get('metric', 'cosine')
    if metric not in {'cosine', 'euclidean'}:
        raise ValueError('Embedding space metric is unsupported')
    if metric == 'cosine' and any(not any(value != 0 for value in vector) for vector in vectors.values()):
        raise ValueError('Cosine embedding spaces require nonzero vectors')
    return vectors, provenance, metric
