import { expect, test, type Page } from '@playwright/test'
import { selectionBar, stubCommonRoutes, switchView } from './helpers'

const ID = 'synthetic-map-membership'
const SNAPSHOT = 'synthetic-membership-snapshot'
const rows = Array.from({ length: 4 }, (_, index) => ({
  id: `${ID}:example:${index}`, dataset_id: ID, snapshot_id: SNAPSHOT, unit: 'example',
  text: `Synthetic ${index < 2 ? 'keep' : 'hide'} point ${index}`, assets: [], source: {},
}))
const ids = rows.map(row => row.id)
const coords = Float32Array.from([-1, -1, 0, 1, -1, 0, -1, 1, 0.1, 1, 1, 0.1])

async function lassoAll(page: Page) {
  await page.getByRole('button', { name: 'Lasso', exact: true }).click()
  const stage = page.locator('.map-stage')
  await stage.scrollIntoViewIfNeeded()
  const box = (await stage.boundingBox())!
  const scroller = (await page.locator('.map').boundingBox())!
  const scope = (await page.locator('.scopeline').boundingBox())!
  // Keep the gesture inside the visible map. Coordinates below the viewport
  // trigger browser drag autoscroll and change the map's origin mid-gesture.
  // The filtered fixture's two lower points remain inside this rectangle.
  const left = box.x + 100, right = box.x + box.width - 20
  const top = Math.max(box.y + 5, scroller.y + 5, scope.y + scope.height + 5)
  const bottom = Math.min(box.y + box.height - 5, scroller.y + scroller.height - 8, page.viewportSize()!.height - 8)
  await page.mouse.move(left, top)
  await page.mouse.down()
  for (const [x, y] of [[right, top], [right, bottom], [left, bottom], [left, top]]) {
    await page.mouse.move(x, y, { steps: 5 })
  }
  await page.mouse.up()
}

async function inspectLastProjectionPoint(page: Page) {
  const box = (await page.locator('.map-stage').boundingBox())!
  // Fixed test coordinates normalise to (1, 1, .05); the unchanged home camera
  // is at z=3.4 with a 45-degree vertical field of view.
  const displacement = box.height / (2 * Math.tan(Math.PI / 8) * (3.4 - 0.05))
  await page.mouse.click(box.x + box.width / 2 + displacement, box.y + box.height / 2 - displacement)
}

