import type { FieldDescriptor, Pack, Query, QueryResult, Record as AtlasRecord } from './generated'

type Filter = { field_id: string; op: string; value?: unknown } | { and: Filter[] } | { or: Filter[] } | { not: Filter }

export function fieldValue(record: AtlasRecord, fieldId: string): unknown {
  if (['id', 'text', 'question', 'unit', 'dataset_id', 'release_id', 'snapshot_id'].includes(fieldId)) return record[fieldId as keyof AtlasRecord]
  const separator = fieldId.indexOf('.')
  if (separator < 0) return undefined
  const namespace = fieldId.slice(0, separator)
  if (!['source', 'prediction', 'human'].includes(namespace)) return undefined
  return record[namespace as 'source' | 'prediction' | 'human']?.[fieldId.slice(separator + 1)]
}

function lexical(a: string, b: string): number {
  const ac = Array.from(a, char => char.codePointAt(0)!), bc = Array.from(b, char => char.codePointAt(0)!)
  for (let i = 0; i < Math.min(ac.length, bc.length); i++) if (ac[i] !== bc[i]) return ac[i] < bc[i] ? -1 : 1
  return ac.length < bc.length ? -1 : ac.length > bc.length ? 1 : 0
}

function same(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (typeof a === 'number' && typeof b === 'number') return a === b
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return false
  return canonical(a) === canonical(b)
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort(lexical).map(key => `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`).join(',')}}`
  return JSON.stringify(value) ?? 'null'
}

function compare(a: unknown, b: unknown): number | null {
  if (typeof a !== typeof b || (typeof a !== 'number' && typeof a !== 'string')) return null
  if (typeof a === 'number' && (Number.isNaN(a) || Number.isNaN(b as number))) return null
  if (typeof a === 'string') return lexical(a, b as string)
  return a < (b as typeof a) ? -1 : a > (b as typeof a) ? 1 : 0
}

function evaluateFilter(record: AtlasRecord, filter: Filter): boolean {
  if ('and' in filter) return filter.and.every(child => evaluateFilter(record, child))
  if ('or' in filter) return filter.or.some(child => evaluateFilter(record, child))
  if ('not' in filter) return !evaluateFilter(record, filter.not)
  const actual = fieldValue(record, filter.field_id)
  if (filter.op === 'is_null') return (actual === null || actual === undefined) === Boolean(filter.value)
  if (actual === null || actual === undefined || filter.value === null || filter.value === undefined) return false
  switch (filter.op) {
    case 'eq': return same(actual, filter.value)
    case 'ne': return !same(actual, filter.value)
    case 'in': return Array.isArray(filter.value) && filter.value.some(item => same(actual, item))
    case 'contains': return typeof actual === 'string' && typeof filter.value === 'string' && actual.toLowerCase().includes(filter.value.toLowerCase())
    case 'gt': return compare(actual, filter.value) === 1
    case 'gte': return [0, 1].includes(compare(actual, filter.value) ?? -2)
    case 'lt': return compare(actual, filter.value) === -1
    case 'lte': return [-1, 0].includes(compare(actual, filter.value) ?? -2)
    default: throw new Error(`Unsupported filter operation: ${filter.op}`)
  }
}

export function matchesFilter(record: AtlasRecord, filter: Filter, fields: FieldDescriptor[]): boolean {
  validateFilter(filter, fields)
  return evaluateFilter(record, filter)
}

export function fnv1a(value: string): number {
  let hash = 0x811c9dc5
  const bytes = new TextEncoder().encode(value)
  for (const byte of bytes) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0
  return hash >>> 0
}

export function assetRecords(pack: Pack): AtlasRecord[] {
  const direct = pack.records.filter(record => record.unit === 'asset')
  if (direct.length) return direct
  const seen = new Set<string>()
  const rows: AtlasRecord[] = []
  for (const record of pack.records) for (const asset of record.assets ?? []) {
    if (seen.has(asset.id)) continue
    seen.add(asset.id)
    rows.push({
      id: asset.id,
      dataset_id: asset.dataset_id,
      release_id: asset.release_id,
      snapshot_id: record.snapshot_id,
      unit: 'asset',
      asset_ids: [asset.id],
      assets: [asset],
      text: asset.text ?? null,
      source: asset.metadata ?? {},
      prediction: {},
      human: {},
      annotations: [],
      relations: [],
    })
  }
  return rows
}

export function packFields(pack: Pack): FieldDescriptor[] {
  const fields = [...pack.fields]
  const names = new Set(fields.map(field => `${field.unit ?? 'example'}:${field.id}`))
  for (const record of assetRecords(pack)) for (const [key, value] of Object.entries(record.source ?? {})) {
    const id = `source.${key}`
    if (names.has(`asset:${id}`)) continue
    names.add(`asset:${id}`)
    fields.push({ id, name: key, namespace: 'source', unit: 'asset', dtype: typeof value === 'number' ? 'number' : typeof value === 'boolean' ? 'boolean' : Array.isArray(value) ? 'array' : value && typeof value === 'object' ? 'object' : 'string', description: 'Original asset metadata', query_ops: ['eq', 'ne', 'in', 'contains', 'gt', 'gte', 'lt', 'lte', 'is_null'] })
  }
  return fields
}

function fingerprint(query: Query): string {
  const { cursor: _cursor, ...withoutCursor } = query
  return fnv1a(JSON.stringify(withoutCursor)).toString(36)
}

function encodeCursor(offset: number, query: Query): string {
  return btoa(JSON.stringify({ offset, fingerprint: fingerprint(query) }))
}

function decodeCursor(cursor: string, query: Query): number {
  try {
    const parsed = JSON.parse(atob(cursor)) as { offset: number; fingerprint: string }
    if (parsed.fingerprint !== fingerprint(query) || !Number.isSafeInteger(parsed.offset) || parsed.offset < 0) throw Error()
    return parsed.offset
  } catch { throw new Error('The query cursor is invalid or belongs to a different query.') }
}

export function queryPack(pack: Pack, query: Query): QueryResult {
  if ((query.population_scope ?? 'preview') !== (pack.population_scope ?? 'preview')) throw new Error('Requested population scope is unavailable in this pack.')
  if (query.snapshot_id !== pack.dataset.snapshot_id) throw new Error('Dataset snapshot changed. Reload this dataset before querying.')
  const limit = query.limit ?? 100
  const sorts = query.sort ?? []
  const unit = query.unit ?? 'example'
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 1000) throw new Error('Query limit must be between 1 and 1,000.')
  const fields = packFields(pack).filter(field => (field.unit ?? 'example') === unit)
  const fieldIds = new Set([...fields.map(field => field.id), 'id', 'text', 'question', 'unit', 'dataset_id', 'release_id', 'snapshot_id'])
  for (const sort of sorts) if (!fieldIds.has(sort.field_id) || !['asc', 'desc'].includes(sort.direction)) throw new Error(`Invalid sort field or direction: ${sort.field_id}`)
  // Validate the whole AST even when the pack has no rows or boolean branches short-circuit.
  if (query.filter) validateFilter(query.filter as Filter, fields)
  let rows = unit === 'asset' ? assetRecords(pack) : pack.records.filter(record => (record.unit ?? 'example') === unit)
  const availableCount = rows.length
  if (!rows.length && pack.records.length) throw new Error('This pack does not support the requested record unit.')
  if ((query.search ?? '').length > 4000) throw new Error('Search exceeds 4,000 characters.')
  if (query.search) {
    const needle = query.search.toLowerCase()
    rows = rows.filter(record => [record.text ?? '', record.question ?? '', JSON.stringify(record.source ?? {})].some(value => value.toLowerCase().includes(needle)))
  }
  if (query.filter) rows = rows.filter(record => evaluateFilter(record, query.filter as Filter))
  const matchedCount = rows.length
  if (sorts.length) rows = [...rows].sort((a, b) => {
    for (const sort of sorts) {
      const av = fieldValue(a, sort.field_id), bv = fieldValue(b, sort.field_id)
      const am = av === null || av === undefined, bm = bv === null || bv === undefined
      if (am !== bm) return am ? 1 : -1
      if (!am && !bm) {
        const result = compare(av, bv) ?? lexical(typeof av === 'object' ? canonical(av) : String(av), typeof bv === 'object' ? canonical(bv) : String(bv))
        if (result) return sort.direction === 'desc' ? -result : result
      }
    }
    return lexical(a.id, b.id)
  })
  const sample = query.sample as { method?: string; seed?: number; size?: number; field_id?: string } | null | undefined
  if (sample) {
    const size = sample.size ?? 100
    if (typeof size !== 'number' || !Number.isSafeInteger(size) || size < 1 || size > 10000) throw new Error('Sample size must be between 1 and 10,000.')
    const seed = sample.seed ?? 0
    if (typeof seed !== 'number' || !Number.isSafeInteger(seed)) throw new Error('Sampling seed must be an integer.')
    if (Object.keys(sample).some(key => !['method', 'size', 'seed', 'field_id'].includes(key))) throw new Error('Unknown sampling option.')
    if (sample.method === 'random') {
      rows = [...rows].sort((a, b) => fnv1a(`${seed}:${a.id}`) - fnv1a(`${seed}:${b.id}`) || lexical(a.id, b.id)).slice(0, size)
    } else if (sample.method === 'stratified') {
      const fieldId = sample.field_id
      if (!fieldId || !fieldIds.has(fieldId)) throw new Error('Choose a registered field for stratified sampling.')
      const groups = new Map<string, AtlasRecord[]>()
      for (const row of rows) {
        const key = canonical(fieldValue(row, fieldId) ?? null)
        groups.set(key, [...(groups.get(key) ?? []), row])
      }
      for (const group of groups.values()) group.sort((a, b) => fnv1a(`${seed}:${a.id}`) - fnv1a(`${seed}:${b.id}`) || lexical(a.id, b.id))
      const keys = [...groups.keys()].sort(lexical)
      const sampled: AtlasRecord[] = []
      while (sampled.length < size && keys.some(key => groups.get(key)!.length)) for (const key of keys) {
        const row = groups.get(key)!.shift()
        if (row && sampled.length < size) sampled.push(row)
      }
      rows = sampled
    } else if ((sample.method ?? 'source') === 'source') rows = rows.slice(0, size)
    else throw new Error(`Unsupported sampling method: ${sample.method}`)
  }
  const offset = query.cursor ? decodeCursor(query.cursor, query) : 0
  const page = rows.slice(offset, offset + limit)
  return {
    snapshot_id: query.snapshot_id,
    unit,
    population_scope: pack.population_scope ?? 'preview',
    records: page,
    returned_count: page.length,
    matched_count: matchedCount,
    count_status: 'exact',
    coverage: { available_count: availableCount, sampled_count: rows.length, sampling: query.sample ?? null },
    ordering: sorts,
    cursor: offset + page.length < rows.length ? encodeCursor(offset + page.length, query) : null,
    warnings: [...((pack.population_scope ?? 'preview') === 'preview' ? ['Counts describe the available preview, not the complete release.'] : []), ...(sample?.method === 'stratified' ? ['Stratified samples do not estimate population prevalence.'] : [])],
  }
}

function validateFilter(filter: Filter, fields: FieldDescriptor[], depth = 0, leaves = { count: 0 }): void {
  if (depth > 8) throw new Error('Filter exceeds the maximum depth of 8.')
  if (++leaves.count > 64) throw new Error('Filter exceeds the maximum of 64 nodes.')
  if (typeof filter !== 'object' || filter === null || Array.isArray(filter)) throw new Error('Filter must be an object.')
  if ('and' in filter) { if (Object.keys(filter).length !== 1 || !Array.isArray(filter.and) || !filter.and.length) throw new Error('Boolean filter needs operands and no extra keys.'); filter.and.forEach(child => validateFilter(child, fields, depth + 1, leaves)); return }
  if ('or' in filter) { if (Object.keys(filter).length !== 1 || !Array.isArray(filter.or) || !filter.or.length) throw new Error('Boolean filter needs operands and no extra keys.'); filter.or.forEach(child => validateFilter(child, fields, depth + 1, leaves)); return }
  if ('not' in filter) { if (Object.keys(filter).length !== 1) throw new Error('Boolean filter has extra keys.'); validateFilter(filter.not, fields, depth + 1, leaves); return }
  if (Object.keys(filter).some(key => !['field_id', 'op', 'value'].includes(key))) throw new Error('Unknown filter key.')
  const field = fields.find(item => item.id === filter.field_id)
  if (!field && !['id', 'text', 'question', 'unit', 'dataset_id', 'release_id', 'snapshot_id'].includes(filter.field_id)) throw new Error(`Unknown field: ${filter.field_id}`)
  if (!['eq', 'ne', 'in', 'contains', 'gt', 'gte', 'lt', 'lte', 'is_null'].includes(filter.op)) throw new Error(`Unsupported filter operation: ${filter.op}`)
  if (filter.op === 'in' && (!Array.isArray(filter.value) || filter.value.length > 1000)) throw new Error('Membership expects at most 1,000 values.')
  if (filter.op === 'is_null' && typeof filter.value !== 'boolean') throw new Error('is_null expects a boolean value.')
  if (filter.op === 'contains' && typeof filter.value !== 'string') throw new Error('contains expects literal text.')
}

export type AggregateItem =
  | { field_id: string; kind: 'categorical'; denominator: number; missing: number; counts: Array<{ value: string; count: number }>; truncated: boolean }
  | { field_id: string; kind: 'numeric'; denominator: number; missing: number; min: number | null; max: number | null; mean: number | null; present: number }
  | { field_id: string; kind: 'unsupported'; reason: string }

/** Mirrors dataset_atlas.queries.aggregate_pack so both providers report the same shape. */
export function aggregatePack(pack: Pack, query: Query, fieldIds: string[], top = 24) {
  if ((query.population_scope ?? 'preview') !== (pack.population_scope ?? 'preview')) throw new Error('Requested population scope is unavailable in this pack.')
  if (query.snapshot_id !== pack.dataset.snapshot_id) throw new Error('Dataset snapshot changed. Reload this dataset before aggregating.')
  if (fieldIds.length > 12) throw new Error('Aggregate at most 12 fields per request.')
  const unit = query.unit ?? 'example'
  const fields = packFields(pack).filter(field => (field.unit ?? 'example') === unit)
  const known = new Set([...fields.map(field => field.id), 'id', 'text', 'question', 'unit', 'dataset_id', 'release_id', 'snapshot_id'])
  const unknown = fieldIds.find(id => !known.has(id))
  if (unknown) throw new Error(`Unknown aggregation field: ${unknown}`)
  if (query.filter) validateFilter(query.filter as Filter, fields)
  let rows = unit === 'asset' ? assetRecords(pack) : pack.records.filter(record => (record.unit ?? 'example') === unit)
  if (query.search) {
    const needle = query.search.toLowerCase()
    rows = rows.filter(record => [record.text ?? '', record.question ?? '', JSON.stringify(record.source ?? {})].some(value => value.toLowerCase().includes(needle)))
  }
  if (query.filter) rows = rows.filter(record => evaluateFilter(record, query.filter as Filter))
  const denominator = rows.length
  const results: AggregateItem[] = fieldIds.map(fieldId => {
    const values = rows.map(record => fieldValue(record, fieldId))
    const present = values.filter(value => value !== null && value !== undefined)
    const missing = values.length - present.length
    if (present.some(value => typeof value === 'object')) return { field_id: fieldId, kind: 'unsupported', reason: 'Structured fields are not aggregated.' }
    const numbers = present.filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
    if (present.length && numbers.length === present.length) {
      return {
        field_id: fieldId, kind: 'numeric', denominator, missing, present: numbers.length,
        min: Math.min(...numbers), max: Math.max(...numbers),
        mean: numbers.reduce((sum, value) => sum + value, 0) / numbers.length,
      }
    }
    const counter = new Map<string, number>()
    for (const value of present) {
      const key = typeof value === 'string' ? value : JSON.stringify(value)
      counter.set(key, (counter.get(key) ?? 0) + 1)
    }
    const ordered = [...counter].sort((a, b) => b[1] - a[1] || lexical(a[0], b[0]))
    return {
      field_id: fieldId, kind: 'categorical', denominator, missing,
      counts: ordered.slice(0, top).map(([value, count]) => ({ value, count })),
      truncated: ordered.length > top,
    }
  })
  const scope = pack.population_scope ?? 'preview'
  return {
    snapshot_id: query.snapshot_id, unit, population_scope: scope, denominator,
    count_status: 'exact', results, sampling_applied: false,
    warnings: [
      ...(query.sample ? ['Sampling in the browsing query was not applied; these counts describe the filtered population.'] : []),
      ...(scope === 'complete' ? [] : [`Counts describe the available ${scope} snapshot, not a complete release.`]),
    ],
  }
}
