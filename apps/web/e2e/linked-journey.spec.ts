import { expect, test, type Page } from '@playwright/test'
import { addFieldFilter, expectPanel, inspectRecord, scopeLine, selectionBar, switchView } from './helpers'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const recordId = 'coco:example:c765b3eb380b785ef8fc414d'
const imageId = 'coco:asset:7902a9a64c72d30f6de1cd9e'
const ids = { detector: 'ed3d9c68da43ce9d7b593937', nudenet: '9f3fd9518d29eecd47273581', embedding: '102efabba647db4f5066e95e', umap: '4c4e3ec224e69e6290e6edf3' }
const reportPath = fileURLToPath(new URL('../../../reports/browser-linked-journey.json', import.meta.url))

async function forwardLocalApi(page: Page, api: string) {
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url())
    const response = await fetch(`${api}${url.pathname}${url.search}`, { method: request.method(), headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1', ...(request.headers().range ? { Range: request.headers().range } : {}) }, body: request.method() === 'GET' ? undefined : request.postData() ?? undefined })
    await route.fulfill({ status: response.status, headers: { 'Content-Type': response.headers.get('content-type') ?? 'application/octet-stream' }, body: Buffer.from(await response.arrayBuffer()) })
  })
}

test('linked real COCO selection, named analysis, image conversation and exchange', async ({ page, browser }, testInfo) => {
  test.skip(!process.env.ATLAS_LINKED_JOURNEY || !process.env.ATLAS_LIVE_API, 'Set ATLAS_LINKED_JOURNEY=1 and ATLAS_LIVE_API to send one approved image to the configured local VLM.')
  test.setTimeout(240_000)
  const api = process.env.ATLAS_LIVE_API!
  const artifacts = await (await fetch(`${api}/api/v1/artifacts`)).json() as Array<{ id: string; run_id: string; kind: string; ids: string[]; snapshot_ids: string[] }>
  const named = Object.fromEntries(Object.entries(ids).map(([name, id]) => [name, artifacts.find(item => item.id === id)])) as Record<keyof typeof ids, (typeof artifacts)[number]>
  for (const artifact of Object.values(named)) { expect(artifact).toBeTruthy(); expect(artifact.ids).toContain(recordId) }
  expect(new Set(Object.values(named).flatMap(item => item.snapshot_ids)).size).toBe(1)
  await forwardLocalApi(page, api)
  await page.goto('/?mode=workbench#/dataset/coco')
  await expect(page.getByRole('heading', { name: 'COCO' })).toBeVisible()
  await addFieldFilter(page, 'source.person_count', '2')
  await expect(scopeLine(page)).toContainText('5 matches')
  await expect(page.getByRole('button', { name: `Inspect record ${recordId}` })).toBeVisible()
  const filteredCount = Number((await scopeLine(page).innerText()).match(/(\d+) matches/)?.[1])
  expect(filteredCount).toBeGreaterThan(0)
  await page.getByLabel(`Select record ${recordId}`).check()
  await page.getByLabel('Selection name').fill('COCO linked browser acceptance')
  const selectionPromise = page.waitForResponse(r => r.url().endsWith('/api/v1/selections') && r.request().method() === 'POST')
  await selectionBar(page).getByRole('button', { name: 'Save' }).click()
  const selectionHttp = await selectionPromise
  expect(selectionHttp.ok()).toBe(true)
  const selection = await selectionHttp.json() as { id: string; ids: string[]; snapshot_ids: string[] }
  expect(selection.ids).toEqual([recordId])
  expect(selection.snapshot_ids).toEqual(named.detector.snapshot_ids)
  await switchView(page, 'Map')
  await page.getByLabel('Projection').selectOption(ids.umap)
  const colorField = `prediction.${ids.detector}.person_count`
  await page.getByLabel('Colour by').selectOption(colorField)
  await expect(page.locator('.map-strip')).toContainText(`${filteredCount} plotted`)
  await switchView(page, 'Grid')
  const inspector = await inspectRecord(page, recordId)
  await expect(inspector.getByRole('status').filter({ hasText: 'detect.coco_v1' })).toContainText('Completed · 32 detections')
  await expect(inspector.getByRole('status').filter({ hasText: 'detect.nudenet' })).toContainText('Completed')
  await selectionBar(page).getByRole('button', { name: 'Ask model' }).click()
  const drawer = await expectPanel(page, 'Ask model')
  await drawer.getByLabel('Provider').selectOption('local-qwen2-5-vl-3b')
  const imageChoice = drawer.getByRole('checkbox', { name: `Include image asset ${imageId}` })
  await expect(imageChoice).toBeVisible()
  await imageChoice.check()
  const previewPromise = page.waitForResponse(r => r.url().endsWith('/api/v1/conversations/context') && r.request().method() === 'POST')
  await drawer.getByRole('button', { name: 'Review what will be sent' }).click()
  const previewHttp = await previewPromise
  expect(previewHttp.ok()).toBe(true)
  const preview = await previewHttp.json() as { context_digest: string; image_representations: Array<{ asset_id: string; sha256: string; bytes: number; mime_type: string }>; external_send_allowed: boolean; policy: { image_asset_ids: string[] }; outgoing: Array<{ content: Array<{ type: string; image_url?: { url: string } }> }> }
  expect(preview.external_send_allowed).toBe(true)
  expect(preview.policy.image_asset_ids).toEqual([imageId])
  expect(preview.image_representations[0].bytes).toBeGreaterThan(0)
  expect(preview.image_representations[0].sha256).toMatch(/^[a-f0-9]{64}$/)
  expect(preview.outgoing[0].content.find(item => item.type === 'image_url')?.image_url?.url).toMatch(/^data:image\/jpeg;base64,\S+/)
  await expect(drawer.getByText('Outgoing context', { exact: false })).toBeVisible()
  await drawer.getByLabel('Message').fill('Describe the selected image in one sentence.')
  const sendPromise = page.waitForResponse(r => r.url().endsWith('/api/v1/conversations') && r.request().method() === 'POST', { timeout: 150_000 })
  await drawer.getByRole('button', { name: 'Send to provider' }).click()
  const sendHttp = await sendPromise
  expect(sendHttp.ok()).toBe(true)
  const conversation = await sendHttp.json() as { id: string; error?: string | null; context_digest: string; record_ids: string[]; response?: string | null }
  expect(conversation.error).toBeFalsy()
  expect(conversation.record_ids).toEqual(selection.ids)
  expect(conversation.context_digest).toBe(preview.context_digest)
  const savedHttp = await fetch(`${api}/api/v1/conversations/${conversation.id}`)
  expect(savedHttp.ok).toBe(true)
  const saved = await savedHttp.json() as { provenance: { input_sent: typeof preview } }
  expect(saved.provenance.input_sent.image_representations[0].asset_id).toBe(imageId)
  expect(saved.provenance.input_sent.outgoing[0].content.find(item => item.type === 'image_url')?.image_url?.url).toMatch(/^data:image\/jpeg;base64,\S+/)
  const downloadPromise = page.waitForEvent('download')
  await selectionBar(page).getByRole('button', { name: 'Export' }).click()
  const download = await downloadPromise
  const exchangePath = testInfo.outputPath('coco-linked-selection.json')
  await download.saveAs(exchangePath)
  const exchange = JSON.parse(readFileSync(exchangePath, 'utf8')) as { checksum: string; selection: { ids: string[] } }
  expect(exchange.checksum).toMatch(/^[a-f0-9]{64}$/)
  expect(exchange.selection.ids).toEqual(selection.ids)
  await page.goto('/?mode=workbench#/collections')
  const importPromise = page.waitForResponse(r => r.url().endsWith('/api/v1/selections/import') && r.request().method() === 'POST')
  await page.getByLabel('Import exchange').setInputFiles(exchangePath)
  const importHttp = await importPromise
  expect(importHttp.ok()).toBe(true)
  const imported = await importHttp.json() as { id: string; ids: string[]; snapshot_ids: string[] }
  expect(imported.ids).toEqual(selection.ids)
  expect(imported.snapshot_ids).toEqual(selection.snapshot_ids)
  await expect(page.locator('.toasts')).toContainText('Imported 1 frozen example IDs')
  writeFileSync(reportPath, JSON.stringify({ tested_at: new Date().toISOString(), browser: `Chromium ${browser.version()}`, dataset_id: 'coco', source_filter: { field_id: 'source.person_count', op: 'eq', value: 2, matched_count: filteredCount }, record_id: recordId, selection_id: selection.id, snapshot_ids: selection.snapshot_ids, existing_artifacts: Object.fromEntries(Object.entries(named).map(([name, artifact]) => [name, { id: artifact.id, kind: artifact.kind, run_id: artifact.run_id, population_count: artifact.ids.length, includes_record: artifact.ids.includes(recordId) }])), map: { projection_artifact_id: ids.umap, color_field_id: colorField, plotted_count: filteredCount }, provider_id: 'local-qwen2-5-vl-3b', context_digest: preview.context_digest, conversation_id: conversation.id, image_proof: { asset_id: imageId, sha256: preview.image_representations[0].sha256, bytes: preview.image_representations[0].bytes, mime_type: preview.image_representations[0].mime_type, saved_input_contains_image_data_url: true }, response_error: conversation.error ?? null, response_text: conversation.response ?? null, exported_selection_checksum: exchange.checksum, imported_selection_id: imported.id, imported_ids_equal_export: JSON.stringify(imported.ids) === JSON.stringify(exchange.selection.ids), note: 'Existing 100-record analysis artifacts include the selected record; they were not recomputed. Image bytes and data URL are excluded from this receipt.' }, null, 2) + '\n')
})

