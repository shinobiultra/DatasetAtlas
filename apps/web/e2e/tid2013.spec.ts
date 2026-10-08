import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

test('TID2013 native BMP originals and their paired reference render', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared native author archive.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/tid2013/pack`)
  expect(response.ok).toBeTruthy()
  const pack = await response.json()
  expect(pack.dataset.coverage.total_count).toBe(3000)
  expect(pack.records).toHaveLength(100)
  const native = new Set(pack.records.flatMap((record: { assets: { sha256: string }[] }) => record.assets.map(asset => asset.sha256)))
  const hashes: string[] = []
  page.on('response', async response => {
    if (response.url().includes('/api/v1/media/') && response.headers()['content-type']?.startsWith('image/bmp')) {
      hashes.push(createHash('sha256').update(await response.body()).digest('hex'))
    }
  })
  await page.goto(`${api}/?mode=workbench#/dataset/tid2013`)
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  const image = page.locator('.focus-stage img').first()
  await expect.poll(() => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  await page.getByLabel('Choose image in this record').selectOption('1')
  await expect.poll(() => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  await expect.poll(() => hashes.length).toBeGreaterThan(0)
  for (const hash of hashes) expect(native.has(hash)).toBeTruthy()
  const record = pack.records[0]
  for (const asset of record.assets) {
    const result = await page.request.get(`${api}${asset.uri}`)
    expect(result.status()).toBe(200)
    expect(result.headers()['content-type']).toContain('image/bmp')
    expect(createHash('sha256').update(await result.body()).digest('hex')).toBe(asset.sha256)
  }
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-tid2013-20261007.json', import.meta.url)), JSON.stringify({
    verified_at_utc: new Date().toISOString(), dataset_id: 'tid2013', snapshot_id: pack.dataset.snapshot_id,
    status: 'passed', native_records: 3000, preview_records: 100, original_hashes: hashes,
    paired_original_http_hashes_checked: record.assets.length, paired_reference_browser_render_checked: true,
    scope: 'Native original BMP rendering and paired reference HTTP hashes; exact paper protocol remains unresolved.',
  }, null, 2) + '\n')
})
