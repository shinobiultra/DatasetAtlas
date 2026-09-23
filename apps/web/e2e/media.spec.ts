import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { inspectRecord, sampleCards, stubCommonRoutes } from './helpers'

const ID = 'synthetic-media-contract'
const SNAPSHOT = 'test-only-media-snapshot'
const names = ['geometry', 'mismatch', 'missing', 'failed', 'zero', 'broken', 'absent', 'variants'] as const
const assetId = (name: string) => `synthetic:asset:${name}`
const recordId = (name: string) => `synthetic:example:${name}`
const fixture = readFileSync(fileURLToPath(new URL('./fixtures/orientation-6.jpg', import.meta.url)))
const records = names.map(name => ({
  id: recordId(name), dataset_id: ID, release_id: 'test-only', snapshot_id: SNAPSHOT, unit: 'example',
  text: `Synthetic ${name} image`, source: { test_case: name },
  asset_ids: [assetId(name)],
  assets: name === 'variants'
    ? ['ref', 'p0', 'p1'].map(role => ({ id: assetId(name) + role, dataset_id: ID, release_id: 'test-only', modality: 'image', representation: 'original', uri: '/test-media/orientation-6.jpg', metadata: { source_role: role, question: `Synthetic question for ${role}` } }))
    : [{ id: assetId(name), dataset_id: ID, release_id: 'test-only', modality: 'image', representation: 'original', uri: name === 'absent' ? null : `/test-media/${name === 'broken' ? 'missing.png' : 'orientation-6.jpg'}`, metadata: name === 'absent' ? { availability: 'absent_from_pinned_release', source_path: 'native/missing.jpg' } : {} }],
}))
const assetOutput = (name: string, width = 40, height = 80, detections: unknown[] = []) => ({ asset_id: assetId(name), status: 'completed', width, height, detections })
const artifact = {
  id: 'synthetic-detector', kind: 'detect.test', run_id: 'test-only-detector', unit: 'example',
  snapshot_ids: [SNAPSHOT], ids: records.map(record => record.id),
  provenance: { processor_provenance: { input_representation: 'local original image, EXIF-transposed RGB', box_coordinates: 'xyxy pixels in EXIF-transposed image', extraction_threshold: 0.5 } },
  data: { items: [
    { id: recordId('geometry'), status: 'completed', output: { assets: [assetOutput('geometry', 40, 80, [{ class: 'marker', score: 0.9, box: [19, 10, 35, 31] }])] } },
    { id: recordId('mismatch'), status: 'completed', output: { assets: [assetOutput('mismatch', 80, 40, [{ class: 'wrong space', score: 0.9, box: [10, 5, 30, 20] }])] } },
    { id: recordId('failed'), status: 'failed', error: 'Synthetic detector failure', output: { assets: [{ asset_id: assetId('failed'), status: 'failed', error: 'Synthetic detector failure' }] } },
    { id: recordId('zero'), status: 'completed', output: { assets: [assetOutput('zero')] } },
    { id: recordId('broken'), status: 'completed', output: { assets: [assetOutput('broken', 40, 80, [{ class: 'marker', score: 0.9, box: [19, 10, 35, 31] }])] } },
  ] },
}
const dataset = { id: ID, name: 'Synthetic media contract fixture', release: 'test-only', snapshot_id: SNAPSHOT, coverage: { preview_count: records.length, unit: 'example', complete_data: 'unimplemented' } }

async function setup(page: Page) {
  await page.route('**/test-media/**', route => route.request().url().endsWith('/missing.png') ? route.fulfill({ status: 404, body: 'missing test image' }) : route.fulfill({ contentType: 'image/jpeg', body: fixture }))
  await page.route('**/api/v1/**', route => {
    const url = new URL(route.request().url()), path = url.pathname.replace('/api/v1', '')
    const common = stubCommonRoutes(path, ID)
    if (common !== undefined) return route.fulfill({ json: common })
    let body: unknown
    if (path === '/capabilities') body = { mode: 'workbench', operations: ['catalogue', 'query', 'artifacts'] }
    else if (path === '/datasets') body = [dataset]
    else if (path === `/datasets/${ID}`) body = dataset
    else if (path === `/datasets/${ID}/fields`) body = []
    else if (path === '/artifacts') body = [artifact]
    else if (path === `/queries/${ID}`) body = { snapshot_id: SNAPSHOT, unit: 'example', population_scope: 'preview', records, returned_count: records.length, matched_count: records.length, count_status: 'exact', cursor: null }
    else throw new Error(`Unexpected test API request: ${path}`)
    return route.fulfill({ json: body })
  })
  await page.goto(`/?mode=workbench#/dataset/${ID}`)
  await expect(sampleCards(page)).toHaveCount(records.length)
}

