"""Named local source credentials; never serialized into plans or request receipts."""
from __future__ import annotations
import os
from pathlib import Path


def source_headers(profile, host):
    if profile is None:return {}
    if profile!='huggingface':raise ValueError('Unknown source credential profile')
    # Signed CDN redirects must never receive the Hub bearer credential.
    if host!='huggingface.co':return {}
    token=os.environ.get('HF_TOKEN')
    if not token:
        home=Path(os.environ.get('HF_HOME',str(Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'huggingface')))
        path=Path(os.environ.get('HF_TOKEN_PATH',str(home/'token')))
        if path.is_file():
            with path.open() as stream:token=stream.read(4097)
    token=(token or '').strip()
    if not token:raise ValueError('Hugging Face credentials are missing; sign in locally or register authorized source files')
    if len(token)>4096 or not token.isascii() or any(c.isspace() for c in token):raise ValueError('Invalid local Hugging Face credential')
    return {'Authorization':'Bearer '+token}
