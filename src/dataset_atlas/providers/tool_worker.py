"""Disposable metadata-only tools; no media resolution or data acquisition."""
from __future__ import annotations
import json
from pathlib import Path
import resource
import sqlite3
import sys

from dataset_atlas.models import Artifact, Query, Run
from dataset_atlas.registry import Registry
from dataset_atlas.api.tools import make_tool_backend
from .tools import execute_tool


class ReadOnlyJobs:
    def __init__(self, root):
        self.path = Path(root)/'work/jobs.sqlite3'
    def _read(self, table, column, identity):
        with sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True) as db:
            row = db.execute(f'SELECT {column} FROM {table} WHERE id=?',(identity,)).fetchone()
        if row is None: raise ValueError('Read-only run result is unavailable')
        return row[0]
    def get_run(self, identity):
        return Run.model_validate_json(self._read('runs','run_json',identity))
    def get_artifact(self, identity):
        return Artifact.model_validate_json(self._read('artifacts','artifact_json',identity))


def main():
    resource.setrlimit(resource.RLIMIT_CPU,(120,121))
    resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000))
    payload = sys.stdin.buffer.read(1_000_001)
    if len(payload) > 1_000_000: raise ValueError('Oversized read-only tool request')
    request = json.loads(payload)
    registry = Registry(Path(request['root']))
    scope = frozenset(request['scope'])
    if not 1 <= len(scope) <= 1000: raise ValueError('Invalid approved tool scope')
    bindings=request.get('record_versions')
    if bindings is not None and (not isinstance(bindings,dict) or set(bindings)!=scope):
        raise ValueError('Invalid approved snapshot bindings')
    packs = {}; snapshots = {}
    result_ids=request.get('result_snapshot_ids',[])
    if not isinstance(result_ids,list) or len(result_ids)>32 or len(set(result_ids))!=len(result_ids) or any(not isinstance(identity,str) for identity in result_ids):
        raise ValueError('Invalid approved result bindings')
    jobs=ReadOnlyJobs(registry.root) if request['jobs'] else None
    results=[]
    from dataset_atlas.registry.artifacts import RetainedArtifactIndex
    artifact_index=RetainedArtifactIndex(registry)
    approved_snapshots={value['snapshot_id'] for value in bindings.values()} if bindings is not None else None
    approved_datasets={value['dataset_id'] for value in bindings.values()} if bindings is not None else None
    packed_results=None
    for identity in result_ids:
        artifact=None
        if jobs:
            try:artifact=jobs.get_artifact(identity)
            except ValueError:pass
        if artifact is None:
            if packed_results is None:packed_results={item.id:item for item in artifact_index.list(approved_snapshots,approved_datasets)}
            artifact=packed_results.get(identity)
        if artifact is None:raise ValueError('Approved result is unavailable')
        results.append(artifact)
    def native_lookup(identity):
        if identity not in scope: raise ValueError('Record outside approved tool scope')
        binding=bindings[identity] if bindings is not None else None
        prefix = identity.split(':',1)[0]
        candidates = [prefix] if registry.has(prefix) else registry.ids()
        for dataset_id in candidates:
            for dataset,pack_path,snapshot_path in registry.versions(dataset_id):
                if binding is not None and (dataset.id,dataset.release,dataset.snapshot_id)!=(binding.get('dataset_id'),binding.get('release_id'),binding.get('snapshot_id')):continue
                if not pack_path.is_file(): continue
                key = str(pack_path)
                if key not in packs:
                    from dataset_atlas.models import Pack
                    if pack_path.stat().st_size > 100_000_000:
                        raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
                    pack = Pack.model_validate_json(pack_path.read_text())
                    packs[key] = {record.id:record for record in pack.records}
                if identity in packs[key]: return packs[key][identity]
                if (snapshot_path/'manifest.json').is_file():
                    from dataset_atlas.queries.parquet import ParquetSnapshot
                    if str(snapshot_path) not in snapshots:
                        snapshots[str(snapshot_path)] = ParquetSnapshot(snapshot_path.parent,snapshot_path)
                    snapshot = snapshots[str(snapshot_path)]
                    result = snapshot.query(Query(snapshot_id=snapshot.snapshot_id,population_scope='complete',unit=snapshot.unit,
                        filter={'field_id':'id','op':'eq','value':identity},limit=1))
                    if result.records: return result.records[0]
        return None
    def lookup(identity):
        record=native_lookup(identity)
        if record is None or not results:return record
        chosen=[artifact for artifact in results if record.snapshot_id in artifact.snapshot_ids and record.unit==artifact.unit]
        if not chosen:return record
        from dataset_atlas.models import Pack
        from dataset_atlas.queries.results import attach_results
        dataset=registry.dataset_version(record.dataset_id,record.release_id,record.snapshot_id)
        return attach_results(Pack(dataset=dataset,fields=[],records=[record]),chosen).records[0]
    backend = make_tool_backend(registry,lookup,jobs,results)
    receipt = execute_tool(request['name'],request['arguments'],backend,scope,request['remaining_rows'],request['mode'])
    output = json.dumps({'receipt':receipt},ensure_ascii=False).encode()
    if len(output) > 120_000: raise ValueError('Oversized read-only tool result')
    sys.stdout.buffer.write(output)


if __name__ == '__main__':
    try: main()
    except Exception:
        # Do not surface source data, exception arguments, paths or credentials.
        sys.stdout.write(json.dumps({'error':'Read-only tool could not resolve the approved metadata within its bounds'}))
