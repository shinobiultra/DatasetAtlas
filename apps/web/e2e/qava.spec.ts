import { expect, test } from '@playwright/test'

test('QAVA 32×50 subset opens a pinned original COCO image', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared QAVA author subset.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/vqa-v2-m-n-subsets/pack`)
  expect(response.ok).toBeTruthy()
  const pack = await response.json()
  expect(pack.records).toHaveLength(100)
  expect(pack.sampling.method).toBe('sha256_asset_first_with_example_fill')
  expect(new Set(pack.records.map((record: { assets: { id: string }[] }) => record.assets[0].id)).size).toBe(32)
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const upstream = await fetch(`${api}${url.pathname}${url.search}`, {
      method: request.method(),
      headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' },
      body: request.method() === 'GET' ? undefined : request.postData() ?? undefined,
    })
    await route.fulfill({ status: upstream.status, contentType: upstream.headers.get('content-type') ?? 'application/octet-stream', body: Buffer.from(await upstream.arrayBuffer()) })
  })
  await page.goto('/?mode=workbench#/dataset/vqa-v2-m-n-subsets')
  await page.locator('.sample-card .open').first().dblclick()
  const image = page.locator('.focus-stage img')
  await expect.poll(async () => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  await expect(page.getByLabel('Selected image representation')).toContainText('Original')
})
