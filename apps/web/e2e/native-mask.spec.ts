import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { inspectRecord } from './helpers'

test('real TextVQA-X mask is labelled and its native array downloads unchanged', async ({ page }, testInfo) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the locally prepared TextVQA-X release.')
  const api = process.env.ATLAS_LIVE_API!
  const packResponse = await fetch(`${api}/api/v1/datasets/textvqa-x/pack`)
  expect(packResponse.ok).toBeTruthy()
  const pack = await packResponse.json()
  const record = pack.records[0], array = record.assets.find((asset: { modality: string }) => asset.modality === 'array')
  const original = Buffer.from(await (await fetch(`${api}${array.uri}`)).arrayBuffer())
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url())
    const response = await fetch(`${api}${url.pathname}${url.search}`, { method: request.method(), headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' }, body: request.method() === 'GET' ? undefined : request.postData() ?? undefined })
    await route.fulfill({ status: response.status, contentType: response.headers.get('content-type') ?? 'application/octet-stream', body: Buffer.from(await response.arrayBuffer()) })
  })
  await page.goto('/?mode=workbench#/dataset/textvqa-x')
  const inspector = await inspectRecord(page, record.id)
  await inspector.getByRole('button', { name: 'Open', exact: true }).click()
  await page.getByLabel('Choose image in this record').selectOption('1')
  await expect(page.getByLabel('Selected image representation')).toContainText('visual explanation mask')
  await expect(page.getByLabel('Selected image representation')).toContainText('Lossless mask view')
  await expect(page.locator('.focus-stage img')).toHaveJSProperty('complete', true)
  const width = await page.locator('.focus-stage img').evaluate((image: HTMLImageElement) => image.naturalWidth)
  expect(width).toBeGreaterThan(0)
  await inspector.getByRole('tab', { name: 'Metadata', exact: true }).click()
  const downloadPromise = page.waitForEvent('download')
  await inspector.getByRole('link', { name: 'Download native array' }).click()
  const download = await downloadPromise, path = testInfo.outputPath('native-mask.npy')
  await download.saveAs(path)
  expect(readFileSync(path)).toEqual(original)
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-native-mask.json', import.meta.url)), JSON.stringify({ verified_at_utc: new Date().toISOString(), dataset_id: 'textvqa-x', record_id: record.id, status: 'passed', labelled_lossless_mask: true, native_array_download_bytes: original.length, native_array_sha256: createHash('sha256').update(original).digest('hex') }, null, 2) + '\n')
})
