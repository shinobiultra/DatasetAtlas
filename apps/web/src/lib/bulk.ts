import type { Artifact } from '../generated'

/**
 * Array-backed results. A large run stores its per-record numbers as binary arrays beside an ids list
 * rather than as one JSON item per record, so a 200k-point projection is a 2.5 MB buffer, not a 30 MB parse.
 */
export type BulkEntry = { file: string; dtype: string; shape: number[]; bytes: number; sha256: string }
export type Bulk = { dir: string; count: number; arrays: Record<string, BulkEntry>; extras?: Record<string, BulkEntry> }
export type ClusterRow = { cluster: number; size: number; mean_distance_to_centroid?: number; exemplar_ids?: string[] }
export type ClusterSummary = { clusters: ClusterRow[]; noise: number; cluster_count: number; silhouette_sample?: number | null }

export function bulkOf(artifact: Artifact): Bulk | null {
  const bulk = artifact.data?.bulk as Bulk | undefined
  return bulk && typeof bulk === 'object' && bulk.arrays ? bulk : null
}

export function clusterSummary(artifact: Artifact): ClusterSummary | null {
  const summary = artifact.data?.summary as ClusterSummary | undefined
  return summary && Array.isArray(summary.clusters) ? summary : null
}

/** Rows an artifact covers, whichever way it is stored. */
export function resultCount(artifact: Artifact): number {
  return bulkOf(artifact)?.count ?? artifact.ids.length
}

export type Numeric = Float32Array | Float64Array | Int32Array | Uint32Array | Int16Array | Uint16Array | Int8Array | Uint8Array
export type LoadedArray = { shape: number[]; data: Numeric }

const CONSTRUCTORS: Record<string, new (buffer: ArrayBuffer) => Numeric> = {
  float32: Float32Array, float64: Float64Array, int32: Int32Array, uint32: Uint32Array,
  int16: Int16Array, uint16: Uint16Array, int8: Int8Array, uint8: Uint8Array,
}
const MAX_CACHED = 12
const cache = new Map<string, Promise<unknown>>()

/** Artifact IDs are content digests, so a fetched array never goes stale; the cache only bounds memory. */
function memo<T>(key: string, load: () => Promise<T>): Promise<T> {
  const hit = cache.get(key)
  if (hit) return hit as Promise<T>
  const pending = load().catch(failure => { cache.delete(key); throw failure })
  cache.set(key, pending)
  while (cache.size > MAX_CACHED) cache.delete(cache.keys().next().value as string)
  return pending
}

const base = (artifact: Artifact) => `/api/v1/artifacts/${encodeURIComponent(artifact.id)}`

export function loadIds(artifact: Artifact): Promise<string[]> {
  return memo(`${artifact.id}:ids`, async () => {
    const response = await fetch(`${base(artifact)}/ids`, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`Result ids request failed (${response.status})`)
    return response.json() as Promise<string[]>
  })
}

export function loadArray(artifact: Artifact, name: string): Promise<LoadedArray> {
  return memo(`${artifact.id}:${name}`, async () => {
    const response = await fetch(`${base(artifact)}/arrays/${encodeURIComponent(name)}`, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`Result array ${name} request failed (${response.status})`)
    const dtype = response.headers.get('X-Atlas-Dtype') ?? ''
    const shape = (response.headers.get('X-Atlas-Shape') ?? '').split(',').filter(Boolean).map(Number)
    const Constructor = CONSTRUCTORS[dtype]
    if (!Constructor || shape.some(value => !Number.isFinite(value))) throw new Error(`Unsupported result array type ${dtype || 'unknown'}`)
    const buffer = await response.arrayBuffer()
    const data = new Constructor(buffer)
    if (data.length !== shape.reduce((product, value) => product * value, 1)) throw new Error('Result array size disagrees with its shape')
    return { shape, data }
  })
}

export type Projection = { ids: string[]; coords: Float32Array; dims: 2 | 3 }

type LegacyPoint = { id: string; x?: number; y?: number; z?: number; output?: { x?: number; y?: number; z?: number } }

/** Points of a projection artifact: arrays for large runs, the JSON points/items for small ones. */
export async function loadProjection(artifact: Artifact): Promise<Projection> {
  if (bulkOf(artifact)) {
    const [ids, coords] = await Promise.all([loadIds(artifact), loadArray(artifact, 'coords')])
    const dims = coords.shape[1]
    if (dims !== 2 && dims !== 3) throw new Error('Projection must have two or three coordinates')
    return { ids, coords: coords.data as Float32Array, dims }
  }
  const raw = (artifact.data?.points ?? artifact.data?.items ?? []) as LegacyPoint[]
  const points = raw
    .map(item => ({ id: item.id, x: item.x ?? item.output?.x, y: item.y ?? item.output?.y, z: item.z ?? item.output?.z }))
    .filter(item => Number.isFinite(item.x) && Number.isFinite(item.y))
  const dims: 2 | 3 = points.some(point => Number.isFinite(point.z)) ? 3 : 2
  const coords = new Float32Array(points.length * dims)
  points.forEach((point, index) => {
    coords[index * dims] = point.x as number
    coords[index * dims + 1] = point.y as number
    if (dims === 3) coords[index * dims + 2] = (point.z as number) ?? 0
  })
  return { ids: points.map(point => point.id), coords, dims }
}

/** One scalar column of an array-backed result (cluster label, outlier score, probability), with its row ids. */
export async function loadColumn(artifact: Artifact, name: string): Promise<{ ids: string[]; values: Numeric }> {
  const [ids, column] = await Promise.all([loadIds(artifact), loadArray(artifact, name)])
  return { ids, values: column.data }
}

/** Artifacts whose rows can colour a projection: cluster labels and scores over the same snapshot and unit. */
export function colourSources(artifacts: Artifact[], projection: Artifact): Array<{ artifact: Artifact; column: string; categorical: boolean }> {
  const sources: Array<{ artifact: Artifact; column: string; categorical: boolean }> = []
  for (const artifact of artifacts) {
    if (artifact.id === projection.id || artifact.unit !== projection.unit || !artifact.snapshot_ids.some(snapshot => projection.snapshot_ids.includes(snapshot))) continue
    const bulk = bulkOf(artifact)
    if (!bulk) continue
    if (bulk.arrays.cluster) sources.push({ artifact, column: 'cluster', categorical: true })
    if (bulk.arrays.outlier_score) sources.push({ artifact, column: 'outlier_score', categorical: false })
    if (bulk.arrays.probability) sources.push({ artifact, column: 'probability', categorical: false })
  }
  return sources
}
