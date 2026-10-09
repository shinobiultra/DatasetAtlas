import { expect, test } from '@playwright/test'

test('COCO-GB keeps release variants apart and shows the authors\' native gender integer without naming it', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared COCO-GB population.')
  const api = process.env.ATLAS_LIVE_API!
  const pack = await (await fetch(`${api}/api/v1/datasets/cocogender/pack`)).json()
  expect(pack.records).toHaveLength(100)
  const variants = new Set(pack.records.map((record: any) => record.source.release_variant))
  expect(variants).toEqual(new Set(['v1', 'v2']))
  const ids = pack.records.map((record: any) => record.source.source_id)
  expect(new Set(ids).size).toBe(ids.length)
  const gender = pack.fields.find((field: any) => field.id === 'source.gender')
  expect(gender.description).toContain('coding not documented')
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
  await page.goto('/?mode=workbench#/dataset/cocogender')
  await page.locator('.sample-card .open').first().dblclick()
  const image = page.locator('.focus-stage img')
  await expect.poll(async () => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  const original = await page.request.get(`${api}${pack.records[0].assets[0].uri}`)
  expect(original.status()).toBe(200)
  expect([...(await original.body()).subarray(0, 3)]).toEqual([0xff, 0xd8, 0xff])
})
