import { describe, expect, it } from 'vitest'
import { OPTIONS, optionConfig } from './analysisOptions'

describe('analysis option forms', () => {
  it('sends the value the form shows even when it was never touched', () => {
    // The form defaults a projection to 3D while the processor's own default is 2D; the run must follow the screen.
    expect(optionConfig('project.umap', {})).toEqual({ dimensions: 3, neighbors: 15, min_dist: 0.1, metric: 'cosine' })
    expect(optionConfig('project.pca', {})).toEqual({ dimensions: 3 })
  })

  it('lets edits win and turns numeric text into numbers', () => {
    expect(optionConfig('cluster.kmeans', { clusters: '60', metric: 'cosine' })).toEqual({ clusters: 60, n_init: 1, metric: 'cosine' })
    expect(optionConfig('project.umap', { dimensions: '2', min_dist: '0.25' })).toMatchObject({ dimensions: 2, min_dist: 0.25 })
  })

  it('leaves a blank number out so the processor default applies', () => {
    expect(optionConfig('cluster.hdbscan', { min_cluster_size: '' })).toEqual({ metric: 'cosine' })
  })

  it('has nothing to send for analyses without options', () => {
    expect(optionConfig('quality.basic', { anything: 1 })).toEqual({})
  })

  it('offers only bounds the backend accepts', () => {
    for (const options of Object.values(OPTIONS)) for (const option of options) if (option.kind === 'number') {
      expect(option.min).toBeLessThanOrEqual(option.initial)
      expect(option.max).toBeGreaterThanOrEqual(option.initial)
    }
  })
})
