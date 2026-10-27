"""Artifact-aligned membership of a complete query, independent of browse pages.

Only identities leave the query engine. Samples are chosen over the entire
filtered population before intersecting the artifact's subjects, so a map does
not silently resample its own subset or stop at the loaded record limit.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from dataset_atlas.models import Artifact, Pack, Query
from dataset_atlas.queries import materialize_records, query_pack
from dataset_atlas.queries.results import attach_results

if TYPE_CHECKING:
    from dataset_atlas.queries.parquet import ParquetSnapshot

# Matches the existing bulk-analysis subject ceiling. The additional identity
# byte budget bounds Arrow input independently of potentially very long IDs;
# the returned uint8 mask is at most 2 MB. Neither bound truncates a response.
MAX_MEMBERSHIP_ROWS = 2_000_000
MAX_MEMBERSHIP_ID_BYTES = 128_000_000


def membership_mask(
    query: Query,
    artifact: Artifact,
    *,
    ids: Sequence[str] | None = None,
    pack: Pack | None = None,
    snapshot: ParquetSnapshot | None = None,
    artifacts: Sequence[Artifact] = (),
) -> bytes:
    """One uint8 0/1 byte per registered artifact subject, in exactly its order.

    Supply exactly one pinned source. For array-backed artifacts the caller
    supplies ``ids`` after validating the registered bundle; this helper never
    opens a caller-provided path. Inline artifacts use their registered IDs.
    ``limit`` and ``cursor`` describe a browse page and do not affect membership.
    All filters, search, sorting that affects a source sample, and sampling do.
    """
    if (pack is None) == (snapshot is None):
        raise ValueError("Membership requires exactly one pack or Parquet snapshot")
    if artifact.snapshot_ids != [query.snapshot_id]:
        raise ValueError("Artifact snapshot differs from the membership query snapshot")
    if artifact.unit != query.unit:
        raise ValueError("Artifact unit differs from the membership query unit")
    selected = query.result_snapshot_ids
    if len(selected) != len(set(selected)) or set(selected) != {item.id for item in artifacts} or len(artifacts) != len(selected):
        raise ValueError("Explicit result snapshot IDs must match supplied artifacts")
    for item in artifacts:
        if item.snapshot_ids != [query.snapshot_id] or item.unit != query.unit:
            raise ValueError("Selected result snapshot or unit differs from the membership query")
    subjects = _subjects(artifact, ids)
    _sample_options(query, None)
    if pack is not None:
        # The pack engine implements the canonical preview ordering and samples.
        # Raising only its internal page size avoids repeated pagination scans;
        # query_pack returns references to the already materialized records.
        joined = attach_results(pack, list(artifacts)) if artifacts else pack
        available = len(materialize_records(joined, query.unit))
        population_query = query.model_copy(update={"cursor": None, "limit": max(1, available)})
        result = query_pack(joined, population_query)
        matched = {record.id for record in result.records}
        return bytes(int(identity in matched) for identity in subjects)
    assert snapshot is not None
    return _snapshot_mask(snapshot, query, subjects, artifacts)


def _subjects(artifact: Artifact, supplied: Sequence[str] | None) -> Sequence[str]:
    bulk = artifact.data.get("bulk")
    if isinstance(bulk, dict):
        if supplied is None:
            raise ValueError("Array-backed membership requires explicit validated IDs")
        if type(bulk.get("count")) is not int or bulk["count"] < 0 or len(supplied) != bulk["count"]:
            raise ValueError("Membership ID count differs from the registered array count")
        subjects = supplied
    else:
        if supplied is not None and list(supplied) != artifact.ids:
            raise ValueError("Membership IDs differ from the registered artifact")
        subjects = artifact.ids
    if len(subjects) > MAX_MEMBERSHIP_ROWS:
        raise ValueError(f"Membership exceeds its {MAX_MEMBERSHIP_ROWS:,}-row budget")
    seen: set[str] = set()
    encoded_bytes = 0
    for identity in subjects:
        if not isinstance(identity, str) or not identity:
            raise ValueError("Membership requires nonempty string IDs")
        if identity in seen:
            raise ValueError("Membership artifact IDs must be unique")
        seen.add(identity)
        encoded_bytes += len(identity.encode("utf-8"))
        if encoded_bytes > MAX_MEMBERSHIP_ID_BYTES:
            raise ValueError(f"Membership exceeds its {MAX_MEMBERSHIP_ID_BYTES:,}-byte ID byte budget")
    return subjects


def _sample_options(query: Query, registry: dict | None) -> tuple[str, int, int | None, str | None]:
    if not query.sample:
        return "source", 0, None, None
    options = query.sample
    method = options.get("method", "source")
    if set(options) - {"method", "seed", "size", "field_id"} or not isinstance(method, str) or method not in {"source", "random", "stratified"}:
        raise ValueError("Invalid sampling method or options")
    size, seed, field = options.get("size", 100), options.get("seed", 0), options.get("field_id")
    if type(size) is not int or not 1 <= size <= 10_000 or type(seed) is not int:
        raise ValueError("Invalid source sample size or seed")
    if method == "stratified" and (not isinstance(field, str) or registry is not None and field not in registry):
        raise ValueError("Stratified sampling requires a registered field")
    return method, seed, size, field


def _json_path(*parts: str) -> str:
    """A quoted SQL literal containing a JSON path, from validated field parts."""
    path = "$" + "".join("." + json.dumps(part, ensure_ascii=False) for part in parts)
    return "'" + path.replace("'", "''") + "'"


def _stratum_expression(field: str, joined: bool) -> str:
    namespace, dot, key = field.partition(".")
    parts = (namespace, key) if dot else (field,)
    original = f'json_extract(source."record_json", {_json_path(*parts)})'
    if joined and namespace == "prediction":
        # JSON null is distinct from SQL NULL: an explicitly null prediction
        # overrides a source value, just as the regular query engine's merge does.
        original = f'coalesce(json_extract(results."prediction_json", {_json_path(key)}), {original})'
    return f"atlas_membership_stratum({original})"


def _snapshot_mask(snapshot: ParquetSnapshot, query: Query, subjects: Sequence[str], artifacts: Sequence[Artifact]) -> bytes:
    import numpy as np
    import pyarrow as pa

    snapshot._check(query)
    result_table, registry, where, params = snapshot._where(query, artifacts)
    sorts = []
    for sort in query.sort:
        if set(sort) != {"field_id", "direction"} or sort["direction"] not in {"asc", "desc"}:
            raise ValueError("Invalid sort specification")
        column, dtype, _ = snapshot._column(sort["field_id"], registry)
        if dtype in {"array", "object"}:
            raise ValueError(f"Cannot sort structured field: {sort['field_id']}")
        expression = snapshot._category_sort_expression(sort["field_id"], column, snapshot.category_kinds)[0] if dtype == "category" else column
        sorts.append(f'{expression} {sort["direction"].upper()} NULLS LAST')
    if (query.sort or artifacts) and not any(sort.get("field_id") == "id" for sort in query.sort):
        sorts.append('source."id" ASC')
    order = " ORDER BY " + ", ".join(sorts) if sorts else ""
    method, seed, size, sample_field = _sample_options(query, registry)
    mask = bytearray(len(subjects))
    if not subjects:
        return bytes(mask)
    with snapshot._bounded(snapshot.timeout_seconds) as guard:
        connection = guard.connection
        guard.check()
        connection.register("membership_subjects", pa.table({"id": subjects, "position": pa.array(range(len(subjects)), type=pa.int64())}))
        if artifacts:
            connection.register("result_table", result_table)
        source = 'read_parquet(?) AS source' + (' LEFT JOIN result_table AS results ON source."id" = results."id"' if artifacts else '')
        if method in {"random", "stratified"}:
            def ranks(identities):
                # Portable FNV-1a, vectorized over DuckDB's Arrow input batch.
                encoded = [f"{seed}:{identity}".encode() for identity in identities.to_pylist()]
                if not encoded:
                    return pa.array([], type=pa.uint64())
                lengths = np.array([len(value) for value in encoded])
                width = int(lengths.max())
                octets = np.frombuffer(b"".join(value.ljust(width, b"\0") for value in encoded), dtype=np.uint8).reshape(len(encoded), width)
                values = np.full(len(encoded), 2166136261, dtype=np.uint32)
                for column in range(width):
                    values = np.where(lengths > column, (values ^ octets[:, column]) * np.uint32(16777619), values)
                return pa.array(values.astype(np.uint64))
            connection.create_function("atlas_membership_rank", ranks, ["VARCHAR"], "UBIGINT", type="arrow")
            order = ' ORDER BY atlas_membership_rank(source."id"), source."id"'
        if method == "stratified":
            assert isinstance(sample_field, str)
            def strata(values):
                return pa.array([json.dumps(json.loads(value) if value is not None else None, sort_keys=True,
                                            separators=(",", ":"), ensure_ascii=False) for value in values.to_pylist()], type=pa.string())
            connection.create_function("atlas_membership_stratum", strata, ["VARCHAR"], "VARCHAR", null_handling="special", type="arrow")
            # Extract only the grouping value inside DuckDB. Native record
            # envelopes are never fetched into Python, copied into a sort, or
            # returned to the caller, even for wide complete snapshots.
            key = _stratum_expression(sample_field, bool(artifacts))
            chosen = (f'WITH filtered AS (SELECT source."id", {key} AS stratum FROM {source}{where}), '
                      'ranked AS (SELECT id, stratum, row_number() OVER (PARTITION BY stratum '
                      'ORDER BY atlas_membership_rank(id), id) AS stratum_rank FROM filtered), '
                      'chosen AS (SELECT id FROM ranked ORDER BY stratum_rank, stratum LIMIT ?) ')
            sql = chosen + 'SELECT wanted.position FROM membership_subjects AS wanted JOIN chosen ON wanted.id = chosen.id'
            values = [str(snapshot.parquet), *params, size]
        elif size is not None:
            # Keep the LIMIT on the full population inside a CTE. Joining to
            # wanted subjects before sampling would change the selected sample.
            sql = (f'WITH chosen AS (SELECT source."id" FROM {source}{where}{order} LIMIT ?) '
                   'SELECT wanted.position FROM membership_subjects AS wanted JOIN chosen ON wanted.id = chosen.id')
            values = [str(snapshot.parquet), *params, size]
        else:
            # Without a sample, intersection commutes with filtering: restrict
            # the output to requested subjects while scanning the source once.
            sql = (f'SELECT wanted.position FROM {source} JOIN membership_subjects AS wanted ON source."id" = wanted.id{where}')
            values = [str(snapshot.parquet), *params]
        reader = connection.execute(sql, values)
        guard.check()
        while batch := reader.fetchmany(10_000):
            guard.check()
            for (position,) in batch:
                mask[position] = 1
        guard.check()
    return bytes(mask)
