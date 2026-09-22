import { expect, test } from '@playwright/test'
import { cpus, totalmem } from 'node:os'
import { writeFileSync } from 'node:fs'

const SIZE = 10_000
const PAGE = 1_000
const ID = 'synthetic-map-10k'
const SNAPSHOT = 'test-only-snapshot'

// Generated solely inside this browser test. No synthetic rows enter published packs.
const records = Array.from({ length: SIZE }, (_, index) => ({
  schema_version: '1.0', id: `synthetic:example:${String(index).padStart(5, '0')}`,
  dataset_id: ID, release_id: 'test-only', snapshot_id: SNAPSHOT, unit: 'example',
  assets: [], text: `Synthetic point ${index}`, source: { group: index % 2 ? 'B' : 'A' },
}))
const ids = records.map(record => record.id)
const artifact = {
  schema_version: '1.0', id: 'test-only-umap', kind: 'project.umap', run_id: 'test-only',
  snapshot_ids: [SNAPSHOT], unit: 'example', ids,
  provenance: { fixture: 'synthetic Playwright map performance test; not a model projection' },
  data: { points: ids.map((id, index) => ({ id, x: index % 100, y: Math.floor(index / 100) })) },
}
const dataset = {
  schema_version: '1.0', id: ID, name: 'Synthetic 10,000-point test fixture',
  description: 'Browser engineering fixture only; not a published dataset.',
  release: 'test-only', snapshot_id: SNAPSHOT, modalities: ['test'], tasks: ['rendering'],
  coverage: { access: 'test-only', preview_count: SIZE, unit: 'example', publication: 'test-only', complete_data: 'unimplemented' },
  evidence: [
    { kind: 'source_audit_identity', source_identity_status: 'official_source_resolved_not_human_reviewed', note: 'Synthetic evidence rendering check', checked_on: '2026-09-22', url: 'https://example.org/test-only' },
    { kind: 'corpus_mention', paper_id: 'test-paper', page: 3, review_scope: 'agent_paper_text_check', excerpt: 'Synthetic paper mention rendering check' },
  ],
}
const fields = [{ id: 'source.group', name: 'group', namespace: 'source', dtype: 'category', unit: 'example', query_ops: ['eq', 'ne', 'in', 'is_null'] }]

