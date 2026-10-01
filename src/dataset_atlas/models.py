"""Canonical v1 contracts. JSON Schema and TypeScript are generated from these models."""
from __future__ import annotations
import hashlib
import json
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Unit = Literal['asset', 'example', 'entity', 'conversation']

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Versioned(Model):
    schema_version: str = '1.0'
    @field_validator('schema_version')
    @classmethod
    def major_version(cls, value: str) -> str:
        if value.split('.')[0] != '1':
            raise ValueError('Unsupported schema major version; use an Atlas reader supporting ' + value)
        return value

class Coverage(Model):
    identity: str = 'candidate'
    source: str = 'missing'
    access: str = 'unavailable'
    adapter: str = 'not_started'
    preview: str = 'none'
    complete_data: str = 'unimplemented'
    publication: str = 'not_reviewed'
    preview_count: int = 0
    total_count: int | None = None
    unit: Unit = 'example'
    blockers: list[str] = Field(default_factory=list)

class Availability(Model):
    """What this deployment holds right now; computed per request and never stored in the registry.

    `Coverage` records what a maintainer prepared on their machine. A colleague's fresh
    workspace holds none of that until it is fetched, so the two must not be conflated."""
    preview: Literal['local', 'on_request', 'none'] = 'none'
    complete_data: Literal['local', 'on_request', 'none'] = 'none'
    upstream_preview_count: int = 0

class Dataset(Versioned):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ''
    tasks: list[str] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    source_url: str | None = None
    release: str = 'unresolved'
    snapshot_id: str = ''
    adapter: str = 'structured'
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    coverage: Coverage = Field(default_factory=Coverage)
    availability: Availability | None = None
    rights: dict[str, str] = Field(default_factory=dict)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)

class Release(Versioned):
    id: str
    dataset_id: str
    revision: str
    snapshot_id: str
    source: dict[str, Any] = Field(default_factory=dict)
    measurements: list[dict[str, Any]] = Field(default_factory=list)

class Asset(Model):
    id: str
    dataset_id: str
    release_id: str
    modality: str
    uri: str | None = None
    text: str | None = None
    representation: str = 'original'
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class Entity(Model):
    id: str
    asset_id: str
    dataset_id: str
    release_id: str
    geometry: dict[str, Any] = Field(default_factory=dict)
    coordinate_system: str = 'original_exif_oriented_pixels'
    provenance: dict[str, Any] = Field(default_factory=dict)

class Measurement(Model):
    value: float
    unit: str
    scope: Literal['reported_upstream','reported_in_paper','complete_available_release','preview','filtered_selection']
    release_id: str
    split: str | None = None
    selection_id: str | None = None
    source: dict[str, Any]
    method: str


class Annotation(Model):
    id: str
    subject_id: str
    subject_unit: Unit
    namespace: Literal['source','prediction','human'] = 'source'
    field_id: str
    value: Any = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    annotator: str | None = None
    aggregation: str | None = None

class Relation(Model):
    subject_id: str
    object_id: str
    type: str
    provenance: dict[str, Any] = Field(default_factory=dict)

class Record(Versioned):
    id: str
    dataset_id: str
    release_id: str
    snapshot_id: str
    unit: Unit = 'example'
    asset_ids: list[str] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    text: str | None = None
    question: str | None = None
    choices: list[Any] = Field(default_factory=list)
    conversation: list[dict[str, Any]] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    prediction: dict[str, Any] = Field(default_factory=dict)
    human: dict[str, Any] = Field(default_factory=dict)
    annotations: list[Annotation] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)

class FieldDescriptor(Model):
    id: str
    name: str
    dtype: Literal['string','number','boolean','category','array','object'] = 'string'
    namespace: Literal['source','prediction','human','record'] = 'source'
    values: list[Any] | None = None
    unit: Unit = 'example'
    description: str = ''
    provenance: dict[str, Any] = Field(default_factory=dict)
    query_ops: list[str] = Field(default_factory=lambda:['eq','ne','in','contains','is_null'])

class Query(Model):
    population_scope: Literal['preview','complete'] = 'preview'
    result_snapshot_ids: list[str] = Field(default_factory=list, max_length=32)
    snapshot_id: str
    unit: Unit = 'example'
    filter: dict[str, Any] | None = None
    search: str = ''
    sort: list[dict[str, str]] = Field(default_factory=list, max_length=4)
    limit: int = Field(default=100, ge=1, le=1000)
    cursor: str | None = None
    sample: dict[str, Any] | None = None

class QueryResult(Model):
    snapshot_id: str
    unit: Unit
    population_scope: str
    records: list[Record]
    returned_count: int
    matched_count: int | None
    count_status: Literal['exact','estimated','unknown'] = 'exact'
    coverage: dict[str, Any] = Field(default_factory=dict)
    ordering: list[dict[str,str]] = Field(default_factory=list)
    cursor: str | None = None
    warnings: list[str] = Field(default_factory=list)

class Selection(Versioned):
    id: str
    name: str = 'Untitled selection'
    ids: list[str]
    unit: Unit
    snapshot_ids: list[str]
    dataset_ids: list[str]
    method: str = 'manual'
    seed: int | None = None
    query: dict[str, Any] = Field(default_factory=dict)
    created_at: str

class Run(Versioned):
    id: str
    processor_id: str
    selection_id: str
    status: str = 'queued'
    config: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    created_at: str
    completed_at: str | None = None

class Artifact(Versioned):
    id: str
    kind: str
    run_id: str | None = None
    snapshot_ids: list[str]
    unit: Unit
    ids: list[str]
    files: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)

class Capabilities(Versioned):
    mode: Literal['static','workbench']
    operations: list[str]
    api_version: str = '1'
    limits: dict[str, int] = Field(default_factory=lambda:{'query_rows':1000,'tool_calls':16,'tool_rows':1000,'tool_images':8,'tool_iterations':8})

class Pack(Versioned):
    dataset: Dataset
    fields: list[FieldDescriptor]
    records: list[Record]
    artifacts: list[Artifact] = Field(default_factory=list)
    population_scope: str = 'preview'
    sampling: dict[str, Any] = Field(default_factory=dict)
    checksums: dict[str, str] = Field(default_factory=dict)

def stable_id(dataset: str, release: str, unit: str, source_id: str) -> str:
    value = json.dumps([dataset, release, unit, source_id], ensure_ascii=False, separators=(',',':'))
    return f'{dataset}:{unit}:{hashlib.sha256(value.encode()).hexdigest()[:24]}'

def content_id(value: Any, prefix: str = '') -> str:
    return prefix + hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()[:24]
