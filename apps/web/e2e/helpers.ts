import { expect, type Page } from '@playwright/test'

/**
 * Shared browser-test helpers.
 *
 * Specs address the interface the way a user does — accessible names and the
 * stable `data-record-id` / `data-dataset-id` hooks — so a visual change does
 * not silently invalidate an acceptance check.
 */

export const sampleCards = (page: Page) => page.locator('.sample-card')
export const tableRows = (page: Page) => page.locator('table.data tbody tr[data-record-id]')
export const scopeLine = (page: Page) => page.locator('.scopeline')
export const selectionBar = (page: Page) => page.locator('.statusbar.active')

export function inspector(page: Page) {
  return page.getByRole('complementary', { name: 'Sample inspector' })
}

export async function openDataset(page: Page, datasetId: string) {
  await page.locator(`.ds-card[data-dataset-id="${datasetId}"], .ds-row[data-dataset-id="${datasetId}"]`).first().click()
}

/**
 * Bring a record into the DOM before acting on it.
 *
 * The grid and table are virtualized, so a record far down the population is
 * genuinely absent until scrolled to — exactly as it is for a user.
 */
export async function revealRecord(page: Page, recordId: string) {
  const card = page.locator(`[data-record-id="${recordId}"]`)
  const scroller = page.locator('.work-scroll')
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (await card.count()) {
      try {
        // Opening the inspector resizes the virtual grid. A card measured
        // before that layout change may disappear before scrolling finishes.
        await card.first().scrollIntoViewIfNeeded({ timeout: 1000 })
        if (await card.count()) return card.first()
      } catch {
        // Continue the bounded scroll search after the grid settles.
      }
    }
    await scroller.evaluate(element => { element.scrollTop += element.clientHeight * 0.8 })
    await page.waitForTimeout(60)
  }
  throw new Error(`Record ${recordId} never appeared while scrolling the population`)
}

export async function inspectRecord(page: Page, recordId: string) {
  await revealRecord(page, recordId)
  await page.getByRole('button', { name: `Inspect record ${recordId}` }).click()
  return inspector(page)
}

export async function switchView(page: Page, view: 'Grid' | 'Table' | 'Map' | 'Compare') {
  await page.getByRole('group', { name: 'Workspace view' }).getByRole('button', { name: view, exact: true }).click()
}

/** Apply a filter through the rail's explicit field/operation/value form. */
export async function addFieldFilter(page: Page, fieldId: string, value: string, op = 'eq') {
  const rail = page.getByRole('complementary', { name: 'Sample filters' })
  const other = rail.locator('details.facet').filter({ has: page.getByText('Other fields', { exact: true }) })
  if (!(await other.evaluate(element => (element as HTMLDetailsElement).open))) {
    await other.getByText('Other fields', { exact: true }).click()
  }
  await other.getByLabel('Field').selectOption(fieldId)
  await other.getByLabel('Operation').selectOption(op)
  await other.getByLabel('Value').fill(value)
  await other.getByRole('button', { name: 'Add filter' }).click()
}

export async function expectPanel(page: Page, name: string) {
  const panel = page.getByRole('complementary', { name })
  await expect(panel).toBeVisible()
  return panel
}

/**
 * Minimal stub endpoints every screen touches.
 *
 * Returning explicit empties keeps a spec's mock focused on what it is testing
 * while still exercising the real request paths.
 */
export function stubCommonRoutes(path: string, datasetId: string): unknown | undefined {
  if (path === '/catalogue/thumbnails') return { schema_version: '1.0', datasets: {} }
  if (path === '/preparation') return []
  if (path === '/runs' || path === '/selections' || path === '/processors' || path === '/providers') return []
  if (path === `/aggregate/${datasetId}`) {
    return { snapshot_id: '', unit: 'example', population_scope: 'preview', denominator: 0, count_status: 'exact', results: [], sampling_applied: false, warnings: [] }
  }
  return undefined
}

/** Forward only the explicit test API to the already running local workbench. */
export async function pointToLiveWorkbench(page: Page, api: string) {
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), url = new URL(req.url())
    const response = await fetch(`${api}${url.pathname}${url.search}`, {
      method: req.method(), headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' },
      body: ['GET', 'HEAD'].includes(req.method()) ? undefined : req.postData() ?? undefined,
    })
    await route.fulfill({ status: response.status, contentType: response.headers.get('content-type') ?? 'application/json', body: Buffer.from(await response.arrayBuffer()) })
  })
}
