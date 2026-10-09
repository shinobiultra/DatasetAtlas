import { expect, test, type Page } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { addFieldFilter, expectPanel, inspectRecord, openDataset, sampleCards, scopeLine, switchView } from './helpers'

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
  await expect(page.getByRole('heading', { name: 'Datasets', exact: true })).toBeVisible()
  await openDataset(page, 'clevr')
  await expect(page.getByRole('heading', { name: 'CLEVR', exact: true })).toBeVisible()
  await expect(sampleCards(page).first()).toBeVisible()

  await addFieldFilter(page, 'source.answer', 'no')
  await expect(scopeLine(page)).toContainText(`${matched.length} matches`)

  await switchView(page, 'Map')
  const canvas = page.locator('.map-stage canvas')
  await expect(canvas).toHaveAttribute('aria-label', new RegExp(`Projection project\\.umap with ${matched.length} plotted points`))
  await expect(page.locator('.map-strip')).toContainText(`${matched.length} plotted`)

  // Click the exact screen position of one matching point and inspect it.
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()
  const present = points.filter(point => matched.some((record: { id: string }) => record.id === point.id))
  const xs = present.map(point => point.x), ys = present.map(point => point.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
  const padding = 26
  const width = box!.width - padding * 2, height = box!.height - padding * 2
  const target = present[0]
  const x = padding + width * (target.x - minX) / (maxX - minX || 1)
  const y = padding + height * (1 - (target.y - minY) / (maxY - minY || 1))
  await canvas.click({ position: { x, y } })

  const inspector = await expectPanel(page, 'Sample inspector')
  await expect(inspector.getByText('Source annotations', { exact: true })).toBeVisible()
  await inspector.getByRole('tab', { name: 'Metadata' }).click()
  await expect(inspector.getByText(target.id, { exact: true })).toBeVisible()
})

test('inspection and selection stay separate interactions', async ({ page }) => {
  await page.goto('/#/dataset/clevr')
  await expect(sampleCards(page).first()).toBeVisible()
  const first = sampleCards(page).first()
  const recordId = await first.getAttribute('data-record-id')
  expect(recordId).toBeTruthy()

  // Clicking a card inspects it and never selects it.
  await page.getByRole('button', { name: `Inspect record ${recordId}` }).click()
  await expectPanel(page, 'Sample inspector')
  await expect(page.locator('.statusbar.active')).toHaveCount(0)
  await expect(first).toHaveAttribute('data-inspected', 'true')

  // Ticking the checkbox selects it and reveals the selection actions.
  await page.getByLabel(`Select record ${recordId}`).check()
  await expect(page.locator('.statusbar.active .count')).toHaveText('1 selected')
  await expect(page.locator('.statusbar.active').getByRole('button', { name: 'Save' })).toBeVisible()
})

test('a public build states what it can show and never claims the workbench preview', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.cat-head')).toContainText('browsable in this public build')
  const unpublished = page.locator('.ds-card').filter({ hasText: 'Metadata only here' }).first()
  await expect(unpublished).toBeVisible()
  await expect(unpublished).toContainText('exists in the local workbench')
})

test('a metadata-only dataset explains the gap instead of showing an empty grid', async ({ page }) => {
  await page.goto('/#/dataset/facet')
  await expect(page.getByText('No inspectable examples here yet')).toBeVisible()
  await expect(page.getByText(/implementation gap in Dataset Atlas/)).toBeVisible()
  await expect(sampleCards(page)).toHaveCount(0)
})

test('a public dataset page says how to get the data, what a record holds and which papers name it', async ({ page }) => {
  await page.goto('/#/dataset/imagenet-1k')
  const how = page.locator('.card').filter({ hasText: 'How to get this dataset' })
  await expect(how).toContainText('Accept terms, then fetch')
  await expect(how.locator('code').first()).toHaveText('atlas previews fetch --dataset imagenet-1k')
  await expect(how.locator('code').nth(1)).toHaveText('atlas previews fetch --dataset imagenet-1k --execute')
  await expect(how.getByRole('button', { name: 'Copy' })).toHaveCount(2)
  const schema = page.locator('.card').filter({ hasText: 'What a record holds' })
  await expect(schema).toContainText('No record values are published here')
  await expect(schema.locator('td.mono').first()).toBeVisible()
  await expect(page.locator('.card').filter({ hasText: /Named in \d+ corpus papers?/ })).toContainText('A mention does not establish')
})

