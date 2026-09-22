import { describe, expect, it } from 'vitest'
import type { Pack, Query } from './generated'
import fixture from './test-fixtures/query-parity.json'
import { aggregatePack, fieldValue, fnv1a, queryPack } from './query'

const pack = fixture.pack as Pack

describe('static query parity with canonical Python fixtures', () => {
  for (const [name, testCase] of Object.entries(fixture.cases)) {
    it(name, () => {
      const expected = testCase as { query: Query; ids: string[]; matched_count: number }
      const result = queryPack(pack, expected.query)
      expect(result.records.map(record => record.id)).toEqual(expected.ids)
      expect(result.matched_count).toBe(expected.matched_count)
      expect(result.population_scope).toBe('preview')
    })
  }

  it('paginates without changing IDs or scope', () => {
    const query: Query = { snapshot_id: 'synthetic-v1', limit: 3 }
    const first = queryPack(pack, query)
    const second = queryPack(pack, { ...query, cursor: first.cursor })
    expect([...first.records, ...second.records].map(record => record.id)).toEqual(pack.records.map(record => record.id))
    expect(second.cursor).toBeNull()
    expect(() => queryPack(pack, { ...query, search: 'blue', cursor: first.cursor })).toThrow(/cursor/)
  })

  it('preserves dotted source keys and distinct asset identity', () => {
    expect(fieldValue(pack.records[0], 'source.meta.key')).toBe('North')
    const assets = queryPack(pack, { snapshot_id: 'synthetic-v1', unit: 'asset' })
    expect(assets.records).toHaveLength(5)
    expect(assets.records[0].source).toEqual({ asset_group: 'A' })
    expect(assets.records[0].question).toBeUndefined()
  })

  it('rejects unsupported operations, stale snapshots, and malformed filters', () => {
    expect(() => queryPack(pack, { snapshot_id: 'changed' })).toThrow(/snapshot/i)
    expect(() => queryPack(pack, { snapshot_id: 'synthetic-v1', filter: { field_id: 'source.absent', op: 'eq', value: 1 } })).toThrow(/Unknown field/)
    expect(() => queryPack(pack, { snapshot_id: 'synthetic-v1', filter: { and: [] } })).toThrow(/operands/)
    expect(() => queryPack(pack, { snapshot_id: 'synthetic-v1', unit: 'conversation' })).toThrow(/unit/)
  })

  it('counts boolean nodes toward the 64-node AST limit before short-circuiting', () => {
    const leaf = { field_id: 'source.group', op: 'eq', value: 'A' }
    const allowed = { or: Array.from({ length: 63 }, () => leaf) }
    const rejected = { or: Array.from({ length: 64 }, () => leaf) }
    expect(queryPack(pack, { snapshot_id: 'synthetic-v1', filter: allowed }).matched_count).toBe(3)
    expect(() => queryPack(pack, { snapshot_id: 'synthetic-v1', filter: rejected })).toThrow(/64 nodes/)
    expect(() => queryPack(pack, { snapshot_id: 'synthetic-v1', filter: { or: [leaf, { field_id: 'source.absent', op: 'eq', value: 1 }] } })).toThrow(/Unknown field/)
  })

  it('uses portable UTF-8 FNV-1a ordering', () => {
    expect(fnv1a('42:α-1')).toBe(2855757388)
  })
})

describe('aggregate parity with canonical Python fixtures', () => {
  for (const [name, testCase] of Object.entries(fixture.aggregates)) {
    it(name, () => {
      const expected = testCase as { query: Query; field_ids: string[]; expected: Record<string, unknown> }
      const actual = aggregatePack(pack, expected.query, expected.field_ids)
      expect(actual.denominator).toEqual(expected.expected.denominator)
      expect(actual.population_scope).toEqual(expected.expected.population_scope)
      expect(actual.sampling_applied).toEqual(expected.expected.sampling_applied)
      expect(actual.warnings).toEqual(expected.expected.warnings)
      expect(JSON.parse(JSON.stringify(actual.results))).toEqual(expected.expected.results)
    })
  }

  it('rejects an unregistered aggregation field rather than counting nothing', () => {
    expect(() => aggregatePack(pack, { snapshot_id: 'synthetic-v1' }, ['source.absent'])).toThrow(/Unknown aggregation field/)
  })

  it('never applies the browsing sample to a population count', () => {
    const sampled = aggregatePack(pack, { snapshot_id: 'synthetic-v1', sample: { method: 'random', size: 2, seed: 1 } }, ['source.group'])
    const plain = aggregatePack(pack, { snapshot_id: 'synthetic-v1' }, ['source.group'])
    expect(sampled.denominator).toBe(plain.denominator)
    expect(sampled.warnings.some(warning => warning.includes('Sampling in the browsing query was not applied'))).toBe(true)
  })
})
