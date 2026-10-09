import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

test('Places365 native validation originals open in the browser', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared native Places365 validation population.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/places/pack`)
  expect(response.ok).toBeTruthy()
  const pack = await response.json()
  expect(pack.dataset.coverage.total_count).toBe(36500)
  expect(pack.records).toHaveLength(100)
  const hashes: string[] = []
  page.on('response', async response => {
    if (response.url().includes('/api/v1/media/') && response.headers()['content-type']?.startsWith('image/')) {
      hashes.push(createHash('sha256').update(await response.body()).digest('hex'))
    }
  })
  await page.goto(`${api}/?mode=workbench#/dataset/places`)
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  const image = page.locator('.focus-stage img')
  await expect.poll(() => image.evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  await expect.poll(() => hashes.length).toBeGreaterThan(0)
  // Drain all in-flight native-byte checks before Playwright closes the page.
  await page.removeAllListeners('response', { behavior: 'wait' })
  const native = new Set(pack.records.flatMap((record: { assets: { sha256: string }[] }) => record.assets.map(asset => asset.sha256)))
  for (const hash of hashes) expect(native.has(hash)).toBeTruthy()
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-places365-20261007.json', import.meta.url)), JSON.stringify({
    verified_at_utc: new Date().toISOString(), dataset_id: 'places', snapshot_id: pack.dataset.snapshot_id,
    status: 'passed', native_records: 36500, preview_records: 100, original_hashes: hashes,
    scope: 'Publisher-prepared Places365 Standard256 validation originals; historical paper population remains unidentified.',
  }, null, 2) + '\n')
})

test('Spoken Wikipedia whole-article native audio plays and seeks', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API || !process.env.ATLAS_NATIVE_AUDIO, 'Requires the completed native audio preparation.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/spoken-wikipedia/pack`)
  expect(response.ok).toBeTruthy()
  const pack = await response.json()
  expect(pack.records).toHaveLength(100)
  expect(pack.records[0].assets.some((asset: { modality: string }) => asset.modality === 'audio')).toBeTruthy()
  await page.goto(`${api}/?mode=workbench#/dataset/spoken-wikipedia`)
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  const audio = page.locator('.focus-stage audio').first()
  await expect(audio).toBeVisible()
  await audio.evaluate((item: HTMLAudioElement) => { item.muted = true; item.load() })
  await expect.poll(() => audio.evaluate((item: HTMLAudioElement) => Number.isFinite(item.duration) && item.duration > 0), { timeout: 60000 }).toBeTruthy()
  await audio.evaluate(async (item: HTMLAudioElement) => { await item.play() })
  await expect.poll(() => audio.evaluate((item: HTMLAudioElement) => item.currentTime > 0 && !item.paused)).toBeTruthy()
  await audio.evaluate((item: HTMLAudioElement) => { item.pause(); item.currentTime = Math.min(30, item.duration / 3) })
  await expect.poll(() => audio.evaluate((item: HTMLAudioElement) => !item.seeking && item.currentTime > 0)).toBeTruthy()
  const technical = await audio.evaluate((item: HTMLAudioElement) => ({ duration_seconds: item.duration, seek_seconds: item.currentTime, ready_state: item.readyState }))
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-spoken-wikipedia-native-audio-20261007.json', import.meta.url)), JSON.stringify({
    verified_at_utc: new Date().toISOString(), dataset_id: 'spoken-wikipedia', snapshot_id: pack.dataset.snapshot_id,
    status: 'passed', native_sentence_records: pack.dataset.coverage.total_count, preview_records: pack.records.length,
    muted_playback_and_seek_checked: true, ...technical,
    scope: 'Native whole-article audio parts linked to sentence annotations; playback does not claim sentence clips or paper-specific alignment.',
  }, null, 2) + '\n')
})

test('VOC2011 native images and palette masks open in the browser', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the prepared native VOC2011 archive.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/pascal-voc/pack`)
  expect(response.ok).toBeTruthy()
  const pack = await response.json()
  expect(pack.dataset.coverage.total_count).toBe(14961)
  expect(pack.records).toHaveLength(100)
  const masked = pack.records.find((record: { assets: { metadata: { role?: string } }[] }) => record.assets.some(asset => asset.metadata.role === 'native class segmentation mask'))
  expect(masked).toBeTruthy()
  const masks = masked.assets.filter((asset: { metadata: { role?: string } }) => asset.metadata.role?.endsWith('segmentation mask'))
  expect(masks).toHaveLength(2)
  const maskHashes: string[] = []
  for (const mask of masks) {
    const media = await fetch(`${api}${mask.uri}`)
    expect(media.ok).toBeTruthy()
    expect(media.headers.get('content-type')).toBe('image/png')
    const hash = createHash('sha256').update(Buffer.from(await media.arrayBuffer())).digest('hex')
    expect(hash).toBe(mask.sha256)
    maskHashes.push(hash)
  }
  await page.goto(`${api}/?mode=workbench#/dataset/pascal-voc`)
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.locator('.sample-card .open').first().dblclick()
  await expect.poll(() => page.locator('.focus-stage img').first().evaluate((item: HTMLImageElement) => item.complete && item.naturalWidth > 0)).toBeTruthy()
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-pascal-voc2011-20261007.json', import.meta.url)), JSON.stringify({
    verified_at_utc: new Date().toISOString(), dataset_id: 'pascal-voc', snapshot_id: pack.dataset.snapshot_id,
    status: 'passed', native_image_xml_pairs: 14961, preview_records: 100, palette_mask_original_hashes: maskHashes,
    scope: 'VOC2011 native JPEG and palette PNG originals; main classification split and paper membership remain explicit.',
  }, null, 2) + '\n')
})
