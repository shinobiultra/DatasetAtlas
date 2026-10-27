import { expect, it } from 'vitest'
import type { Dataset } from '../generated'
import { coverageLine, coverageState } from './format'

it('labels metadata-only native previews without claiming available media', () => {
  const dataset: Dataset = { id: 'fixture', name: 'Fixture', coverage: { preview: 'metadata_only', preview_count: 100,
    total_count: 4000, complete_data: 'indexed_metadata_partial_media' } }
  expect(coverageState(dataset, 'workbench')).toBe('metadata')
  expect(coverageLine(dataset, 'workbench')).toEqual({ text: '100 native metadata records · media not acquired', tone: 'warn' })
  expect(coverageLine(dataset, 'static').text).toContain('prepared in the local workbench')
})
