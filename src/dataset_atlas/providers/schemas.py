from __future__ import annotations

import ipaddress
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Capability = Literal[
    "text_generation", "single_image_input", "multiple_image_input",
    "structured_output", "tool_calls", "text_embeddings", "image_embeddings",
]
CAPABILITIES: tuple[Capability, ...] = (
    "text_generation", "single_image_input", "multiple_image_input",
    "structured_output", "tool_calls", "text_embeddings", "image_embeddings",
)
ToolName = Literal[
    "describe_dataset", "describe_fields", "search_records", "get_records",
    "aggregate", "inspect_images", "get_run_results",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderConfig(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    base_url: str
    model: str = Field(min_length=1, max_length=256)
    api_key_env: str | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_output_tokens: int = Field(default=512, ge=1, le=4096)
    reasoning_effort: Literal['none','minimal','low','medium','high','xhigh','max'] | None = None
    max_input_characters: int = Field(default=20000, ge=1, le=100000)
    max_images: int = Field(default=8, ge=0, le=8)
    allow_external: bool = False

    @field_validator("api_key_env")
    @classmethod
    def valid_env_ref(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value):
            raise ValueError("api_key_env must name an environment variable")
        return value

    @field_validator("base_url")
    @classmethod
    def valid_endpoint(cls, value: str) -> str:
        p = urlsplit(value)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise ValueError("base_url must be an HTTP(S) endpoint without credentials, query, or fragment")
        if p.path.rstrip("/") not in ("", "/v1"):
            raise ValueError("base_url path must be empty or /v1")
        if p.hostname.lower() == "localhost":
            local = True
        else:
            try:
                local = ipaddress.ip_address(p.hostname).is_loopback
            except ValueError:
                local = False
        if p.scheme == "http" and not local:
            raise ValueError("non-loopback providers require HTTPS")
        return value.rstrip("/")

    @model_validator(mode="after")
    def external_opt_in(self) -> "ProviderConfig":
        host = urlsplit(self.base_url).hostname or ""
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host.lower() == "localhost"
        if not local and not self.allow_external:
            raise ValueError("external provider requires allow_external=true")
        return self


class CapabilityResult(StrictModel):
    status: Literal["unknown", "supported", "unsupported"] = "unknown"
    tested_at: str | None = None
    detail: str = "not tested"


class ProviderView(StrictModel):
    config: ProviderConfig
    capabilities: dict[Capability, CapabilityResult]


class ContextRequest(StrictModel):
    provider_id: str
    record_ids: list[str] = Field(min_length=1, max_length=100)
    snapshot_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)
    result_snapshot_ids: list[str] = Field(default_factory=list, max_length=32)
    mode: Literal["exploration", "evaluation"] = "exploration"
    fields: list[str] = Field(default_factory=list, max_length=64)
    include_annotations: bool = False
    image_asset_ids: list[str] = Field(default_factory=list, max_length=8)
    independent_records: bool = False

    @model_validator(mode="after")
    def unique_ids(self) -> "ContextRequest":
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValueError("record_ids must be unique")
        if len(set(self.image_asset_ids)) != len(self.image_asset_ids):
            raise ValueError("image_asset_ids must be unique")
        if len(set(self.result_snapshot_ids)) != len(self.result_snapshot_ids) or len(set(self.fields)) != len(self.fields):
            raise ValueError('Result snapshots and context fields must be unique')
        if self.result_snapshot_ids and not self.snapshot_ids:
            raise ValueError('Selected results require explicit dataset snapshot IDs')
        return self


class ContextPreview(StrictModel):
    context_digest: str
    provider_id: str
    model: str
    record_ids: list[str]
    mode: Literal["exploration", "evaluation"]
    outgoing: list[dict[str, Any]]
    delivery: Literal["joint", "independent"] = "joint"
    per_record_contexts: list[dict[str, Any]] = Field(default_factory=list)
    image_representations: list[dict[str, Any]]
    notices: list[str]
    policy: dict[str, Any]
    external_send_allowed: bool = False
    external_send_reason: str | None = None


class ConversationRequest(StrictModel):
    context: ContextRequest
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_provider_id: str
    approved_record_ids: list[str]
    prompt: str = Field(min_length=1, max_length=10000)
    use_tools: bool = False
    required_tool: ToolName | None = None
    max_iterations: int = Field(default=8, ge=1, le=8)
    max_tool_calls: int = Field(default=16, ge=0, le=16)
    max_tool_rows: int = Field(default=1000, ge=0, le=1000)
    max_batch_completion_tokens: int = Field(default=8192, ge=1, le=100000)
    deadline_seconds: float = Field(default=60, gt=0, le=120)

    @model_validator(mode="after")
    def tool_choice_valid(self) -> "ConversationRequest":
        if self.required_tool and not self.use_tools:
            raise ValueError("required_tool needs use_tools=true")
        return self


class ToolResult(StrictModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    population_scope: str
    coverage: dict[str, Any] = Field(default_factory=dict)
    truncated: bool = False


class ConversationResult(StrictModel):
    id: str
    provider_id: str
    model: str
    context_digest: str
    record_ids: list[str]
    mode: Literal["exploration", "evaluation"]
    prompt: str
    response: str | None
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any]
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str


class ConversationSummary(StrictModel):
    id: str
    provider_id: str
    model: str
    context_digest: str
    record_ids: list[str]
    mode: Literal["exploration", "evaluation"]
    response: str | None
    error: str | None
    created_at: str


class BatchConversationResult(StrictModel):
    batch_id: str
    provider_id: str
    model: str
    context_digest: str
    record_ids: list[str]
    completed_record_ids: list[str]
    pending_record_ids: list[str]
    results: list[ConversationResult]
    status: Literal["complete", "partial"]
    created_at: str
