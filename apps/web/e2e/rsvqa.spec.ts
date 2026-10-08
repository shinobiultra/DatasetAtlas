import { expect, test } from '@playwright/test'

test('RSVQA-LR TIFF originals render faithfully and stay downloadable unchanged', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared RSVQA-LR population.')
  const api = process.env.ATLAS_LIVE_API!
  const packResponse = await fetch(`${api}/api/v1/datasets/rs-vqa/pack`)
  expect(packResponse.ok).toBeTruthy()
  const pack = await packResponse.json()
  expect(pack.records).toHaveLength(100)
  const first = pack.records[0].assets[0]
  expect(first.metadata.browser_render_required).toBe(true)
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
  const requested: string[] = []
  page.on('request', request => { if (request.url().includes('/api/v1/media/')) requested.push(request.url()) })
  await page.goto('/?mode=workbench#/dataset/rs-vqa')
  await page.locator('.sample-card .open').first().dblclick()
  const image = page.locator('.focus-stage img')
  await expect.poll(async () => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  expect(await image.evaluate((item: HTMLImageElement) => [item.naturalWidth, item.naturalHeight])).toEqual([256, 256])
  await expect(page.getByText('TIFF display derivative').first()).toBeVisible()
  // A faithful rendering, never the blurred safe view.
  expect(requested.some(url => url.includes('representation=display'))).toBeTruthy()
  expect(requested.some(url => url.includes('representation=safe-view'))).toBeFalsy()
  const original = await page.request.get(`${api}${first.uri}`)
  expect(original.status()).toBe(200)
  expect([...(await original.body()).subarray(0, 4)]).toEqual([0x49, 0x49, 0x2a, 0x00])
  const rendering = await page.request.get(`${api}${first.uri}?representation=display`)
  expect(rendering.headers()['content-type']).toBe('image/png')
  expect(rendering.headers()['x-atlas-media-representation']).toBe('display')
})
