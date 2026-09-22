import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { sampleCards, scopeLine, stubCommonRoutes, switchView, tableRows } from './helpers'

const SIZE = 10_000
const PAGE = 60
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

test('synthetic 10,000-record grid and table stay virtualized and fetch media only for what is on screen', async ({ page }, testInfo) => {
  let mediaRequests = 0
  const apiPageSizes: number[] = []
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/test-pagination-image/')) mediaRequests++ })
  await page.route('**/test-pagination-image/**', route => route.fulfill({ contentType: 'image/jpeg', body: image }))
  await page.route('**/api/v1/**', route => {
    const url = new URL(route.request().url()), path = url.pathname.replace('/api/v1', '')
    const common = stubCommonRoutes(path, ID)
    if (common !== undefined) return route.fulfill({ json: common })
    let body: unknown
    if (path === '/capabilities') body = { mode: 'workbench', operations: ['catalogue', 'query'] }
    else if (path === '/datasets') body = [dataset]
    else if (path === `/datasets/${ID}`) body = dataset
    else if (path === `/datasets/${ID}/fields`) body = []
    else if (path === '/artifacts') body = []
    else if (path === `/queries/${ID}`) {
      const query = route.request().postDataJSON() as { cursor?: string; limit?: number }
      const start = Number(query.cursor ?? 0), end = Math.min(SIZE, start + (query.limit ?? PAGE))
      apiPageSizes.push(end - start)
      body = { snapshot_id: SNAPSHOT, unit: 'example', population_scope: 'preview', records: records.slice(start, end), returned_count: end - start, matched_count: SIZE, count_status: 'exact', cursor: end < SIZE ? String(end) : null }
    } else throw new Error(`Unexpected test API request: ${path}`)
    return route.fulfill({ json: body })
  })

  await page.goto(`/?mode=workbench#/dataset/${ID}`)
  await expect(scopeLine(page)).toContainText('10,000 matches')

  // Virtualization: the first page holds 60 records but only a screenful exists in the DOM.
  await expect(sampleCards(page).first()).toBeVisible()
  const firstGridCards = await sampleCards(page).count()
  const firstGridImages = await page.locator('.sample-grid img').count()
  expect(firstGridCards).toBeLessThan(PAGE)
  const mediaAfterFirstPage = mediaRequests
  expect(mediaAfterFirstPage).toBeLessThanOrEqual(firstGridCards)

  // Scrolling loads the next page automatically and still does not render everything.
  const scroller = page.locator('.work-scroll')
  for (let step = 0; step < 25 && apiPageSizes.length < 2; step += 1) {
    await scroller.evaluate(element => { element.scrollTop = element.scrollHeight })
    await page.waitForTimeout(150)
  }
  expect(apiPageSizes.length).toBeGreaterThan(1)
  const afterScrollCards = await sampleCards(page).count()
  expect(afterScrollCards).toBeLessThan(PAGE * 2)
  const mediaAfterScroll = mediaRequests

  await switchView(page, 'Table')
  await expect(tableRows(page).first()).toBeVisible()
  const tableRowCount = await tableRows(page).count()
  const tableImages = await page.locator('table.data img').count()
  expect(tableRowCount).toBeLessThan(PAGE * 2)

  const metrics = {
    fixture: 'SYNTHETIC TEST ONLY', population: SIZE, requestedPageSize: PAGE, apiPageSizes,
    firstGridCards, firstGridImages, afterScrollCards, tableRowCount, tableImages,
    mediaRequestsFirstPage: mediaAfterFirstPage, mediaRequestsAfterScroll: mediaAfterScroll, mediaRequestsAfterTable: mediaRequests,
  }
  writeFileSync(testInfo.outputPath('synthetic-pagination-metrics.json'), JSON.stringify(metrics, null, 2))
  console.log(`Synthetic pagination benchmark: ${JSON.stringify(metrics)}`)

  expect(apiPageSizes.every(size => size <= PAGE)).toBe(true)
  // Media is fetched for visible cards only; the table's small thumbnails are
  // likewise bounded by the rendered window rather than the loaded population.
  expect(firstGridImages).toBeLessThanOrEqual(firstGridCards)
  expect(tableImages).toBeLessThanOrEqual(tableRowCount)
  expect(mediaRequests).toBeLessThan(SIZE / 10)
})