test('EXIF-oriented pixel boxes align through browser resize and object-fit letterboxing', async ({ page }, testInfo) => {
  await setup(page)
  const inspector = await inspectRecord(page, recordId('geometry'))
  const image = inspector.getByRole('img', { name: `Primary asset of ${recordId('geometry')}` })
  await expect(image).toHaveJSProperty('naturalWidth', 40)
  await expect(image).toHaveJSProperty('naturalHeight', 80)
  // Two rects per detection: the outline and the plate its label sits on.
  await expect(inspector.locator('.box-layer rect')).toHaveCount(2)

  async function geometry() {
    return inspector.locator('.insp-media').evaluate(item => {
      const image = item.querySelector('img')!, svg = item.querySelector('svg')!, box = svg.querySelector('rect')!
      const imageBounds = image.getBoundingClientRect(), overlayBounds = svg.getBoundingClientRect(), itemBounds = item.getBoundingClientRect()
      const scale = Math.min(imageBounds.width / image.naturalWidth, imageBounds.height / image.naturalHeight)
      const left = imageBounds.left + (imageBounds.width - image.naturalWidth * scale) / 2
      const top = imageBounds.top + (imageBounds.height - image.naturalHeight * scale) / 2
      const matrix = box.getScreenCTM()!
      const a = new DOMPoint(19, 10).matrixTransform(matrix), b = new DOMPoint(35, 31).matrixTransform(matrix)
      const check = [Math.abs(a.x - (left + 19 * scale)), Math.abs(a.y - (top + 10 * scale)), Math.abs(b.x - (left + 35 * scale)), Math.abs(b.y - (top + 31 * scale))]
      const sample = document.createElement('canvas'); sample.width = 40; sample.height = 80
      const context = sample.getContext('2d')!; context.drawImage(image, 0, 0)
      const landmark = Array.from(context.getImageData(25, 15, 1, 1).data)
      return { imageWidth: image.naturalWidth, imageHeight: image.naturalHeight, horizontalLetterbox: (imageBounds.width - image.naturalWidth * scale) / 2, overlayWidthError: Math.abs(overlayBounds.width - itemBounds.width), maxBoxError: Math.max(...check), landmark }
    })
  }
  const original = await geometry()
  expect(original.horizontalLetterbox).toBeGreaterThan(20)
  expect(original.overlayWidthError).toBeLessThan(1)
  expect(original.maxBoxError).toBeLessThan(1)
  expect(original.landmark[0]).toBeGreaterThan(original.landmark[1] * 1.5)
  await inspector.locator('.insp-media').evaluate(element => { (element as HTMLElement).style.height = '120px' })
  const resized = await geometry()
  expect(resized.horizontalLetterbox).toBeGreaterThan(original.horizontalLetterbox)
  expect(resized.maxBoxError).toBeLessThan(1)
  await inspector.locator('.insp-media').screenshot({ path: testInfo.outputPath('exif-overlay-resized.png') })

  await inspectRecord(page, recordId('mismatch'))
  await expect(inspector.getByText(/Overlay hidden: 80×40 detector input differs/)).toBeVisible()
  await expect(inspector.locator('.box-layer')).toHaveCount(0)
})

test('missing, failed, zero-detection, and broken-image states stay distinct', async ({ page }) => {
  await setup(page)
  const inspector = await inspectRecord(page, recordId('missing'))
  await expect(inspector.getByRole('status')).toContainText('Not computed for this record')
  await expect(inspector.locator('.box-layer')).toHaveCount(0)

  await inspectRecord(page, recordId('failed'))
  await expect(inspector.getByRole('status')).toContainText('failed result')
  await expect(inspector.getByRole('status')).toContainText('Synthetic detector failure')
  await expect(inspector.locator('.box-layer')).toHaveCount(0)

  await inspectRecord(page, recordId('zero'))
  await expect(inspector.getByRole('status')).toContainText('Completed · no detections found')
  await expect(inspector.locator('.box-layer rect')).toHaveCount(0)

  await inspectRecord(page, recordId('broken'))
  await expect(inspector.getByText('Media could not be loaded')).toBeVisible()
  await expect(inspector.locator('.insp-media img')).toHaveCount(0)
  await expect(inspector.locator('.box-layer')).toHaveCount(0)
})

test('the extraction threshold is stated beside the boxes it produced', async ({ page }) => {
  await setup(page)
  const inspector = await inspectRecord(page, recordId('geometry'))
  await expect(inspector.getByRole('status')).toContainText('Completed · 1 detection')
  await expect(inspector.getByRole('status')).toContainText('Extraction threshold 0.5')
})


test('source-listed absent images remain explicit without a broken media request', async ({ page }) => {
  const requested: string[] = []
  page.on('request', request => { if (request.url().includes('native/missing')) requested.push(request.url()) })
  await setup(page)
  const inspector = await inspectRecord(page, recordId('absent'))
  await expect(inspector.getByText('Listed by the source, absent from this release')).toBeVisible()
  await expect(inspector.getByText('native/missing.jpg', { exact: true })).toBeVisible()
  await expect(inspector.getByText('Unavailable in source release')).toBeVisible()
  expect(requested).toEqual([])
})

test('focused inspection names native image roles and shows the selected image question', async ({ page }) => {
  await setup(page)
  const inspector = await inspectRecord(page, recordId('variants'))
  await expect(inspector.getByText('Reference', { exact: true })).toBeVisible()
  await inspector.getByRole('button', { name: 'Open', exact: true }).click()
  const select = page.getByLabel('Choose image in this record')
  await expect(select.locator('option')).toHaveText(['Reference · 1 of 3', 'Patch 0 · 2 of 3', 'Patch 1 · 3 of 3'])
  await select.selectOption('2')
  await expect(page.getByLabel('Question for selected image')).toContainText('Synthetic question for p1')
  await expect(page.getByLabel('Question for selected image')).not.toContainText('Synthetic question for ref')
})
