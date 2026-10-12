"""Batch work against a local model server: answers, tags, verdicts and embeddings at dataset scale.

Everything here talks only to loopback servers (vLLM, Ollama, LM Studio, llama.cpp, SGLang) and runs inside job
workers, so the usual estimate-then-approve flow, resumable shards and provenance apply.
"""
