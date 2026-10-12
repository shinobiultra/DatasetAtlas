import { describe, expect, it } from 'vitest'
import type { Artifact } from '../generated'
import { bulkOf, colourSources, loadProjection, resultCount } from './bulk'

const entry = (shape: number[], dtype = 'float32') => ({ file: 'x.npy', dtype, shape, bytes: 1, sha256: 'a' })
const artifact = (id: string, kind: string, data: Artifact['data'], overrides: Partial<Artifact> = {}): Artifact => ({
  id, kind, snapshot_ids: ['s'], unit: 'example', ids: ['a', 'b', 'c'], data, ...overrides,
})

describe('array-backed results', () => {
  it('recognises them and counts rows from the arrays, not the ids list', () => {
    const bulk = artifact('p', 'project.umap', { bulk: { dir: 'arrays/p', count: 2, arrays: { coords: entry([2, 3]) } } })
    expect(bulkOf(bulk)).not.toBeNull()
    expect(resultCount(bulk)).toBe(2)
    expect(bulkOf(artifact('j', 'project.pca', { items: [] }))).toBeNull()
    expect(resultCount(artifact('j', 'project.pca', { items: [] }))).toBe(3)
  })

  it('reads small JSON projections, with or without a third coordinate', async () => {
    const flat = await loadProjection(artifact('f', 'project.pca', { points: [{ id: 'a', x: 1, y: 2 }, { id: 'b', x: 3, y: 4 }, { id: 'c', x: NaN as number, y: 0 }] }))
    expect(flat.dims).toBe(2)
    expect(flat.ids).toEqual(['a', 'b'])
    expect(Array.from(flat.coords)).toEqual([1, 2, 3, 4])
    const solid = await loadProjection(artifact('s', 'project.pca', { items: [{ id: 'a', output: { x: 1, y: 2, z: 3 } }] }))
    expect(solid.dims).toBe(3)
    expect(Array.from(solid.coords)).toEqual([1, 2, 3])
  })

  it('offers cluster labels and scores over the same snapshot as colour sources, and nothing else', () => {
    const projection = artifact('proj', 'project.umap', { bulk: { dir: 'd', count: 3, arrays: { coords: entry([3, 3]) } } })
    const clusters = artifact('km', 'cluster.kmeans', { bulk: { dir: 'd', count: 3, arrays: { cluster: entry([3], 'int32') } } })
    const outliers = artifact('ol', 'outlier.knn', { bulk: { dir: 'd', count: 3, arrays: { outlier_score: entry([3]) } } })
    const otherSnapshot = artifact('x', 'cluster.kmeans', { bulk: { dir: 'd', count: 3, arrays: { cluster: entry([3], 'int32') } } }, { snapshot_ids: ['elsewhere'] })
    const legacy = artifact('lg', 'cluster.kmeans', { items: [] })
    const sources = colourSources([projection, clusters, outliers, otherSnapshot, legacy], projection)
    expect(sources.map(source => `${source.artifact.id}:${source.column}:${source.categorical}`)).toEqual(['km:cluster:true', 'ol:outlier_score:false'])
  })
})
