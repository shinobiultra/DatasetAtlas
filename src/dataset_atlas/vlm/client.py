"""A loopback model server, spoken to concurrently over the OpenAI-compatible API or Ollama's native one.

Batch runs send only to the machine they run on (vLLM, Ollama, LM Studio, llama.cpp, SGLang); an endpoint that is not
loopback is refused here regardless of what a provider is configured to allow, because dataset contents are never sent to an
external model by a batch job. Redirects are not followed and environment proxies are not used. Error text never echoes the
request, which may hold image data.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
import numpy as np

_RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class Completion:
    text: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float
    reasoned: bool = False  # the server reported reasoning text separately from the reply


class ModelServerError(Exception):
    """A request the server did not answer usefully. The message is safe to store: it never holds the prompt."""


def is_loopback(base_url: str) -> bool:
    host = urlsplit(base_url).hostname or ""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _origin(base_url: str) -> str:
    parts = urlsplit(base_url)
    return f"{parts.scheme}://{parts.netloc}"


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        message = body.get("error", body) if isinstance(body, dict) else body
        text = message.get("message") if isinstance(message, dict) else str(message)
    except ValueError:
        text = response.text
    return str(text or "")[:200].replace("\n", " ")


class ModelServer:
    """Settings for one server; every call is made through a fresh event loop so workers stay synchronous."""

    def __init__(self, provider: dict[str, Any], *, api: str = "auto", concurrency: int = 16, retries: int = 2):
        base = str(provider["base_url"]).rstrip("/")
        if not is_loopback(base):
            raise ValueError("Batch model runs send only to a loopback server; this endpoint is not loopback")
        if api not in {"auto", "openai", "ollama"}:
            raise ValueError("api must be auto, openai or ollama")
        if not 1 <= concurrency <= 256:
            raise ValueError("concurrency must be within 1..256")
        self.base_url = base
        self.origin = _origin(base)
        self.model = str(provider["model"])
        self.timeout = float(provider.get("timeout_seconds", 60))
        self.api_key = os.environ.get(provider["api_key_env"]) if provider.get("api_key_env") else None
        self.concurrency = concurrency
        self.retries = max(0, retries)
        self.api = self._detect() if api == "auto" else api

    def _detect(self) -> str:
        """Ollama answers GET /api/version with a version document; no OpenAI-compatible server does."""
        try:
            response = httpx.get(self.origin + "/api/version", timeout=3, follow_redirects=False, trust_env=False)
            if response.status_code == 200 and isinstance(response.json().get("version"), str):
                return "ollama"
        except (httpx.HTTPError, ValueError):
            pass
        return "openai"

    @property
    def _openai_root(self) -> str:
        return self.base_url if self.base_url.endswith("/v1") else self.base_url + "/v1"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    # -- chat -----------------------------------------------------------------
    def chat_request(self, messages: list[dict[str, Any]], *, max_tokens: int, temperature: float = 0.0, schema: dict[str, Any] | None = None,
                     thinking: bool | None = None, extra: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
        """(url, JSON body). ``messages`` are ``{"role", "text", "images": [base64 JPEG]}``."""
        extra = dict(extra or {})
        if self.api == "ollama":
            body: dict[str, Any] = {
                "model": self.model, "stream": False, "think": bool(thinking) if thinking is not None else False, "keep_alive": "30m",
                "messages": [{"role": m["role"], "content": m["text"], **({"images": m["images"]} if m.get("images") else {})} for m in messages],
                "options": {"temperature": temperature, "num_predict": max_tokens, **extra.pop("options", {})},
            }
            if schema is not None:
                body["format"] = schema
            body.update({key: value for key, value in extra.items() if key not in {"model", "messages", "stream"}})
            return self.origin + "/api/chat", body
        content = []
        for m in messages:
            if m.get("images"):
                parts = [{"type": "text", "text": m["text"]}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image}} for image in m["images"]]
                content.append({"role": m["role"], "content": parts})
            else:
                content.append({"role": m["role"], "content": m["text"]})
        body = {"model": self.model, "messages": content, "max_tokens": max_tokens, "temperature": temperature, "stream": False}
        if schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "atlas_output", "strict": True, "schema": schema}}
        if thinking is not None:
            body["chat_template_kwargs"] = {"enable_thinking": thinking}
        body.update({key: value for key, value in extra.items() if key not in {"model", "messages", "stream"}})
        return self._openai_root + "/chat/completions", body

    @staticmethod
    def _completion(api: str, data: dict[str, Any], started: float) -> Completion:
        latency = (time.perf_counter() - started) * 1000
        if api == "ollama":
            message = data.get("message") or {}
            return Completion(str(message.get("content") or ""), data.get("done_reason"), data.get("prompt_eval_count"), data.get("eval_count"), latency, bool(message.get("thinking")))
        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        message = choice.get("message") or {}
        return Completion(str(message.get("content") or ""), choice.get("finish_reason"), usage.get("prompt_tokens"), usage.get("completion_tokens"), latency,
                          bool(message.get("reasoning_content") or message.get("reasoning")))

    async def _post(self, client: httpx.AsyncClient, url: str, body: dict[str, Any]) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.post(url, json=body, headers=self._headers())
            except httpx.TimeoutException as exc:
                last = ModelServerError("The model server did not answer in time")
            except httpx.TransportError as exc:
                last = ModelServerError(f"Could not reach the model server ({type(exc).__name__})")
            else:
                if response.status_code == 200:
                    return response
                if 300 <= response.status_code < 400:
                    raise ModelServerError("The model server redirected the request; redirects are not followed")
                if response.status_code not in _RETRYABLE:
                    raise ModelServerError(f"HTTP {response.status_code}: {_detail(response)}")
                last = ModelServerError(f"HTTP {response.status_code}: {_detail(response)}")
            if attempt < self.retries:
                await asyncio.sleep(0.4 * 2 ** attempt)
        assert last is not None
        raise last

    def _client(self) -> httpx.AsyncClient:
        limits = httpx.Limits(max_connections=self.concurrency, max_keepalive_connections=self.concurrency)
        return httpx.AsyncClient(timeout=httpx.Timeout(self.timeout), limits=limits, follow_redirects=False, trust_env=False)

    def complete_many(self, requests: list[tuple[str, dict[str, Any]]]) -> list[Completion | ModelServerError]:
        """Answer every request with at most ``concurrency`` in flight; a failed request is returned, not raised."""
        async def run() -> list[Completion | ModelServerError]:
            gate = asyncio.Semaphore(self.concurrency)
            async with self._client() as client:
                async def one(url: str, body: dict[str, Any]):
                    async with gate:
                        started = time.perf_counter()
                        try:
                            response = await self._post(client, url, body)
                            return self._completion(self.api, response.json(), started)
                        except ModelServerError as exc:
                            return exc
                        except (ValueError, KeyError, AttributeError):
                            return ModelServerError("The model server's reply was not in the expected format")
                return list(await asyncio.gather(*(one(url, body) for url, body in requests)))
        return asyncio.run(run())

    # -- embeddings -----------------------------------------------------------
    def embed_many(self, texts: list[str], *, batch_size: int = 64) -> list[np.ndarray | ModelServerError]:
        """One vector (float32) per text, requested in batches; every text of a failed batch gets that error."""
        batches = [texts[start:start + batch_size] for start in range(0, len(texts), batch_size)]

        async def run():
            gate = asyncio.Semaphore(self.concurrency)
            async with self._client() as client:
                async def one(batch: list[str]):
                    async with gate:
                        try:
                            response = await self._post(client, self._openai_root + "/embeddings", {"model": self.model, "input": batch, "encoding_format": "float"})
                            rows = sorted(response.json()["data"], key=lambda item: item["index"])
                            if len(rows) != len(batch):
                                raise ModelServerError("The model server returned a different number of embeddings than inputs")
                            return [np.asarray(row["embedding"], dtype=np.float32) for row in rows]
                        except ModelServerError as exc:
                            return [exc] * len(batch)
                        except (ValueError, KeyError, TypeError):
                            return [ModelServerError("The model server's reply was not in the expected format")] * len(batch)
                return await asyncio.gather(*(one(batch) for batch in batches))
        return [item for batch in asyncio.run(run()) for item in batch]
