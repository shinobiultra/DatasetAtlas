import { describe, expect, it } from 'vitest'
import type { Artifact, Query, Record as AtlasRecord } from '../generated'
import { GROUNDING_INSTRUCTION, groundedPrompt, hitRows, retrievalQuery, snippet, spaceLabel } from './retrieval'

const record = (id: string, extra: Partial<AtlasRecord> = {}) => ({ id, ...extra }) as AtlasRecord

describe('retrieval helpers', () => {
  it('ties the question to the attached records', () => {
    expect(groundedPrompt('  What colour is the bus?  ')).toBe(`What colour is the bus?\n\n${GROUNDING_INSTRUCTION}`)
    expect(GROUNDING_INSTRUCTION).toContain('[record:<id>]')
  })

  it('searches the whole filtered population, not one sampled page of it', () => {
    const query: Query = { snapshot_id: 's', population_scope: 'complete', unit: 'example', limit: 60, cursor: 'abc', sample: { method: 'random', size: 5 }, filter: { field_id: 'source.label', op: 'eq', value: 'A' } }
    expect(retrievalQuery(query)).toMatchObject({ sample: null, cursor: null, filter: query.filter, snapshot_id: 's', population_scope: 'complete' })
    expect(query.sample).not.toBeNull()
  })

  it('shows the question when there is one, else the text, shortened on one line', () => {
    expect(snippet(record('a', { question: 'Which  object?', text: 'ignored' }))).toBe('Which object?')
    expect(snippet(record('a', { text: 'x'.repeat(200) }), 20)).toBe(`${'x'.repeat(19)}…`)
    expect(snippet(undefined)).toBe('')
  })

  it('keeps the search ranking and a row for a record that could not be fetched', () => {
    const hits = hitRows([{ id: 'b', distance: 0.1 }, { id: 'gone', distance: 0.2 }, { id: 'a', distance: 0.3 }], [record('a', { text: 'alpha' }), record('b', { text: 'beta' })])
    expect(hits.map(hit => hit.id)).toEqual(['b', 'gone', 'a'])
    expect(hits.map(hit => hit.snippet)).toEqual(['beta', '', 'alpha'])
  })

  it('tells embedding spaces apart by model, representation and coverage', () => {
    const artifact = (extra: Partial<Artifact>) => ({ id: 'abcdef123456', kind: 'embed.api', snapshot_ids: ['s'], unit: 'example', ids: [], ...extra }) as Artifact
    expect(spaceLabel(artifact({
      provenance: { processor_provenance: { model_id: 'qwen3-embedding:0.6b', recipe: { representation: 'question' } } }, data: { bulk: { count: 92672 } },
    }))).toBe('embed.api · qwen3-embedding:0.6b · question · 92,672 records · …123456')
    expect(spaceLabel(artifact({ kind: 'embed.minilm', ids: ['a', 'b'] }))).toBe('embed.minilm · 2 records · …123456')
  })
})
