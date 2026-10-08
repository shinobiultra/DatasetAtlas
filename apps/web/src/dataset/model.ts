import { useCallback, useEffect, useRef, useState } from 'react'
import type { Artifact, Dataset, FieldDescriptor, Query, QueryResult, Record as AtlasRecord } from '../generated'
import { provider, type CompleteScope } from '../provider'
import type { Box, Overlay } from '../ui/MediaView'
import { display, shortId } from '../lib/format'
import { fieldValue } from '../query'

export type Unit = 'asset' | 'example' | 'entity' | 'conversation'
export type View = 'grid' | 'table' | 'map'
export type PopulationScope = 'preview' | 'complete'

/** One applied filter. Chips above the results map one-to-one onto these. */
export type Clause = { key: string; fieldId: string; fieldName: string; op: string; value: unknown; label: string }

export const PAGE_SIZE = 60
export const MAP_PAGE_SIZE = 1000
export const MAP_MAX_POINTS = 10000

export function clauseFilter(clauses: Clause[]): Record<string, unknown> | null {
  if (!clauses.length) return null
  const nodes = clauses.map(clause => ({ field_id: clause.fieldId, op: clause.op, value: clause.value }))
  return nodes.length === 1 ? nodes[0] : { and: nodes }
}

export function describeClause(field: FieldDescriptor, op: string, value: unknown): string {
  const name = field.name || field.id
  if (op === 'is_null') return `${name} ${value ? 'is missing' : 'is present'}`
  if (op === 'in') return `${name} in ${(Array.isArray(value) ? value : []).map(display).join(', ')}`
  const symbol: Record<string, string> = { eq: '=', ne: '≠', gt: '>', gte: '≥', lt: '<', lte: '≤', contains: 'contains' }
  return `${name} ${symbol[op] ?? op} ${display(value)}`
}

export function canBrowse(dataset: Dataset): boolean {
  if (provider.mode === 'static') return dataset.coverage?.publication === 'approved' && (dataset.coverage.preview_count ?? 0) > 0
  return (dataset.coverage?.preview_count ?? 0) > 0 || dataset.availability?.complete_data === 'local' || dataset.coverage?.complete_data === 'supported'
}

export function supportsComplete(dataset: Dataset): boolean {
  return provider.mode === 'workbench' && (dataset.availability?.complete_data === 'local' || ['supported', 'requires_preparation'].includes(dataset.coverage?.complete_data ?? ''))
}

/** Accumulating pager: pages append, so scrolling never resets what is on screen. */
export type Browse = {
  records: AtlasRecord[]
  result: QueryResult | null
  loading: boolean
  loadingMore: boolean
  error: string
  hasMore: boolean
  loadMore: () => void
  reload: () => void
}

export function useBrowse(datasetId: string, query: Query | null, enabled: boolean, maxRecords = Infinity): Browse {
  const [records, setRecords] = useState<AtlasRecord[]>([])
  const [result, setResult] = useState<QueryResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)
  const generation = useRef(0)
  const signature = query ? JSON.stringify(query) : ''

  useEffect(() => {
    if (!enabled || !query) { setRecords([]); setResult(null); return }
    const current = ++generation.current
    setLoading(true); setError('')
    const timer = setTimeout(() => {
      provider.query(datasetId, query)
        .then(page => {
          if (current !== generation.current) return
          setRecords(page.records); setResult(page); setLoading(false)
        })
        .catch(failure => {
          if (current !== generation.current) return
          setError(String(failure instanceof Error ? failure.message : failure)); setRecords([]); setResult(null); setLoading(false)
        })
    }, 150)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, signature, enabled, nonce])

  const loadMore = useCallback(() => {
    if (!query || !result?.cursor || loading || loadingMore) return
    if (records.length >= maxRecords) return
    const current = generation.current
    setLoadingMore(true)
    provider.query(datasetId, { ...query, cursor: result.cursor })
      .then(page => {
        if (current !== generation.current) return
        setRecords(rows => {
          const seen = new Set(rows.map(row => row.id))
          return [...rows, ...page.records.filter(row => !seen.has(row.id))]
        })
        setResult(page); setLoadingMore(false)
      })
      .catch(failure => {
        if (current !== generation.current) return
        setError(String(failure instanceof Error ? failure.message : failure)); setLoadingMore(false)
      })
  }, [datasetId, query, result, loading, loadingMore, records.length, maxRecords])

  return {
    records, result, loading, loadingMore, error,
    hasMore: Boolean(result?.cursor) && records.length < maxRecords,
    loadMore,
    reload: () => setNonce(value => value + 1),
  }
}

/* ---------- Detector artifacts ---------- */

type DetectorAsset = { asset_id: string; status?: string; width?: number; height?: number; detections?: Box[]; file_sha256?: string; error?: string }
type DetectorItem = { id?: string; status?: string; output?: { assets?: DetectorAsset[] } | null; error?: string }

export type RunState = {
  artifact: Artifact
  runLabel: string
  /** Missing computation, a failure and a genuine zero stay three different things. */
  state: 'not_computed' | 'completed' | 'completed_empty' | 'partial' | 'failed' | 'other'
  summary: string
  detail: string
  threshold: unknown
  extractionThreshold?: unknown
  overlays: Overlay[]
}

export function runLabel(artifact: Artifact): string {
  return `${artifact.kind} · ${shortId(artifact.run_id ?? artifact.id, 8)}`
}

