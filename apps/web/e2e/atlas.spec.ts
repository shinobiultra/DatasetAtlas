import { expect, test, type Page } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

type Point = { id: string; x: number; y: number }
const packPath = fileURLToPath(new URL('../public/data/clevr.json', import.meta.url))

async function forwardLocalApi(page: Page, api: string, allowedMediaToken?: string) {
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url())
    if (allowedMediaToken && url.pathname.startsWith('/api/v1/media/') && !url.pathname.endsWith(`/${allowedMediaToken}`)) return route.abort()
    const range = request.headers().range
    const response = await fetch(`${api}${url.pathname}${url.search}`, {
      method: request.method(),
      headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1', ...(range ? { Range: range } : {}) },
      body: request.method() === 'GET' ? undefined : request.postData() ?? undefined,
    })
    await route.fulfill({ status: response.status, headers: { 'Content-Type': response.headers.get('content-type') ?? 'application/octet-stream', ...(response.headers.get('content-range') ? { 'Content-Range': response.headers.get('content-range')! } : {}), ...(response.headers.get('accept-ranges') ? { 'Accept-Ranges': response.headers.get('accept-ranges')! } : {}) }, body: Buffer.from(await response.arrayBuffer()) })
  })
}

test('published CLEVR catalogue → source filter → map → inspector', async ({ page }) => {
  const pack = JSON.parse(readFileSync(packPath, 'utf8'))
  const matched = pack.records.filter((record: { source: { answer: string } }) => record.source.answer === 'no')
  const projection = pack.artifacts.find((artifact: { kind: string }) => artifact.kind === 'project.umap')
  expect(projection).toBeTruthy()
  const points: Point[] = projection.data.points
  expect(points.length).toBe(100)

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Explore datasets' })).toBeVisible()
  await page.locator('.dataset-row').filter({ has: page.locator('strong', { hasText: /^CLEVR$/ }) }).click()
  await expect(page.getByRole('heading', { name: 'CLEVR' })).toBeVisible()
  await expect(page.locator('.record-card')).toHaveCount(48)
  await page.getByText('Filters', { exact: true }).click()
  await page.locator('.workspace-controls .filter-fields select').first().selectOption('source.answer')
  await page.getByLabel('Filter value').fill('no')
  await expect(page.locator('.scope-line')).toContainText(`${matched.length} matches`)
  await page.getByRole('button', { name: 'Map', exact: true }).click()
  const canvas = page.getByRole('img', { name: new RegExp(`Projection with ${matched.length} visible records`) })
  await expect(canvas).toBeVisible()
  await expect(page.locator('.map-wrap')).toContainText(`${matched.length} plotted of ${matched.length} loaded records`)

  const xs = points.map(point => point.x), ys = points.map(point => point.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
  const target = points.find(point => matched.some((record: { id: string }) => record.id === point.id))!
  const x = 24 + 752 * (target.x - minX) / (maxX - minX || 1)
  const y = 24 + 452 * (1 - (target.y - minY) / (maxY - minY || 1))
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()
  await canvas.click({ position: { x: x * box!.width / 800, y: y * box!.height / 500 } })
  await expect(page.getByRole('complementary', { name: 'Sample inspector' })).toBeVisible()
  await expect(page.getByText(target.id, { exact: true })).toBeVisible()
  await expect(page.getByText('Source fields', { exact: true })).toBeVisible()
})

test('About drawer keeps unpublished evidence absent and shows public source', async ({ page }, testInfo) => {
  await page.goto('/#/dataset/clevr')
  await page.getByRole('button', { name: 'About' }).click()
  const drawer = page.getByRole('dialog', { name: 'about drawer' })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('heading', { name: 'Evidence', exact: true })).toBeVisible()
  await expect(drawer.getByText('No evidence receipts registered.')).toBeVisible()
  await expect(drawer.getByRole('link', { name: 'Original source ↗' })).toHaveAttribute('href', /^https:\/\//)
  await drawer.screenshot({ path: testInfo.outputPath('about-public-clevr.png') })
})

test('About relationship opens a distinct catalogue dataset with its own coverage', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Local workbench catalogue exposes source and release relationships.')
  await forwardLocalApi(page, process.env.ATLAS_LIVE_API!)
  await page.goto('/?mode=workbench#/dataset/clevr')
  await page.getByRole('button', { name: 'About' }).click()
  const drawer = page.getByRole('dialog', { name: 'about drawer' })
  const related = drawer.getByRole('region', { name: 'Related datasets' })
  await expect(related).toContainText('has complete release variant')
  await expect(related).toContainText('Status: verified')
  await related.getByRole('button', { name: /clevr-v1-full/ }).click()
  await expect(page).toHaveURL(/#\/dataset\/clevr-v1-full$/)
  await expect(page.getByRole('heading', { name: 'CLEVR v1.0 (official complete release)' })).toBeVisible()
  await expect(page.locator('.scope-line')).toContainText('100 example preview')
})

test('local workbench About renders source and paper receipts when available', async ({ page }, testInfo) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Set ATLAS_LIVE_API to a running local workbench URL for this optional integration check.')
  await forwardLocalApi(page, process.env.ATLAS_LIVE_API!)
  await page.goto('/?mode=workbench#/dataset/clevr')
  await page.getByRole('button', { name: 'About' }).click()
  const drawer = page.getByRole('dialog', { name: 'about drawer' })
  await expect(drawer.getByRole('heading', { name: 'Evidence', exact: true })).toBeVisible()
  await expect(drawer.getByRole('heading', { name: /Source and release evidence/ })).toBeVisible()
  await expect(drawer.getByRole('heading', { name: /Paper mentions/ })).toBeVisible()
  await expect(drawer.getByText(/Paper text check/)).toBeVisible()
  await expect(drawer.getByText(/Source or release reference/).first()).toBeVisible()
  await drawer.locator('.evidence-section').screenshot({ path: testInfo.outputPath('about-local-clevr-evidence.png') })
})

