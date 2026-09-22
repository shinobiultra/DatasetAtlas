"""Local query encoding against a registered embedding artifact's recipe."""
from __future__ import annotations

from typing import Any

from dataset_atlas.models import Artifact, Record
from .embeddings import compatible_siglip2_spaces, run_embeddings


def encode_text_query(artifact: Artifact | dict[str, Any], source_run_config: dict[str, Any], text: str) -> list[float]:
    """Encode bounded text only when the local model matches an existing space.

    For MiniLM, the query must reproduce the artifact's text/question recipe.
    SigLIP 2 image artifacts accept a compatible text encoder from the same
    weights; their representation identities stay distinct. No download or
    remote embedding provider is used.
    """
    artifact = Artifact.model_validate(artifact)
    if artifact.kind not in {"embed.minilm", "embed.siglip2"}:
        raise ValueError("Text query requires a MiniLM or SigLIP 2 embedding artifact")
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("Text query must contain 1..4000 characters")
    if not isinstance(source_run_config, dict):
        raise ValueError("Source run configuration is required")
    saved = artifact.provenance.get("processor_provenance", {})
    if not isinstance(saved, dict) or not isinstance(saved.get("recipe"), dict):
        raise ValueError("Embedding artifact has no complete recipe provenance")
    for key in ("model_revision", "model_sha256"):
        if not saved.get(key) or source_run_config.get(key) != saved[key]:
            raise ValueError(f"Source run {key} differs from embedding artifact")
    recipe = saved["recipe"]
    source_mode = recipe.get("representation")
    if artifact.kind == "embed.minilm":
        if source_mode not in {"text", "question"}:
            raise ValueError("MiniLM artifact is not a text representation")
        query_mode = source_mode
    else:
        if source_mode not in {"image", "text", "question"}:
            raise ValueError("Unsupported SigLIP 2 source representation")
        query_mode = "text" if source_mode == "image" else source_mode
    config = {**source_run_config, "representation": query_mode}
    record = Record(id="__local_query__", dataset_id="__query__", release_id="__query__",
                    snapshot_id=artifact.snapshot_ids[0] if artifact.snapshot_ids else "__query__",
                    text=text if query_mode == "text" else None,
                    question=text if query_mode == "question" else None)
    items, generated = run_embeddings(artifact.kind, [record], config)
    if len(items) != 1 or items[0]["status"] != "completed":
        raise ValueError(f"Local query embedding failed: {items[0].get('error') if items else 'no result'}")
    if artifact.kind == "embed.minilm" or source_mode in {"text", "question"}:
        if generated["embedding_space_id"] != saved.get("embedding_space_id"):
            raise ValueError("Query embedding recipe does not match artifact")
    elif not compatible_siglip2_spaces(saved, generated):
        raise ValueError("SigLIP 2 text query is not compatible with image artifact")
    vector = items[0]["output"]["vector"]
    if len(vector) != recipe.get("dimension"):
        raise ValueError("Query vector dimension differs from artifact recipe")
    return vector