for (const storage of ['legacy', 'arrays'] as const) {
  test(`${storage} 3D map keeps rendering and selection in the filtered population without refitting`, async ({ page }) => {
    await page.addInitScript(() => {
      const state = { lastIndexedPointCount: -1 }
      ;(window as typeof window & { atlasMapDraw: typeof state }).atlasMapDraw = state
      for (const Constructor of [WebGLRenderingContext, WebGL2RenderingContext]) {
        const draw = Constructor.prototype.drawElements
        Constructor.prototype.drawElements = function (mode, count, type, offset) {
          if (mode === this.POINTS) state.lastIndexedPointCount = count
          return draw.call(this, mode, count, type, offset)
        }
      }
    })
    const projection = {
      id: `synthetic-projection-${storage}`, kind: 'project.pca', unit: 'example', snapshot_ids: [SNAPSHOT], ids,
      provenance: { fit_id: 'synthetic-unchanged-fit' },
      data: storage === 'arrays'
        ? { bulk: { count: 4, dir: 'synthetic', arrays: { coords: { dtype: 'float32', shape: [4, 3], bytes: coords.byteLength, sha256: 'test-only' } } } }
        : { points: rows.map((row, index) => ({ id: row.id, x: coords[index * 3], y: coords[index * 3 + 1], z: coords[index * 3 + 2] })) },
    }
    const clusters = { id: 'synthetic-clusters', kind: 'cluster.kmeans', unit: 'example', snapshot_ids: [SNAPSHOT], ids,
      data: { bulk: { count: 4, dir: 'synthetic', arrays: { cluster: { dtype: 'int32', shape: [4], bytes: 16, sha256: 'test-only' } } }, summary: { clusters: [{ cluster: 0, size: 4 }] } } }
    const dataset = { id: ID, name: 'Synthetic membership fixture', snapshot_id: SNAPSHOT, coverage: { preview_count: 4, unit: 'example' } }
    const original = JSON.stringify(projection)
    let release: (() => void) | undefined
    let requested = false
    const held = new Promise<void>(resolve => { release = resolve })
    let releasePage: (() => void) | undefined
    const lastPage = new Promise<void>(resolve => { releasePage = resolve })
    const recordReads: Array<{ ids: string[]; snapshot_ids?: string[] }> = []
    let fitRequests = 0
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace('/api/v1', '')
      if (path === '/runs' && request.method() === 'POST') { fitRequests += 1; throw new Error('Filtering must not fit a projection') }
      const common = stubCommonRoutes(path, ID)
      if (common !== undefined) return route.fulfill({ json: common })
      if (path === '/capabilities') return route.fulfill({ json: { mode: 'workbench', operations: ['catalogue', 'query', 'selection', 'artifacts'], api_version: '1' } })
      if (path === '/datasets') return route.fulfill({ json: [dataset] })
      if (path === `/datasets/${ID}`) return route.fulfill({ json: dataset })
      if (path === `/datasets/${ID}/fields`) return route.fulfill({ json: [] })
      if (path === '/artifacts') return route.fulfill({ json: [projection, clusters] })
      if (path === `/artifacts/${projection.id}/ids` || path === '/artifacts/synthetic-clusters/ids') return route.fulfill({ json: ids })
      if (path === `/artifacts/${projection.id}/arrays/coords`) return route.fulfill({ body: Buffer.from(coords.buffer), headers: { 'X-Atlas-Dtype': 'float32', 'X-Atlas-Shape': '4,3' } })
      if (path === '/artifacts/synthetic-clusters/arrays/cluster') return route.fulfill({ body: Buffer.from(new Int32Array(4).buffer), headers: { 'X-Atlas-Dtype': 'int32', 'X-Atlas-Shape': '4' } })
      if (path === `/datasets/${ID}/membership/${projection.id}`) {
        const query = request.postDataJSON()
        const headers = { 'X-Atlas-Dtype': 'uint8', 'X-Atlas-Shape': '4' }
        if (query.search === 'bad') return route.fulfill({ body: Buffer.from([1, 1, 0]), headers: { ...headers, 'X-Atlas-Shape': '3' }, contentType: 'application/octet-stream' })
        if (query.search) { requested = true; await held }
        return route.fulfill({ body: Buffer.from(query.search ? [1, 1, 0, 0] : [1, 1, 1, 1]), headers, contentType: 'application/octet-stream' })
      }
      if (path === `/queries/${ID}`) {
        const query = request.postDataJSON()
        if (!query.search && query.cursor) {
          await lastPage
          return route.fulfill({ json: { snapshot_id: SNAPSHOT, unit: 'example', population_scope: 'preview', records: rows.slice(3), matched_count: 4, returned_count: 1, count_status: 'exact', cursor: null } })
        }
        const chosen = query.search ? rows.slice(0, 2) : rows.slice(0, 3)
        return route.fulfill({ json: { snapshot_id: SNAPSHOT, unit: 'example', population_scope: 'preview', records: chosen, matched_count: query.search ? 2 : 4, returned_count: chosen.length, count_status: 'exact', cursor: query.search ? null : 'last' } })
      }
      if (path === '/records') {
        const body = request.postDataJSON() as { ids: string[]; snapshot_ids?: string[] }
        recordReads.push(body)
        // Simulate an activation after the projection was opened. An unbound
        // lookup would return newer content for exactly the same stable ID.
        const pinned = body.snapshot_ids?.includes(SNAPSHOT)
        return route.fulfill({ json: rows.filter(row => body.ids.includes(row.id)).map(row => pinned ? row : { ...row, snapshot_id: 'synthetic-new-active', text: 'Synthetic replacement from another snapshot' }) })
      }
      throw new Error(`Unexpected synthetic membership API ${path}`)
    })
    await page.goto(`/?mode=workbench#/dataset/${ID}`)
    await switchView(page, 'Map')
    await expect(page.locator('.map-strip')).toContainText('4 plotted')
    await expect.poll(() => page.evaluate(() => (window as typeof window & { atlasMapDraw: { lastIndexedPointCount: number } }).atlasMapDraw.lastIndexedPointCount)).toBe(4)
    await expect(page.getByRole('button', { name: 'Cluster 0 · 4', exact: true })).toBeVisible()
    await expect(page.locator('.scopeline')).toContainText('3 loaded')
    await inspectLastProjectionPoint(page)
    const inspector = page.getByRole('complementary', { name: 'Sample inspector' })
    await expect(inspector).toContainText(rows[3].text)
    expect(recordReads).toContainEqual({ ids: [ids[3]], snapshot_ids: [SNAPSHOT] })
    await expect(inspector).not.toContainText('Synthetic replacement from another snapshot')
    releasePage!()
    await expect(page.locator('.scopeline')).toContainText('4 loaded')
    await page.getByRole('button', { name: 'Close panel', exact: true }).click()
    await page.getByRole('textbox', { name: 'Search records in this dataset' }).fill('keep')
    await expect.poll(() => requested).toBe(true)
    await expect(page.locator('.map-stage')).toContainText('Resolving projection population')
    await expect(page.getByRole('button', { name: 'Lasso', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: /^Cluster 0/ })).toHaveCount(0)
    release!()
    await expect(page.locator('.map-strip')).toContainText('2 plotted')
    await expect.poll(() => page.evaluate(() => (window as typeof window & { atlasMapDraw: { lastIndexedPointCount: number } }).atlasMapDraw.lastIndexedPointCount)).toBe(2)
    await expect(page.getByRole('button', { name: 'Cluster 0 · 2', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Cluster 0 · 2', exact: true }).click()
    await expect(selectionBar(page).locator('.count')).toHaveText('2 selected')
    await selectionBar(page).getByRole('button', { name: 'Clear', exact: true }).click()
    await expect(selectionBar(page)).toHaveCount(0)
    await expect(page.locator('.map-strip')).toContainText('2 plotted')
    await expect.poll(() => page.evaluate(() => (window as typeof window & { atlasMapDraw: { lastIndexedPointCount: number } }).atlasMapDraw.lastIndexedPointCount)).toBe(2)
    await lassoAll(page)
    await expect(selectionBar(page).locator('.count')).toHaveText('2 selected')
    await page.getByRole('textbox', { name: 'Search records in this dataset' }).fill('')
    await expect(page.locator('.map-strip')).toContainText('4 plotted')
    await expect(page.getByRole('button', { name: 'Cluster 0 · 4', exact: true })).toBeVisible()
    expect(JSON.stringify(projection)).toBe(original)
    expect(fitRequests).toBe(0)
    await page.getByRole('textbox', { name: 'Search records in this dataset' }).fill('bad')
    await expect(page.locator('.map-stage')).toContainText(/membership.*length/i)
    await expect(page.locator('.map-strip')).toContainText('0 plotted')
    await expect(page.getByRole('button', { name: 'Lasso', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: /^Cluster 0/ })).toHaveCount(0)
  })
}
