import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

test('native Objaverse originals render in a single interactive 3D view', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared native Objaverse population.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/objaverse/pack`)
  expect(response.ok).toBeTruthy()
  const pack = await response.json()
  expect(pack.records).toHaveLength(100)
  expect(pack.dataset.coverage.unit).toBe('entity')
  expect(pack.sampling.method).toBe('sha256_bottom_k_primary_asset_verified_media')
  const seen: { sha256: string; bytes: number }[] = []
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url())
    const upstream = await fetch(`${api}${url.pathname}${url.search}`, {
      method: request.method(), headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' },
      body: request.method() === 'GET' ? undefined : request.postData() ?? undefined,
    })
    const body = Buffer.from(await upstream.arrayBuffer())
    if (url.pathname.includes('/media/') && body.subarray(0, 4).toString() === 'glTF') {
      seen.push({ sha256: createHash('sha256').update(body).digest('hex'), bytes: body.length })
    }
    await route.fulfill({ status: upstream.status, contentType: upstream.headers.get('content-type') ?? 'application/octet-stream', body })
  })
  await page.goto('/?mode=workbench#/dataset/objaverse')
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await expect(page.locator('canvas[data-atlas-model]')).toHaveCount(0)
  await page.locator('.sample-card .open').first().dblclick()
  const canvas = page.locator('canvas[data-atlas-model="original-glb"]')
  await expect(page.getByText('Original GLB · drag to rotate · scroll to zoom', { exact: true }).first()).toBeVisible()
  await expect(canvas).toBeVisible()
  await expect(canvas).toHaveCount(1)
  await expect(page.getByText('Original GLB · drag to rotate · scroll to zoom', { exact: true })).toBeVisible()
  await expect.poll(() => canvas.evaluate((element: HTMLCanvasElement) => element.width > 0 && element.height > 0)).toBeTruthy()
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2)
  await page.mouse.down(); await page.mouse.move(box!.x + box!.width * 0.65, box!.y + box!.height * 0.6); await page.mouse.up()
  await expect(canvas).toBeVisible()
  expect(seen.length).toBeGreaterThan(0)
  for (const proof of seen) expect(pack.records.some((r: { assets: { sha256: string }[] }) => r.assets.some(a => a.sha256 === proof.sha256))).toBeTruthy()
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-objaverse-20261007.json', import.meta.url)), JSON.stringify({
    verified_at_utc: new Date().toISOString(), dataset_id: 'objaverse', snapshot_id: pack.dataset.snapshot_id,
    status: 'passed', native_entity_count: pack.dataset.coverage.total_count, preview_objects: pack.records.length,
    simultaneous_model_canvases: 1, original_byte_checks: seen, orbit_drag_completed: true,
    scope: 'Functional browser rendering and original-byte identity; no render parity with the citing paper is claimed.',
  }, null, 2) + '\n')
})
