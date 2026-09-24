import { expect, test } from '@playwright/test'

test('Visual6502 transistors browse as source-backed structured records', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the pinned Visual6502 release.')
  const api = process.env.ATLAS_LIVE_API!
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const upstream = await fetch(`${api}${url.pathname}${url.search}`, {
      method: request.method(),
      headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' },
      body: request.method() === 'GET' ? undefined : request.postData() ?? undefined,
    })
    await route.fulfill({ status: upstream.status, contentType: upstream.headers.get('content-type') ?? 'application/json', body: Buffer.from(await upstream.arrayBuffer()) })
  })
  await page.goto('/?mode=workbench#/dataset/visual6502-transistor-netlist')
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  await expect(page.locator('.focus-stage')).toContainText(/gate \d+/)
})
