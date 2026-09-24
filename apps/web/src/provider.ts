import type { Artifact, Capabilities, Dataset, FieldDescriptor, Pack, Query, QueryResult, Record as AtlasRecord, Run, Selection } from './generated'
import { aggregatePack, assetRecords, packFields, queryPack } from './query'

export type ProcessorDescriptor = { id: string; name?: string; description?: string; available?: boolean; reason?: string; input_units?: string[]; configured_recipe?: boolean; requires_local_model?: boolean; config_schema?: Record<string, unknown> }
export type CompleteScope = { snapshot_id: string; unit: 'asset' | 'example' | 'entity' | 'conversation'; population_scope: 'complete'; record_count: number; count_status: 'exact' | 'estimated' | 'unknown'; fields: FieldDescriptor[] }

/** One catalogue card's real preview tiles. Never synthesized. */
export type ThumbTile = { kind: 'image'; uri: string } | { kind: 'text'; text: string }
export type ThumbEntry = { modality: string | null; tiles: ThumbTile[] }
export type Thumbnails = Record<string, ThumbEntry>

export type AggregateResult =
  | { field_id: string; kind: 'categorical'; denominator: number; missing: number; counts: Array<{ value: string; count: number }>; truncated: boolean }
  | { field_id: string; kind: 'numeric'; denominator: number; missing: number; min: number | null; max: number | null; mean: number | null; present: number }
  | { field_id: string; kind: 'unsupported'; reason: string }
export type AggregateResponse = {
  snapshot_id: string; unit: string; population_scope: string; denominator: number
  count_status: string; results: AggregateResult[]; sampling_applied: boolean; warnings: string[]
}

export interface DataProvider {
  readonly mode: 'static' | 'workbench'
  capabilities(): Promise<Capabilities>
  datasets(): Promise<Dataset[]>
  dataset(id: string): Promise<Dataset>
  fields(id: string, scope?: 'preview' | 'complete'): Promise<FieldDescriptor[]>
  completeInfo(id: string): Promise<CompleteScope>
  pack(id: string): Promise<Pack>
  query(id: string, query: Query): Promise<QueryResult>
  selections(): Promise<Selection[]>
  saveSelection(selection: Selection): Promise<Selection>
  importSelection(payload: unknown): Promise<Selection>
  records(ids: string[]): Promise<AtlasRecord[]>
  exportSelection(selection: Selection): Promise<void>
  artifacts(id?: string): Promise<Artifact[]>
  processors(): Promise<ProcessorDescriptor[]>
  runs(): Promise<Run[]>
  estimateRun(selectionId: string, processorId: string, config: Record<string, unknown>): Promise<Record<string, unknown>>
  startRun(selectionId: string, processorId: string, config: Record<string, unknown>, estimateDigest: string): Promise<Run>
  cancelRun(id: string): Promise<Run>
  providers(): Promise<unknown[]>
  addProvider(body: Record<string, unknown>): Promise<unknown>
  probeProvider(id: string): Promise<unknown>
  previewContext(body: Record<string, unknown>): Promise<Record<string, unknown>>
  converse(body: Record<string, unknown>): Promise<Record<string, unknown>>
  conversations(): Promise<Record<string, unknown>[]>
  conversation(id: string): Promise<Record<string, unknown>>
  similarity(datasetId: string, body: Record<string, unknown>): Promise<Record<string, unknown>>
  thumbnails(): Promise<Thumbnails>
  aggregate(datasetId: string, query: Query, fieldIds: string[], top?: number): Promise<AggregateResponse>
}

function checkMajor(data: { schema_version?: string }, label: string): void {
  if ((data.schema_version ?? '1.0').split('.')[0] !== '1') throw new Error(`${label} uses schema ${data.schema_version}. Open it with a compatible Dataset Atlas reader.`)
}

