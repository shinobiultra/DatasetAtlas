import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const SIZE = 10_000
const ID = 'synthetic-pagination-10k'
const SNAPSHOT = 'test-only-pagination-snapshot'
const image = readFileSync(fileURLToPath(new URL('./fixtures/orientation-6.jpg', import.meta.url)))

// This 10,000-record population is constructed only by Playwright's mocked API.
const records = Array.from({ length: SIZE }, (_, index) => ({
  id: `synthetic:example:${String(index).padStart(5, '0')}`, dataset_id: ID, release_id: 'test-only', snapshot_id: SNAPSHOT,
  unit: 'example', text: `Synthetic row ${index}`, source: { index },
  assets: [{ id: `synthetic:asset:${index}`, dataset_id: ID, release_id: 'test-only', modality: 'image', representation: 'original', uri: `/test-pagination-image/${index}.jpg`, metadata: {} }],
}))
const dataset = { id: ID, name: 'Synthetic 10,000-record pagination fixture', release: 'test-only', snapshot_id: SNAPSHOT, coverage: { preview_count: SIZE, unit: 'example', complete_data: 'unimplemented' } }

test('synthetic 10,000-record grid/table keep DOM and media requests bounded by page size', async ({ page }, testInfo) => {
  let mediaRequests = 0
  const apiPageSizes: number[] = []
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/test-pagination-image/')) mediaRequests++ })
  await page.route('**/test-pagination-image/**', route => route.fulfill({ contentType: 'image/jpeg', body: image }))
  await page.route('**/api/v1/**', route => {
    const url = new URL(route.request().url()), path = url.pathname.replace('/api/v1', '')
    let body: unknown
    if (path === '/capabilities') body = { mode: 'workbench', operations: ['catalogue', 'query'] }
    else if (path === '/datasets') body = [dataset]
    else if (path === `/datasets/${ID}`) body = dataset
    else if (path === `/datasets/${ID}/fields`) body = []
    else if (path === '/artifacts') body = []
    else if (path === `/queries/${ID}`) {
      const query = route.request().postDataJSON() as { cursor?: string; limit?: number }
      const start = Number(query.cursor ?? 0), end = Math.min(SIZE, start + (query.limit ?? 48))
      apiPageSizes.push(end - start)
      body = { snapshot_id: SNAPSHOT, unit: 'example', population_scope: 'preview', records: records.slice(start, end), returned_count: end - start, matched_count: SIZE, count_status: 'exact', cursor: end < SIZE ? String(end) : null }
    } else throw new Error(`Unexpected test API request: ${path}`)
    return route.fulfill({ json: body })
  })

  await page.goto(`/?mode=workbench#/dataset/${ID}`)
  await expect(page.locator('.scope-line')).toContainText('10000 matches')
  await expect(page.locator('.record-card')).toHaveCount(48)
  const firstGrid = await page.locator('.record-card').count()
  const firstImages = await page.locator('.record-grid img').count()
  const mediaAfterFirstPage = mediaRequests

  await page.getByRole('button', { name: 'Next page' }).click()
  await expect(page.locator('.record-card')).toHaveCount(48)
  await expect(page.locator('.record-card').first()).toContainText('Synthetic row 48')
  const secondGrid = await page.locator('.record-card').count()
  await expect.poll(() => mediaRequests).toBe(96)
  const mediaAfterSecondPage = mediaRequests

  await page.getByRole('button', { name: 'Table', exact: true }).click()
  await expect(page.locator('.table-scroll tbody tr')).toHaveCount(48)
  const tableRows = await page.locator('.table-scroll tbody tr').count()
  const tableImages = await page.locator('.table-scroll img').count()
  const mediaAfterTable = mediaRequests
  await page.addInitScript(() => localStorage.setItem('atlas.view', 'table'))
  mediaRequests = 0
  await page.goto(`/?mode=workbench#/dataset/${ID}`)
  await expect(page.locator('.table-scroll tbody tr')).toHaveCount(48)
  await page.waitForLoadState('networkidle')
  const directTableMediaRequests = mediaRequests
  const metrics = { fixture: 'SYNTHETIC TEST ONLY', population: SIZE, apiPageSizes, firstGridCards: firstGrid, firstGridImages: firstImages, secondGridCards: secondGrid, tableRows, tableImages, mediaRequestsFirstPage: mediaAfterFirstPage, mediaRequestsAfterSecondPage: mediaAfterSecondPage, mediaRequestsAfterTable: mediaAfterTable, directTableMediaRequests }
  writeFileSync(testInfo.outputPath('synthetic-pagination-metrics.json'), JSON.stringify(metrics, null, 2))
  console.log(`Synthetic pagination benchmark: ${JSON.stringify(metrics)}`)
  expect(apiPageSizes.every(size => size <= 48)).toBe(true)
  expect(firstImages).toBeLessThanOrEqual(48)
  expect(mediaAfterFirstPage).toBeLessThanOrEqual(48)
  expect(mediaAfterSecondPage).toBeLessThanOrEqual(96)
  expect(tableImages).toBe(0)
  expect(mediaAfterTable).toBe(mediaAfterSecondPage)
  expect(directTableMediaRequests).toBe(0)
})
