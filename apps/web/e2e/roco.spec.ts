import { expect, test } from '@playwright/test'

test('real ROCO preview opens its pinned original image with source licence', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared ROCO population.')
  const api = process.env.ATLAS_LIVE_API!
  const packResponse = await fetch(`${api}/api/v1/datasets/roco/pack`)
  expect(packResponse.ok).toBeTruthy()
  const pack = await packResponse.json()
  expect(pack.records).toHaveLength(100)
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const response = await fetch(`${api}${url.pathname}${url.search}`, {
      method: request.method(),
      headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' },
      body: request.method() === 'GET' ? undefined : request.postData() ?? undefined,
    })
    await route.fulfill({ status: response.status, contentType: response.headers.get('content-type') ?? 'application/octet-stream', body: Buffer.from(await response.arrayBuffer()) })
  })
  await page.goto('/?mode=workbench#/dataset/roco')
  await page.locator('.sample-card .open').first().dblclick()
  const image = page.locator('.focus-stage img')
  await expect.poll(async () => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  await expect(page.getByLabel('Selected image representation')).toContainText('Original')
  const firstAsset = pack.records[0].assets[0]
  expect(firstAsset.metadata.source_license).toBeTruthy()
  const response = await page.request.get(`${api}${firstAsset.uri}`)
  expect(response.status()).toBe(200)
  expect(response.headers()['x-atlas-media-representation']).toBe('original')
})