test('local COCO completed detector overlays remain visible on original media', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Set ATLAS_LIVE_API to a running local workbench URL for this optional integration check.')
  await forwardLocalApi(page, process.env.ATLAS_LIVE_API!)
  await page.goto('/?mode=workbench#/dataset/coco')
  await page.getByRole('button', { name: 'Inspect record coco:example:c765b3eb380b785ef8fc414d' }).click()
  const inspector = page.getByRole('complementary', { name: 'Sample inspector' })
  await expect(inspector.locator('.box-overlay rect')).toHaveCount(32)
  await expect(inspector.getByRole('status').filter({ hasText: 'detect.coco_v1' })).toContainText('Completed: 32 detections')
  await expect(inspector.locator('.media-geometry-warning')).toHaveCount(0)
})

test('local VHD H.264 clip exposes metadata and native playback without fetching large codec controls', async ({ page, browser }, testInfo) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Set ATLAS_LIVE_API to a running local workbench URL for this optional integration check.')
  const api = process.env.ATLAS_LIVE_API!
  const id = 'vhd11k:example:d94f12a071554f8f6f2fdbea'
  const lookup = await fetch(`${api}/api/v1/records`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' }, body: JSON.stringify({ ids: [id] }) })
  expect(lookup.ok).toBe(true)
  const [record] = await lookup.json() as Array<{ source: { source_id: string }; assets: Array<{ uri: string }> }>
  expect(record.source.source_id).toBeTruthy()
  const mediaToken = record.assets[0]?.uri.split('/').at(-1)
  expect(mediaToken).toBeTruthy()
  await forwardLocalApi(page, api, mediaToken)
  await page.goto('/?mode=workbench#/dataset/vhd11k')
  await page.getByLabel('Population scope').selectOption('complete')
  await expect(page.locator('.scope-line')).toContainText('11000 example complete index')
  await page.getByText('Filters', { exact: true }).click()
  await page.locator('.workspace-controls .filter-fields select').first().selectOption('source.source_id')
  await page.getByLabel('Filter value').fill(record.source.source_id)
  await expect(page.locator('.scope-line')).toContainText('1 match')
  await expect(page.locator('.record-card')).toHaveCount(1)
  await page.getByText('Filters', { exact: true }).click()
  await page.getByRole('button', { name: `Inspect record ${id}` }).click()
  const video = page.getByRole('complementary', { name: 'Sample inspector' }).locator('video')
  await expect(video).toBeVisible()
  const observation = await video.evaluate(async element => {
    const media = element as HTMLVideoElement
    media.muted = true
    media.preload = 'metadata'
    media.load()
    const outcome = await Promise.race([
      new Promise<string>(resolve => { if (media.readyState >= 1) resolve('metadata'); else { media.addEventListener('loadedmetadata', () => resolve('metadata'), { once: true }); media.addEventListener('error', () => resolve('error'), { once: true }) } }),
      new Promise<string>(resolve => setTimeout(() => resolve('timeout'), 8000)),
    ])
    let playOutcome = 'not attempted'
    let playbackPosition = 0
    let decodedFrames: number | null = null
    if (outcome === 'metadata') {
      try {
        await Promise.race([media.play(), new Promise<never>((_, reject) => setTimeout(() => reject(new Error('play timeout')), 4000))])
        await new Promise(resolve => setTimeout(resolve, 300))
        playOutcome = media.paused ? 'paused' : 'playing'
        playbackPosition = media.currentTime
        decodedFrames = media.getVideoPlaybackQuality().totalVideoFrames
        media.pause()
      } catch (error) { playOutcome = String(error) }
    }
    return { outcome, playOutcome, playbackPosition, decodedFrames, readyState: media.readyState, networkState: media.networkState, duration: media.duration, width: media.videoWidth, height: media.videoHeight, errorCode: media.error?.code ?? null, h264Capability: media.canPlayType('video/mp4; codecs="avc1.640028"'), mpeg4VisualCapability: media.canPlayType('video/mp4; codecs="mp4v.20.9"') }
  })
  console.log(`Local VHD browser video: ${JSON.stringify({ ...observation, browserVersion: browser.version(), recordId: id })}`)
  writeFileSync(testInfo.outputPath('local-vhd-video.json'), JSON.stringify({ ...observation, browserVersion: browser.version(), recordId: id }, null, 2))
  expect(observation.outcome).toBe('metadata')
  expect(observation.width).toBe(1024)
  expect(observation.height).toBe(1024)
  expect(observation.playOutcome).toBe('playing')
  expect(observation.playbackPosition).toBeGreaterThan(0)
})
