import { expect, test } from '@playwright/test'

test('real SafeBench mixed-media example exposes both original audio tracks', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared SafeBench population.')
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
  await page.goto('/?mode=workbench#/dataset/safebench')
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  const chooser = page.getByLabel('Choose media in this record')
  await expect(chooser.locator('option')).toHaveCount(3)
  for (const position of ['1', '2']) {
    await chooser.selectOption(position)
    const player = page.locator('.focus-stage audio[controls]')
    await expect(player).toBeVisible()
    expect(await player.evaluate(element => element.getBoundingClientRect().width)).toBeGreaterThan(300)
    const response = await player.evaluate(async element => {
      const result = await fetch((element as HTMLAudioElement).src)
      return { status: result.status, contentType: result.headers.get('content-type') }
    })
    expect(response.status).toBe(200)
    expect(response.contentType).toContain('audio/wav')
  }
})
