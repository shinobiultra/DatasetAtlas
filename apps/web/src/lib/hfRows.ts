/** Live previews: the first rows of a public Hugging Face dataset, read straight from its dataset-viewer API by the visitor's browser. */
export type LivePreviewSpec = {
  repo: string; config: string; split: string; relation: 'author_release' | 'public_mirror'; media: 'image' | 'audio' | 'video' | 'text'
  rows_total?: number | null; sensitive?: string
}
export type HfFeature = { name: string; kind: string; labels?: string[] }
export type HfMedia = { kind: 'image' | 'audio' | 'video'; src: string }
export type HfRow = { index: number; media: HfMedia[]; fields: Array<{ name: string; text: string }> }
export type HfPage = { rows: HfRow[]; total: number }

const API = 'https://datasets-server.huggingface.co'
const MAX_TEXT = 220

/** Only assets the viewer itself serves are ever put in an `<img>`, `<audio>` or `<video>`: a dataset must not be able to make the page contact other hosts. */
export function isViewerAsset(url: unknown): url is string {
  if (typeof url !== 'string') return false
  try { const parsed = new URL(url); return parsed.protocol === 'https:' && parsed.hostname === 'datasets-server.huggingface.co' } catch { return false }
}

export function rowsUrl(spec: Pick<LivePreviewSpec, 'repo' | 'config' | 'split'>, offset: number, length: number): string {
  const query = new URLSearchParams({ dataset: spec.repo, config: spec.config, split: spec.split, offset: String(offset), length: String(length) })
  return `${API}/rows?${query}`
}

function clip(value: string): string { return value.length > MAX_TEXT ? `${value.slice(0, MAX_TEXT - 1)}…` : value }

function cellText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return clip(value)
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try { return clip(JSON.stringify(value)) } catch { return '' }
}

function mediaOf(kind: 'image' | 'audio' | 'video', cell: unknown): HfMedia[] {
  const cells = Array.isArray(cell) ? cell : [cell]
  return cells.flatMap(item => {
    const src = item && typeof item === 'object' ? (item as { src?: unknown }).src : undefined
    return isViewerAsset(src) ? [{ kind, src }] : []
  })
}

export function normalizeRows(body: { features?: Array<{ name: string; type?: { _type?: string; names?: string[] } }>; rows?: Array<{ row_idx: number; row: Record<string, unknown> }>; num_rows_total?: number }): HfPage {
  const features: HfFeature[] = (body.features ?? []).map(feature => ({ name: feature.name, kind: feature.type?._type ?? 'Value', labels: feature.type?.names }))
  const rows = (body.rows ?? []).map(entry => {
    const media: HfMedia[] = []
    const fields: Array<{ name: string; text: string }> = []
    for (const feature of features) {
      const cell = entry.row[feature.name]
      if (feature.kind === 'Image') media.push(...mediaOf('image', cell))
      else if (feature.kind === 'Audio') media.push(...mediaOf('audio', cell))
      else if (feature.kind === 'Video') media.push(...mediaOf('video', cell))
      else {
        const text = feature.kind === 'ClassLabel' && typeof cell === 'number' ? (feature.labels?.[cell] ?? String(cell)) : cellText(cell)
        if (text !== '') fields.push({ name: feature.name, text })
      }
    }
    return { index: entry.row_idx, media: media.slice(0, 2), fields: fields.slice(0, 6) }
  })
  return { rows, total: body.num_rows_total ?? rows.length }
}

export class LiveBusyError extends Error {}

export async function fetchRows(spec: LivePreviewSpec, offset: number, length: number, signal?: AbortSignal): Promise<HfPage> {
  const response = await fetch(rowsUrl(spec, offset, length), { signal })
  if (response.status === 429 || response.status >= 500) throw new LiveBusyError('Hugging Face is busy right now. Try again in a moment.')
  if (!response.ok) throw new Error(`Hugging Face answered ${response.status}; this dataset's viewer may be unavailable.`)
  return normalizeRows(await response.json())
}