test('the guide separates a maintainer-only preview, a gate, and a request-only release', async ({ page }) => {
  await page.goto('/#/dataset/advbench')
  await expect(page.locator('.card').filter({ hasText: 'How to get this dataset' })).toContainText('Maintainer preview, no public recipe')
  await expect(page.locator('.card').filter({ hasText: 'How to get this dataset' }).locator('code')).toHaveCount(0)
  await expect(page.locator('.card').filter({ hasText: 'What a record holds' }).locator('td.mono').first()).toHaveText('goal')
  await page.goto('/#/dataset/facet')
  await expect(page.locator('.card').filter({ hasText: 'How to get this dataset' })).toContainText('Gated at the source')
  await page.goto('/#/dataset/gyafc')
  const request = page.locator('.card').filter({ hasText: 'How to get this dataset' })
  await expect(request).toContainText('Request from the authors')
  await expect(request.locator('code')).toHaveCount(0)
})

test('the catalogue explains what the public site is and lists the datasets whose examples it publishes', async ({ page }) => {
  await page.goto('/')
  await page.getByText('What this public site is').click()
  await expect(page.locator('.cat-head')).toContainText('The data itself is not hosted here')
  await expect(page.locator('.cat-head')).toContainText('CLEVR')
})

test('About panel keeps unpublished evidence absent and shows the public source', async ({ page }, testInfo) => {
  await page.goto('/#/dataset/clevr')
  await page.getByRole('button', { name: 'About dataset' }).click()
  const about = await expectPanel(page, 'About dataset')
  await about.getByText(/^Evidence \(/).click()
  await expect(about.getByText('No evidence receipts are registered.')).toBeVisible()
  await expect(about.getByRole('link', { name: 'Original source' })).toHaveAttribute('href', /^https:\/\//)
  await about.screenshot({ path: testInfo.outputPath('about-public-clevr.png') })
})

test('About relationship opens a distinct catalogue dataset with its own coverage', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Local workbench catalogue exposes source and release relationships.')
  await forwardLocalApi(page, process.env.ATLAS_LIVE_API!)
  await page.goto('/?mode=workbench#/dataset/clevr')
  await page.getByRole('button', { name: 'About dataset' }).click()
  const about = await expectPanel(page, 'About dataset')
  await expect(about).toContainText('has complete release variant')
  await about.getByRole('button', { name: /CLEVR v1\.0/ }).click()
  await expect(page).toHaveURL(/#\/dataset\/clevr-v1-full$/)
  await expect(page.getByRole('heading', { name: 'CLEVR v1.0 (official complete release)' })).toBeVisible()
  await expect(scopeLine(page)).toContainText('100 example records')
})

test('local workbench About renders source and paper receipts when available', async ({ page }, testInfo) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Set ATLAS_LIVE_API to a running local workbench URL for this optional integration check.')
  await forwardLocalApi(page, process.env.ATLAS_LIVE_API!)
  await page.goto('/?mode=workbench#/dataset/clevr')
  await page.getByRole('button', { name: 'About dataset' }).click()
  const about = await expectPanel(page, 'About dataset')
  await about.getByText(/^Evidence \(/).click()
  await expect(about.getByText(/separate review scopes/)).toBeVisible()
  await expect(about.getByText('Full receipt').first()).toBeVisible()
  await about.screenshot({ path: testInfo.outputPath('about-local-clevr-evidence.png') })
})

test('local COCO completed detector overlays remain visible on original media', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Set ATLAS_LIVE_API to a running local workbench URL for this optional integration check.')
  await forwardLocalApi(page, process.env.ATLAS_LIVE_API!)
  await page.goto('/?mode=workbench#/dataset/coco')
  const inspector = await inspectRecord(page, 'coco:example:c765b3eb380b785ef8fc414d')
  const artifactId = 'ed3d9c68da43ce9d7b593937'
  const artifact = await (await fetch(`${process.env.ATLAS_LIVE_API}/api/v1/artifacts/${artifactId}`)).json()
  await expect(inspector.locator(`.box-layer[data-run-id="${artifact.run_id}"] rect`)).toHaveCount(64) // 32 outlines plus 32 label plates, scoped to the frozen baseline run
  await expect(inspector.locator(`[data-artifact-id="${artifactId}"]`)).toContainText('Completed · 32 detections')
  await expect(inspector.locator('.overlay-note')).toHaveCount(0)
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
  await page.getByRole('group', { name: 'Population scope' }).getByRole('button', { name: 'Complete index' }).click()
  await expect(scopeLine(page)).toContainText('11,000 example records')
  await addFieldFilter(page, 'source.source_id', record.source.source_id)
  await expect(scopeLine(page)).toContainText('1 match')
  await expect(sampleCards(page)).toHaveCount(1)

  const inspector = await inspectRecord(page, id)
  const video = inspector.locator('video')
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