export function isEmbeddingArtifact(artifact: Artifact): boolean {
  const provenance = artifact.provenance?.processor_provenance as { kind?: string; registered_embedding_space?: boolean } | undefined
  return artifact.kind.startsWith('embed.') || (artifact.kind === 'import.research' && provenance?.kind === 'vector' && provenance.registered_embedding_space === true)
}

export function detectorStates(artifacts: Artifact[], recordId: string): RunState[] {
  return artifacts.filter(artifact => artifact.kind.startsWith('detect.')).map(artifact => {
    const provenance = artifact.provenance?.processor_provenance as { extraction_threshold?: unknown; display_threshold?: unknown } | undefined
    const threshold = provenance?.display_threshold ?? provenance?.extraction_threshold ?? 'unknown'
    const extractionThreshold = provenance?.extraction_threshold ?? 'unknown'
    const label = runLabel(artifact)
    const item = ((artifact.data?.items ?? []) as DetectorItem[]).find(entry => entry.id === recordId)
    if (!item) return { artifact, runLabel: label, state: 'not_computed', summary: 'Not computed for this record', detail: '', threshold, overlays: [] }
    if (item.status !== 'completed') {
      const detail = item.error ?? (item.output?.assets ?? []).map(asset => asset.error).filter(Boolean).join('; ')
      return { artifact, runLabel: label, state: item.status === 'failed' ? 'failed' : 'other', summary: `${(item.status ?? 'unknown').replaceAll('_', ' ')} result`, detail, threshold, overlays: [] }
    }
    const assets = item.output?.assets ?? []
    const done = assets.filter(asset => asset.status === 'completed' && Array.isArray(asset.detections))
    const originals = new Map(done.map(asset => [asset.file_sha256 ? `sha256:${asset.file_sha256}` : `asset:${asset.asset_id}`, asset]))
    const count = [...originals.values()].reduce((total, asset) => total + (asset.detections?.length ?? 0), 0)
    const overlays: Overlay[] = done.map(asset => ({
      assetId: asset.asset_id, width: asset.width ?? 0, height: asset.height ?? 0,
      boxes: asset.detections ?? [], run: artifact.run_id ?? artifact.id, kind: artifact.kind, threshold, extractionThreshold, visible: true,
    }))
    if (!assets.length) return { artifact, runLabel: label, state: 'other', summary: 'Completed without asset results', detail: '', threshold, overlays }
    if (done.length !== assets.length) {
      return {
        artifact, runLabel: label, state: 'partial',
        summary: `Partial: ${count} detections, ${assets.length - done.length} asset outputs unavailable`,
        detail: assets.map(asset => asset.error).filter(Boolean).join('; '), threshold, overlays,
      }
    }
    return {
      artifact, runLabel: label, state: count ? 'completed' : 'completed_empty',
      summary: count ? `Completed · ${count} detection${count === 1 ? '' : 's'}` : 'Completed · no detections found',
      detail: '', threshold, overlays,
    }
  })
}

export function projectionArtifacts(artifacts: Artifact[], unit: Unit): Artifact[] {
  return artifacts.filter(artifact => artifact.unit === unit && ['projection', 'pca', 'umap', 'tsne'].some(kind => artifact.kind.toLowerCase().includes(kind)))
}

export type ScopeSummary = { label: string; detail: string }

export function scopeSummary(dataset: Dataset, scope: PopulationScope, complete: CompleteScope | null, result: QueryResult | null): ScopeSummary {
  const unit = scope === 'complete' ? complete?.unit ?? 'example' : dataset.coverage?.unit ?? 'example'
  if (scope === 'complete') {
    return {
      label: `Complete index · ${(complete?.record_count ?? 0).toLocaleString()} ${unit} records`,
      detail: `Release ${dataset.release ?? 'unresolved'}. The index describes the acquired population, which may have partial media.`,
    }
  }
  return {
    label: `Preview · ${(dataset.coverage?.preview_count ?? 0).toLocaleString()} ${unit} records`,
    detail: `Release ${dataset.release ?? 'unresolved'}. ${result?.warnings?.join(' ') ?? 'Counts describe the available preview, not the complete release.'}`,
  }
}

/**
 * Fields whose values merely restate the record's own headline.
 *
 * Datasets routinely carry a `source.question` that is byte-identical to the
 * normalized `question`. Showing both is the duplicate presentation column the
 * UI brief asks us to remove by default; the field stays available in the
 * column picker.
 */
export function duplicatesHeadline(field: FieldDescriptor, records: AtlasRecord[]): boolean {
  const sample = records.slice(0, 16)
  if (sample.length < 3) return false
  let compared = 0
  let identical = 0
  for (const record of sample) {
    const value = fieldValue(record, field.id)
    if (typeof value !== 'string' || !value) continue
    compared += 1
    if (value === record.question || value === record.text) identical += 1
  }
  return compared >= 3 && identical / compared >= 0.8
}

export function defaultColumnFields(fields: FieldDescriptor[], records: AtlasRecord[], limit = 4): FieldDescriptor[] {
  return fields
    .filter(field => field.namespace !== 'record')
    .filter(field => field.dtype !== 'array' && field.dtype !== 'object')
    .filter(field => !duplicatesHeadline(field, records))
    .slice(0, limit)
}
