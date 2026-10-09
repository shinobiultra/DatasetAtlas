import { describe, expect, it, vi } from 'vitest'
import type { Asset } from '../generated'
vi.mock('../provider', () => ({ provider: { mode: 'workbench' } }))
import { browserRenderRequired, displayUrl } from './display'

describe('native TIFF browsing', () => {
  it('uses a faithful display rendering, never the blurred safe view, for current and earlier native TIFF metadata', () => {
    for (const metadata of [{ browser_render_required: true }, { representation: 'original 16-bit expert TIFF' }]) {
      const asset: Asset = { id: 'fixture', dataset_id: 'fixture', release_id: 'fixture', modality: 'image', uri: 'media/native-original', metadata }
      expect(browserRenderRequired(asset)).toBe(true)
      expect(displayUrl('/api/v1/media/a?asset=b', true)).toBe('/api/v1/media/a?asset=b&representation=display')
      expect(asset.uri).toBe('media/native-original')
    }
  })
  it('preserves original URLs for supported media and never fetches an arbitrary render URL', () => {
    expect(displayUrl('/api/v1/media/a')).toBe('/api/v1/media/a')
    expect(displayUrl('https://untrusted.example/a.tif', true)).toMatch(/^data:image\/svg\+xml/)
  })
})
