import { expect, test } from '@playwright/test'

test('SAEgis shows clean and attacked images with their source, split and attack', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared SAEgis population.')
  const api = process.env.ATLAS_LIVE_API!
  const packResponse = await fetch(`${api}/api/v1/datasets/saegis-clean-and-adversarial-splits/pack`)
  expect(packResponse.ok).toBeTruthy()
  const pack = await packResponse.json()
  expect(pack.records).toHaveLength(100)
  const attacked = pack.records.find((record: any) => record.source.condition === 'attacked')
  const clean = pack.records.find((record: any) => record.source.condition === 'original')
  expect(attacked && clean).toBeTruthy()
  expect(attacked.source.attack).toMatch(/^(FOA-Attack|M-Attack|SSA-CWA)$/)
  expect(attacked.source.clean_counterpart).toContain('/original/')
  expect(clean.source.attack).toBeNull()
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
  await page.goto('/?mode=workbench#/dataset/saegis-clean-and-adversarial-splits')
  await expect(page.getByText(/attacked by (FOA-Attack|M-Attack|SSA-CWA)/).first()).toBeVisible()
  await expect(page.getByText('clean original').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  const image = page.locator('.focus-stage img')
  await expect.poll(async () => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  expect(await image.evaluate((item: HTMLImageElement) => [item.naturalWidth, item.naturalHeight])).toEqual([224, 224])
  const original = await page.request.get(`${api}${attacked.assets[0].uri}`)
  expect(original.status()).toBe(200)
  expect([...(await original.body()).subarray(0, 8)]).toEqual([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
})

test('SAEgis projection can be coloured by condition and keeps clean and attacked images distinguishable', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared SAEgis population.')
  const api = process.env.ATLAS_LIVE_API!
  const artifacts = await (await fetch(`${api}/api/v1/artifacts?dataset_id=saegis-clean-and-adversarial-splits&view=browse`)).json()
  test.skip(!artifacts.some((artifact: any) => String(artifact.kind).startsWith('project.')), 'No projection run has been made for this dataset in the workspace.')
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
  await page.goto('/?mode=workbench#/dataset/saegis-clean-and-adversarial-splits')
  await page.getByRole('button', { name: 'Map' }).click()
  await page.getByLabel('Colour by').first().selectOption('source.condition')
  const legend = page.locator('[class*=legend]').first()
  await expect(legend).toContainText('original')
  await expect(legend).toContainText('attacked')
})
