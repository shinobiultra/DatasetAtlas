import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { inspectRecord } from './helpers'

for (const datasetId of ['fairface', 'seed-bench-2']) {
  test(`real ${datasetId} retains labelled native crop/frame order`, async ({ page }) => {
    test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared native source population.')
    test.setTimeout(120_000)
    const api = process.env.ATLAS_LIVE_API!
    const response = await fetch(`${api}/api/v1/datasets/${datasetId}/pack`)
    expect(response.ok).toBeTruthy()
    const pack = await response.json()
    const count = datasetId === 'fairface' ? 2 : 8
    const record = pack.records.find((row: { assets: unknown[] }) => row.assets.length === count)
    expect(record).toBeTruthy()
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), url = new URL(request.url())
      const result = await fetch(`${api}${url.pathname}${url.search}`, { method: request.method(), headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' }, body: request.method() === 'GET' ? undefined : request.postData() ?? undefined })
      await route.fulfill({ status: result.status, contentType: result.headers.get('content-type') ?? 'application/octet-stream', body: Buffer.from(await result.arrayBuffer()) })
    })
    await page.goto(`/?mode=workbench#/dataset/${datasetId}`)
    const inspector = await inspectRecord(page, record.id)
    await inspector.getByRole('button', { name: 'Open', exact: true }).click()
    const chooser = page.getByLabel('Choose image in this record')
    await expect(chooser.locator('option')).toHaveCount(count)
    for (const index of [0, count - 1]) {
      await chooser.selectOption(String(index))
      await expect(page.getByLabel('Selected image representation')).toContainText(record.assets[index].metadata.condition)
      await expect.poll(async () => page.locator('.focus-stage img').evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0), { timeout: 60_000 }).toBeTruthy()
    }
    writeFileSync(fileURLToPath(new URL(`../../../reports/browser-${datasetId}.json`, import.meta.url)), JSON.stringify({ verified_at_utc: new Date().toISOString(), dataset_id: datasetId, snapshot_id: pack.dataset.snapshot_id, record_id: record.id, status: 'passed', labelled_conditions: record.assets.map((asset: { metadata: { condition: string } }) => asset.metadata.condition), first_and_last_native_image_displayed: true }, null, 2) + '\n')
  })
}
