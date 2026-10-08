import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

for (const [id, population] of [['openimages', 41620], ['mit-states', 63440], ['ffhq', 70000], ['emoset', 118102]] as const) {
  test(`${id} native preview originals decode through the workbench`, async ({ page }) => {
    test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared native population.')
    const api = process.env.ATLAS_LIVE_API!
    const response = await fetch(`${api}/api/v1/datasets/${id}/pack`)
    expect(response.ok).toBeTruthy()
    const pack = await response.json()
    expect(pack.dataset.coverage.total_count).toBe(population)
    expect(pack.records).toHaveLength(100)
    const asset = pack.records[0].assets[0]
    const original = await fetch(`${api}${asset.uri}`)
    expect(original.ok).toBeTruthy()
    const sha = createHash('sha256').update(Buffer.from(await original.arrayBuffer())).digest('hex')
    expect(sha).toBe(asset.sha256)
    await page.goto(`${api}/?mode=workbench#/dataset/${id}`)
    await expect(page.locator('.sample-card').first()).toBeVisible()
    await page.locator('.sample-card .open').first().dblclick()
    await expect.poll(() => page.locator('.focus-stage img').first().evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
    writeFileSync(fileURLToPath(new URL(`../../../reports/browser-${id}-native-20261007.json`, import.meta.url)), JSON.stringify({
      verified_at_utc: new Date().toISOString(), status: 'passed', dataset_id: id, snapshot_id: pack.dataset.snapshot_id,
      native_population: population, preview_records: 100, checked_original_sha256: sha, browser_decoded_original: true,
      source_scope: ({ 'mit-states': 'Pinned public mirror; publisher-byte equality and paper membership unverified', 'openimages': 'Pinned publisher V7 validation tables; paper release unidentified', 'ffhq': 'Publisher metadata and file/pixel MD5 verified original aligned PNGs; paper cohort and redistribution rights unverified', 'emoset': 'Full author-linked 118K archive and native split/annotation membership; SHA-block-verified originals; paper cohort and redistribution rights unverified' } as const)[id],
    }, null, 2) + '\n')
  })
}

test('UCF101 original AVI is retained and its lossless browser display plays and seeks', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared UCF101 native mirror population.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/ucf101/pack`)
  expect(response.ok).toBeTruthy()
  const pack = await response.json()
  expect(pack.dataset.coverage.total_count).toBe(13320)
  expect(pack.records).toHaveLength(100)
  const asset = pack.records[0].assets[0]
  const original = await fetch(`${api}${asset.uri}`)
  expect(original.headers.get('content-type')).toBe('video/x-msvideo')
  const sha = createHash('sha256').update(Buffer.from(await original.arrayBuffer())).digest('hex')
  expect(sha).toBe(asset.sha256)
  const display = await fetch(`${api}${asset.uri}?representation=display`, { headers: { Range: 'bytes=0-31' } })
  expect(display.status).toBe(206)
  expect(display.headers.get('content-type')).toBe('video/mp4')
  expect(display.headers.get('x-atlas-original-sha256')).toBe(sha)
  await page.goto(`${api}/?mode=workbench#/dataset/ucf101`)
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  const video = page.locator('.focus-stage video').first()
  await video.evaluate((item: HTMLVideoElement) => { item.muted = true; item.load() })
  await expect.poll(() => video.evaluate((item: HTMLVideoElement) => Number.isFinite(item.duration) && item.duration > 0)).toBeTruthy()
  await video.evaluate(async (item: HTMLVideoElement) => { await item.play() })
  await expect.poll(() => video.evaluate((item: HTMLVideoElement) => item.currentTime > 0 && !item.paused)).toBeTruthy()
  await video.evaluate((item: HTMLVideoElement) => { item.pause(); item.currentTime = item.duration / 2 })
  await expect.poll(() => video.evaluate((item: HTMLVideoElement) => !item.seeking && item.currentTime > 0)).toBeTruthy()
  const technical = await video.evaluate((item: HTMLVideoElement) => ({ duration_seconds: item.duration, seek_seconds: item.currentTime, ready_state: item.readyState }))
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-ucf101-native-20261007.json', import.meta.url)), JSON.stringify({
    verified_at_utc: new Date().toISOString(), status: 'passed', snapshot_id: pack.dataset.snapshot_id, population: 13320, preview_records: 100,
    original_sha256: sha, byte_range_verified: true, muted_playback_and_seek_verified: true, ...technical,
    scope: 'Pinned public mirror native AVI and annotation tables; lossless video display derivative; publisher equality and paper membership unverified',
  }, null, 2) + '\n')
})