test('synthetic 10,000-point map renders and lasso-selects without a production fixture', async ({ page, browser }, testInfo) => {
  await page.addInitScript(() => {
    const state = { lastDraw: null as null | { renderedPoints: number; drawMs: number }, started: 0, fills: 0 }
    ;(window as any).__atlasCanvas = state
    const clear = CanvasRenderingContext2D.prototype.clearRect
    const fill = CanvasRenderingContext2D.prototype.fill
    CanvasRenderingContext2D.prototype.clearRect = function (...args) {
      if (this.canvas.width === 800 && this.canvas.height === 500) { state.started = performance.now(); state.fills = 0 }
      return clear.apply(this, args)
    }
    CanvasRenderingContext2D.prototype.fill = function (...args) {
      const result = fill.apply(this, args)
      if (this.canvas.width === 800 && this.canvas.height === 500) {
        state.fills++
        if (state.fills === 10_000) state.lastDraw = { renderedPoints: state.fills, drawMs: performance.now() - state.started }
      }
      return result
    }
  })
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.replace('/api/v1', '')
    let body: unknown
    if (path === '/capabilities') body = { mode: 'workbench', operations: ['catalogue', 'query', 'selection', 'artifacts'], api_version: '1' }
    else if (path === '/datasets') body = [dataset]
    else if (path === `/datasets/${ID}`) body = dataset
    else if (path === `/datasets/${ID}/fields`) body = url.searchParams.get('unit') === 'asset' ? [] : fields
    else if (path === '/artifacts') body = [artifact]
    else if (path === `/queries/${ID}`) {
      const query = request.postDataJSON() as { cursor?: string; limit?: number }
      const start = Number(query.cursor ?? 0), end = Math.min(SIZE, start + (query.limit ?? PAGE))
      body = { snapshot_id: SNAPSHOT, unit: 'example', population_scope: 'preview', records: records.slice(start, end), returned_count: end - start, matched_count: SIZE, count_status: 'exact', cursor: end < SIZE ? String(end) : null }
    } else throw new Error(`Unexpected test API request: ${path}`)
    await route.fulfill({ json: body })
  })

  await page.goto(`/?mode=workbench#/dataset/${ID}`)
  await expect(page.getByRole('heading', { name: dataset.name })).toBeVisible()
  await page.getByRole('button', { name: 'About' }).click()
  const evidence = page.getByRole('dialog', { name: 'about drawer' }).locator('.evidence-section')
  await expect(evidence.getByText(/Agent source check/)).toBeVisible()
  await expect(evidence.getByText(/Paper text check/)).toBeVisible()
  await expect(evidence.getByRole('link', { name: 'https://example.org/test-only' })).toHaveAttribute('href', 'https://example.org/test-only')
  await evidence.getByText('Full receipt').first().click()
  await expect(evidence.getByText(/official_source_resolved_not_human_reviewed/)).toBeVisible()
  await page.getByRole('button', { name: 'Close drawer' }).click()
  await page.getByRole('button', { name: 'Map', exact: true }).click()
  const canvas = page.locator('.map-canvas canvas')
  await expect(canvas).toHaveAttribute('aria-label', /Projection with 1000 visible records/)
  for (let pageNumber = 2; pageNumber <= 10; pageNumber++) {
    await page.getByRole('button', { name: 'Load more points' }).click()
    await expect(canvas).toHaveAttribute('aria-label', new RegExp(`Projection with ${pageNumber * PAGE} visible records`))
  }
  await expect(page.locator('.map-wrap')).toContainText('10000 plotted of 10000 loaded records')
  const draw = await page.evaluate(() => (window as any).__atlasCanvas.lastDraw)
  expect(draw?.renderedPoints).toBe(SIZE)

  await page.evaluate(() => {
    const state: Record<string, number> = {}
    ;(window as any).__atlasSelection = state
    document.addEventListener('pointerup', () => { state.pointerUpAt = performance.now() }, { capture: true, once: true })
    const observer = new MutationObserver(() => {
      if (document.querySelector('.selection-bar strong')?.textContent === '10000 selected') {
        state.domAt = performance.now()
        observer.disconnect()
        requestAnimationFrame(() => { state.frameAt = performance.now() })
      }
    })
    observer.observe(document.body, { childList: true, subtree: true, characterData: true })
  })
  await canvas.scrollIntoViewIfNeeded()
  const initialBox = await canvas.boundingBox()
  if (initialBox && initialBox.y < 260) await page.evaluate(delta => document.querySelector('.results')?.scrollBy(0, delta), initialBox.y - 260)
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()
  const coord = (x: number, y: number) => ({ x: box!.x + x * box!.width / 800, y: box!.y + y * box!.height / 500 })
  const start = coord(5, 5)
  expect(await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.tagName, start)).toBe('CANVAS')
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  for (const [x, y] of [[400, 5], [795, 5], [795, 250], [795, 495], [400, 495], [5, 495], [5, 250], [5, 5]]) {
    const point = coord(x, y)
    await page.mouse.move(point.x, point.y)
  }
  await page.mouse.up()
  await expect(page.locator('.selection-bar strong')).toHaveText('10000 selected')
  await page.waitForFunction(() => Boolean((window as any).__atlasSelection.frameAt))
  const timing = await page.evaluate(() => (window as any).__atlasSelection as Record<string, number>)
  const environment = await page.evaluate(() => ({ userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, deviceMemoryGiB: (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? null }))
  const metrics = {
    fixture: 'SYNTHETIC TEST ONLY', pointsInArtifact: SIZE, renderedPoints: draw.renderedPoints,
    canvasCommandDrawMs: draw.drawMs,
    selectionDomLatencyMs: timing.domAt - timing.pointerUpAt,
    selectionNextFrameMs: timing.frameAt - timing.pointerUpAt,
    browserVersion: browser.version(), browser: environment,
    host: { platform: process.platform, cpu: cpus()[0]?.model ?? 'unknown', logicalCpuCount: cpus().length, memoryGiB: Math.round(totalmem() / 2 ** 30) },
  }
  writeFileSync(testInfo.outputPath('synthetic-map-metrics.json'), JSON.stringify(metrics, null, 2))
  console.log(`Synthetic map benchmark: ${JSON.stringify(metrics)}`)
  // Timing covers JS canvas command issue and the next rAF callback, not GPU paint.
  expect(metrics.selectionNextFrameMs).toBeLessThan(15_000)
})