test('browser re-exports and re-imports the saved linked COCO selection', async ({ page }, testInfo) => {
  test.skip(!process.env.ATLAS_LIVE_API || !process.env.ATLAS_REIMPORT_SELECTION_ID, 'Requires a saved local selection ID; no model request is made.')
  const api = process.env.ATLAS_LIVE_API!, id = process.env.ATLAS_REIMPORT_SELECTION_ID!
  await forwardLocalApi(page, api)
  await page.goto(`/?mode=workbench#/collections/${encodeURIComponent(id)}`)
  await expect(page.getByRole('heading', { name: 'COCO linked browser acceptance' })).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.locator('.toolbar').getByRole('button', { name: 'Export' }).click()
  const download = await downloadPromise
  const exchangePath = testInfo.outputPath('re-exported-coco-selection.json')
  await download.saveAs(exchangePath)
  const exchange = JSON.parse(readFileSync(exchangePath, 'utf8')) as { checksum: string; checksum_algorithm: string; selection: { id: string; ids: string[] } }
  expect(exchange.checksum_algorithm).toBe('atlas-values-v1')
  expect(exchange.selection.id).toBe(id)
  expect(exchange.selection.ids).toEqual([recordId])
  await page.goto('/?mode=workbench#/collections')
  const importPromise = page.waitForResponse(r => r.url().endsWith('/api/v1/selections/import') && r.request().method() === 'POST')
  await page.getByLabel('Import exchange').setInputFiles(exchangePath)
  const importedHttp = await importPromise
  expect(importedHttp.ok(), await importedHttp.text()).toBe(true)
  const imported = await importedHttp.json() as { id: string; ids: string[]; snapshot_ids: string[] }
  expect(imported.ids).toEqual(exchange.selection.ids)
  await expect(page.locator('.toasts')).toContainText('Imported 1 frozen example IDs')
  writeFileSync(testInfo.outputPath('browser-exchange-retry.json'), JSON.stringify({ selection_id: id, checksum_algorithm: exchange.checksum_algorithm, checksum: exchange.checksum, imported_selection_id: imported.id, imported_ids: imported.ids, snapshot_ids: imported.snapshot_ids }, null, 2) + '\n')
})
