import { expect, test } from '@playwright/test'

test('native radiograph and its paired mask load at their actual dimensions', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires Kaggle v5 prepared locally.')
  const api = process.env.ATLAS_LIVE_API!
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
  await page.goto('/?mode=workbench#/dataset/covid-19-radiography')
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  await page.getByRole('button', { name: 'Open', exact: true }).last().click()
  const chooser = page.getByLabel('Choose image in this record')
  await expect(chooser.locator('option')).toHaveCount(2)
  const image = page.locator('.focus-stage img')
  for (const [position, expected] of [['0', 299], ['1', 256]] as const) {
    await chooser.selectOption(position)
    await expect.poll(async () => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth)).toBe(expected)
    await expect(page.getByLabel('Selected image representation')).toContainText('Original')
  }
})
