import type { Dataset, FieldDescriptor, Record as AtlasRecord } from '../generated'

/** Present a value for reading. Missing stays visibly missing, never coerced to zero. */
export function display(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : String(Number(value.toFixed(4)))
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function isMissing(value: unknown): boolean {
  return value === null || value === undefined || value === ''
}

export function compact(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(value % 1_000_000 === 0 ? 0 : 1)}M`
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(value % 1_000 === 0 ? 0 : 1)}k`
  return value.toLocaleString()
}

export function titleCase(value: string): string {
  return value.replaceAll('_', ' ').replace(/^\w/, character => character.toUpperCase())
}

export function plural(count: number, word: string, suffix = 's'): string {
  return `${count.toLocaleString()} ${word}${count === 1 ? '' : suffix}`
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const then = Date.parse(iso)
  if (!Number.isFinite(then)) return String(iso)
  const seconds = Math.round((Date.now() - then) / 1000)
  if (Math.abs(seconds) < 60) return 'just now'
  const units: Array<[number, Intl.RelativeTimeFormatUnit]> = [
    [31557600, 'year'], [2629800, 'month'], [604800, 'week'],
    [86400, 'day'], [3600, 'hour'], [60, 'minute'],
  ]
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  for (const [size, unit] of units) {
    if (Math.abs(seconds) >= size) return formatter.format(-Math.round(seconds / size), unit)
  }
  return 'just now'
}

/** An https/http URL from untrusted registry data, or null. */
export function safeUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null
  } catch { return null }
}

export function evidenceText(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

/** The single readable line that identifies a record in lists. */
export function recordHeadline(record: AtlasRecord): string {
  if (record.question) return record.question
  if (record.text) return record.text
  const turn = record.conversation?.[0]
  if (turn) return typeof turn.content === 'string' ? turn.content : JSON.stringify(turn.content)
  const source = Object.entries(record.source ?? {}).find(([, value]) => typeof value === 'string' && value.length > 2)
  if (source) return String(source[1])
  return record.id
}

export function shortId(id: string, length = 10): string {
  return id.length <= length ? id : `…${id.slice(-length)}`
}

/**
 * What this deployment can actually show, in its own words.
 *
 * The registry records what the local workbench prepared. A public build only
 * carries what publication approved, so it must not repeat the workbench's
 * preview claim as if the examples were here.
 */
export type CoverageState = 'full' | 'preview' | 'elsewhere' | 'metadata'

export function coverageState(dataset: Dataset, mode: 'static' | 'workbench'): CoverageState {
  const coverage = dataset.coverage ?? {}
  const previewCount = coverage.preview_count ?? 0
  if (mode === 'static') {
    if (coverage.publication === 'approved' && previewCount > 0) return 'preview'
    return previewCount > 0 ? 'elsewhere' : 'metadata'
  }
  if (previewCount > 0 && coverage.complete_data === 'supported') return 'full'
  if (previewCount > 0) return 'preview'
  return 'metadata'
}

export const COVERAGE_STATE_LABEL: Record<CoverageState, string> = {
  full: 'Full data available locally',
  preview: 'Preview available',
  elsewhere: 'Not published here — prepared in the workbench',
  metadata: 'Metadata only — no adapter yet',
}

export function coverageLine(dataset: Dataset, mode: 'static' | 'workbench'): { text: string; tone: 'ok' | 'warn' | 'default' } {
  const coverage = dataset.coverage ?? {}
  const previewCount = coverage.preview_count ?? 0
  const unit = coverage.unit ?? 'example'
  switch (coverageState(dataset, mode)) {
    case 'full':
      return { text: `${previewCount.toLocaleString()} ${unit} preview · full data available locally`, tone: 'ok' }
    case 'preview': {
      const extra = mode === 'workbench'
        ? (coverage.complete_data === 'requires_preparation' ? ' · full data needs preparation'
          : coverage.complete_data === 'externally_blocked' ? ' · full data externally blocked' : '')
        : ''
      return { text: `${previewCount.toLocaleString()} ${unit} preview${extra}`, tone: 'ok' }
    }
    case 'elsewhere':
      return { text: `Metadata only here · ${previewCount.toLocaleString()} ${unit} preview exists in the local workbench`, tone: 'warn' }
    default:
      return { text: `Metadata only · ${titleCase(coverage.access ?? 'access unknown')}`, tone: 'default' }
  }
}

export function accessTone(access: string | undefined): 'ok' | 'warn' | 'danger' | 'default' {
  if (access === 'public') return 'ok'
  if (access === 'gated' || access === 'request_required' || access === 'author_request_required') return 'warn'
  if (access === 'unavailable') return 'danger'
  return 'default'
}

/** Group a field by where it came from, so no score floats free of its run. */
export function fieldOrigin(field: FieldDescriptor): string {
  if (field.namespace === 'source') return 'Source annotations'
  if (field.namespace === 'human') return 'Human review'
  if (field.namespace === 'record') return 'Record structure'
  if (field.namespace === 'prediction') {
    const provenance = field.provenance as { run_id?: string; artifact_id?: string } | undefined
    const run = provenance?.run_id ?? provenance?.artifact_id
    const kind = field.name.split('·')[0]?.trim()
    return run ? `${kind || 'Computed'} · ${shortId(run, 8)}` : 'Computed results'
  }
  return 'Other fields'
}

export function fieldLeafName(field: FieldDescriptor): string {
  const parts = field.name.split('·')
  return (parts.length > 1 ? parts.slice(1).join('·') : field.name).trim() || field.id
}

/** Human byte sizes with the unit the magnitude deserves. */
export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  if (value < 1000) return `${Math.round(value)} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let scaled = value / 1000
  let index = 0
  while (scaled >= 1000 && index < units.length - 1) { scaled /= 1000; index += 1 }
  return `${scaled >= 100 ? scaled.toFixed(0) : scaled >= 10 ? scaled.toFixed(1) : scaled.toFixed(2)} ${units[index]}`
}