export function publicUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  const base = new URL(import.meta.env.BASE_URL, window.location.href)
  return new URL(path.replace(/^\//, ''), base).href
}

async function responseJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json() as { detail?: unknown }
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* HTTP status remains the error. */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

function downloadJson(name: string, value: unknown): void {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const storageKey = 'atlas.selections.v1'
function storedSelections(): Selection[] {
  try { return JSON.parse(localStorage.getItem(storageKey) ?? '[]') as Selection[] } catch { return [] }
}

export class StaticDataProvider implements DataProvider {
  readonly mode = 'static'
  private catalogue?: Dataset[]
  private packs = new Map<string, Pack>()
  /** In-flight requests are shared so a screen opening several panels fetches once. */
  private pending = new Map<string, Promise<Pack>>()
  private thumbs?: Promise<Thumbnails>

  async capabilities(): Promise<Capabilities> { return { mode: 'static', operations: ['catalogue', 'query', 'selection', 'export', 'artifacts'], api_version: '1' } }
  async datasets(): Promise<Dataset[]> {
    if (!this.catalogue) {
      const datasets = await responseJson<Dataset[]>(publicUrl('data/catalogue.json'))
      for (const item of datasets) checkMajor(item, `Dataset ${item.id}`)
      this.catalogue = datasets
    }
    return this.catalogue
  }
  async dataset(id: string): Promise<Dataset> {
    const item = (await this.datasets()).find(dataset => dataset.id === id)
    if (!item) throw new Error(`Dataset ${id} is not in this catalogue.`)
    return item
  }
  async pack(id: string): Promise<Pack> {
    const cached = this.packs.get(id)
    if (cached) return cached
    const inflight = this.pending.get(id)
    if (inflight) return inflight
    const request = (async () => {
      const dataset = await this.dataset(id)
      if (!dataset.coverage?.preview_count || dataset.coverage.publication !== 'approved') throw new Error('No approved public preview is available for this dataset.')
      const pack = await responseJson<Pack>(publicUrl(`data/${encodeURIComponent(id)}.json`))
      checkMajor(pack, `Pack ${id}`)
      if (pack.dataset.id !== id) throw new Error('The published pack has the wrong dataset ID.')
      for (const record of pack.records) checkMajor(record, `Record ${record.id}`)
      this.packs.set(id, pack)
      return pack
    })()
    this.pending.set(id, request)
    try { return await request } finally { this.pending.delete(id) }
  }
  async thumbnails(): Promise<Thumbnails> {
    this.thumbs ??= (async () => {
      try {
        const document = await responseJson<{ schema_version?: string; datasets?: Thumbnails }>(publicUrl('data/thumbnails.json'))
        checkMajor(document, 'Catalogue thumbnails')
        const entries = document.datasets ?? {}
        // Published tiles are relative to the site base, like every other published asset.
        return Object.fromEntries(Object.entries(entries).map(([id, entry]) => [id, {
          modality: entry.modality,
          tiles: entry.tiles.map(tile => tile.kind === 'image' ? { kind: 'image' as const, uri: publicUrl(tile.uri) } : tile),
        }]))
      } catch { return {} }
    })()
    return this.thumbs
  }
  async aggregate(id: string, query: Query, fieldIds: string[], top = 24): Promise<AggregateResponse> {
    return aggregatePack(await this.pack(id), query, fieldIds, top) as AggregateResponse
  }
  async fields(id: string): Promise<FieldDescriptor[]> { return packFields(await this.pack(id)) }
  async completeInfo(): Promise<CompleteScope> { throw new Error('Complete-data queries require the local workbench.') }
  async query(id: string, query: Query): Promise<QueryResult> { return queryPack(await this.pack(id), query) }
  async selections(): Promise<Selection[]> { return storedSelections() }
  async saveSelection(selection: Selection): Promise<Selection> {
    const saved = { ...selection, id: selection.id || crypto.randomUUID() }
    const existing = storedSelections()
    localStorage.setItem(storageKey, JSON.stringify([...existing.filter(item => item.id !== saved.id), saved]))
    return saved
  }
  async importSelection(): Promise<Selection> { throw new Error('Selection exchange imports require the local workbench.') }
  async records(ids: string[]): Promise<AtlasRecord[]> {
    const datasets = await this.datasets()
    const rows = new Map<string, AtlasRecord>()
    for (const dataset of datasets.filter(item => item.coverage?.publication === 'approved' && (item.coverage.preview_count ?? 0) > 0)) {
      const pack = await this.pack(dataset.id)
      for (const record of [...pack.records, ...assetRecords(pack)]) if (ids.includes(record.id)) rows.set(record.id, record)
    }
    if (ids.some(id => !rows.has(id))) throw new Error('One or more saved IDs are no longer in published packs.')
    return ids.map(id => rows.get(id)!)
  }
  async exportSelection(selection: Selection): Promise<void> {
    const records = await this.records(selection.ids)
    downloadJson(`atlas-selection-${selection.id}.json`, { schema_version: '1.0', selection, records, notice: 'Records come from approved public preview packs. Media remain references to published assets.' })
  }
  async artifacts(id?: string): Promise<Artifact[]> { return id ? (await this.pack(id)).artifacts ?? [] : [] }
  async processors(): Promise<ProcessorDescriptor[]> { return [] }
  async runs(): Promise<Run[]> { return [] }
  async estimateRun(): Promise<Record<string, unknown>> { throw new Error('Computation requires the local workbench.') }
  async startRun(): Promise<Run> { throw new Error('Computation requires the local workbench.') }
  async cancelRun(): Promise<Run> { throw new Error('Computation requires the local workbench.') }
  async providers(): Promise<unknown[]> { return [] }
  async addProvider(): Promise<unknown> { throw new Error('Provider configuration requires the local workbench.') }
  async probeProvider(): Promise<unknown> { throw new Error('Provider probes require the local workbench.') }
  async previewContext(): Promise<Record<string, unknown>> { throw new Error('Model conversations require the local workbench.') }
  async converse(): Promise<Record<string, unknown>> { throw new Error('Model conversations require the local workbench.') }
  async conversations(): Promise<Record<string, unknown>[]> { return [] }
  async conversation(): Promise<Record<string, unknown>> { throw new Error('Model conversations require the local workbench.') }
  async similarity(): Promise<Record<string, unknown>> { throw new Error('Similarity search requires the local workbench.') }
}

const api = '/api/v1'
function get<T>(path: string): Promise<T> { return responseJson<T>(`${api}${path}`) }
function post<T>(path: string, body?: unknown): Promise<T> {
  return responseJson<T>(`${api}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' }, body: JSON.stringify(body ?? {}) })
}

export class WorkbenchDataProvider implements DataProvider {
  readonly mode = 'workbench'
  capabilities(): Promise<Capabilities> { return get('/capabilities') }
  datasets(): Promise<Dataset[]> { return get('/datasets') }
  dataset(id: string): Promise<Dataset> { return get(`/datasets/${encodeURIComponent(id)}`) }
  async fields(id: string, scope: 'preview' | 'complete' = 'preview'): Promise<FieldDescriptor[]> {
    if (scope === 'complete') return (await this.completeInfo(id)).fields
    const path = `/datasets/${encodeURIComponent(id)}/fields`
    const [examples, assets] = await Promise.all([get<FieldDescriptor[]>(path), get<FieldDescriptor[]>(`${path}?unit=asset`)])
    return [...examples, ...assets]
  }
  completeInfo(id: string): Promise<CompleteScope> { return get(`/datasets/${encodeURIComponent(id)}/complete`) }
  pack(id: string): Promise<Pack> { return get(`/datasets/${encodeURIComponent(id)}/pack`) }
  query(id: string, query: Query): Promise<QueryResult> { return post(`/queries/${encodeURIComponent(id)}`, query) }
  selections(): Promise<Selection[]> { return get('/selections') }
  saveSelection(selection: Selection): Promise<Selection> { return post('/selections', selection) }
  importSelection(payload: unknown): Promise<Selection> { return post('/selections/import', payload) }
  records(ids: string[]): Promise<AtlasRecord[]> { return post('/records', { ids }) }
  async exportSelection(selection: Selection): Promise<void> {
    const result = await get<unknown>(`/selections/${encodeURIComponent(selection.id)}/export`)
    downloadJson(`atlas-selection-${selection.id}.json`, result)
  }
  /** Browsing never renders embedding vectors; the browse view omits them and stays scoped to one dataset's snapshots. */
  artifacts(id?: string): Promise<Artifact[]> { return get(`/artifacts?view=browse${id ? `&dataset_id=${encodeURIComponent(id)}` : ''}`) }
  processors(): Promise<ProcessorDescriptor[]> { return get('/processors') }
  runs(): Promise<Run[]> { return get('/runs') }
  estimateRun(selectionId: string, processorId: string, config: Record<string, unknown>): Promise<Record<string, unknown>> { return post('/runs/estimate', { selection_id: selectionId, processor_id: processorId, config }) }
  startRun(selectionId: string, processorId: string, config: Record<string, unknown>, estimateDigest: string): Promise<Run> { return post('/runs', { selection_id: selectionId, processor_id: processorId, config, estimate_digest: estimateDigest }) }
  cancelRun(id: string): Promise<Run> { return post(`/runs/${encodeURIComponent(id)}/cancel`) }
  providers(): Promise<unknown[]> { return get('/providers') }
  addProvider(body: Record<string, unknown>): Promise<unknown> { return post('/providers', body) }
  probeProvider(id: string): Promise<unknown> { return post(`/providers/${encodeURIComponent(id)}/probe`) }
  previewContext(body: Record<string, unknown>): Promise<Record<string, unknown>> { return post('/conversations/context', body) }
  converse(body: Record<string, unknown>): Promise<Record<string, unknown>> { return post('/conversations', body) }
  conversations(): Promise<Record<string, unknown>[]> { return get('/conversations?limit=100') }
  conversation(id: string): Promise<Record<string, unknown>> { return get(`/conversations/${encodeURIComponent(id)}`) }
  similarity(datasetId: string, body: Record<string, unknown>): Promise<Record<string, unknown>> { return post(`/similarity/${encodeURIComponent(datasetId)}`, body) }
  private thumbs?: Promise<Thumbnails>
  thumbnails(): Promise<Thumbnails> {
    this.thumbs ??= get<{ datasets?: Thumbnails }>('/catalogue/thumbnails').then(document => document.datasets ?? {}).catch(() => ({}))
    return this.thumbs
  }
  aggregate(datasetId: string, query: Query, fieldIds: string[], top = 24): Promise<AggregateResponse> {
    return post(`/aggregate/${encodeURIComponent(datasetId)}`, { query, field_ids: fieldIds, top })
  }
}

export const provider: DataProvider = new URLSearchParams(window.location.search).get('mode') === 'workbench' ? new WorkbenchDataProvider() : new StaticDataProvider()

export function recordMedia(record: AtlasRecord): string[] {
  return (record.assets ?? []).filter(asset => asset.uri).map(asset => provider.mode === 'static' ? publicUrl(asset.uri!) : asset.uri!)
}

/** Explicit user-triggered workbench acquisition; never invoked by static browsing or model tools. */
export const preparationApi = {
  list: <T,>(datasetId: string) => get<T>(`/preparation?dataset_id=${encodeURIComponent(datasetId)}`),
  plan: <T,>(id: string, maxDownloadBytes: number, maxOutputBytes: number, sourceMode: 'download' | 'selective' | 'sample' = 'download') => post<T>(`/datasets/${encodeURIComponent(id)}/preparation/plan`, { max_download_bytes: maxDownloadBytes, max_output_bytes: maxOutputBytes, source_mode: sourceMode }),
  start: <T,>(id: string) => post<T>(`/preparation/${encodeURIComponent(id)}/start`),
  status: <T,>(id: string) => get<T>(`/preparation/${encodeURIComponent(id)}`),
  cancel: <T,>(id: string) => post<T>(`/preparation/${encodeURIComponent(id)}/cancel`),
}
