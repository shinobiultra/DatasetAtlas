"""Trusted, local Atlas processors. Heavy model packages are imported only on use."""
from .core import describe_processors, get_processor, run_processor
from .queries import encode_text_query

__all__ = ["describe_processors", "get_processor", "run_processor", "encode_text_query"]
