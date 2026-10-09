import { expect, test } from '@playwright/test'
import { sampleCards, stubCommonRoutes } from './helpers'

test('a local metadata index opens without a preview pack or image request', async ({ page }) => {
  const id = 'synthetic-metadata-index', snapshot = 'synthetic-metadata-snapshot'
  const dataset = { id, name: 'Synthetic metadata index', release: 'Generated fixture', snapshot_id: snapshot,
    coverage: { preview_count: 0, complete_data: 'indexed_metadata_partial_media', unit: 'example' },
    availability: { preview: 'none', complete_data: 'local', upstream_preview_count: 0 } }
  const record = { id: 'synthetic-url-row', dataset_id: id, release_id: dataset.release, snapshot_id: snapshot,
    unit: 'example', assets: [], source: { media_available: false } }
  const fields = [{ id: 'source.media_available', name: 'media available', namespace: 'source', dtype: 'boolean', unit: 'example' }]
  let completeQueries = 0, previewRequests = 0
  await page.route('**/api/v1/**', route => {
    const request = route.request(), path = new URL(request.url()).pathname.replace('/api/v1', '')
    const common = stubCommonRoutes(path, id)
    if (common !== undefined) return route.fulfill({ json: common })
    if (path === '/capabilities') return route.fulfill({ json: { mode: 'workbench', operations: ['catalogue', 'query'] } })
    if (path === '/datasets') return route.fulfill({ json: [dataset] })
    if (path === `/datasets/${id}`) return route.fulfill({ json: dataset })
    if (path === `/datasets/${id}/complete`) return route.fulfill({ json: { snapshot_id: snapshot, unit: 'example', population_scope: 'complete', record_count: 4934, count_status: 'exact', fields } })
    if (path === `/datasets/${id}/fields` || path.endsWith('/pack')) { previewRequests++; return route.fulfill({ status: 404, json: { detail: 'No synthetic preview' } }) }
    if (path === '/artifacts') return route.fulfill({ json: [] })
    if (path === `/queries/${id}`) {
      expect(request.postDataJSON().population_scope).toBe('complete')
      completeQueries++
      return route.fulfill({ json: { snapshot_id: snapshot, unit: 'example', population_scope: 'complete', matched_count: 4934,
        returned_count: 1, count_status: 'exact', records: [record], fields } })
    }
    throw new Error(`Unexpected synthetic metadata request ${path}`)
  })
  await page.goto(`/?mode=workbench#/dataset/${id}`)
  await expect(sampleCards(page).first()).toBeVisible()
  await expect(page.getByText(/Complete index · 4,934 example records/).first()).toBeVisible()
  expect(completeQueries).toBeGreaterThan(0)
  expect(previewRequests).toBe(0)
})
