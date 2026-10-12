import { describe, expect, it } from 'vitest'
import { coerceStored } from './storedValue'

const emptyFacets = { modality: [] as string[], task: [] as string[], howto: [] as string[], annotations: false }

describe('coerceStored', () => {
  it('fills in keys that older builds never saved', () => {
    const saved = { modality: ['image'], task: [], annotations: true }
    expect(coerceStored(saved, emptyFacets)).toEqual({ modality: ['image'], task: [], howto: [], annotations: true })
  })

  it('replaces values of the wrong kind with the default', () => {
    expect(coerceStored({ modality: 'image', task: null, howto: {}, annotations: 'yes' }, emptyFacets)).toEqual(emptyFacets)
    expect(coerceStored('x', ['a'])).toEqual(['a'])
    expect(coerceStored({ a: 1 }, [] as string[])).toEqual([])
    expect(coerceStored(null, emptyFacets)).toEqual(emptyFacets)
    expect(coerceStored(1, true)).toBe(true)
  })

  it('keeps well-formed saved values, including entries of an open record', () => {
    expect(coerceStored(['b'], ['a'])).toEqual(['b'])
    expect(coerceStored(false, true)).toBe(false)
    expect(coerceStored(372, 300)).toBe(372)
    expect(coerceStored({ 'ds-1': ['name'] }, {} as Record<string, string[]>)).toEqual({ 'ds-1': ['name'] })
  })
})
