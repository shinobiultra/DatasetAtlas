import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { addFieldFilter, expectPanel, inspectRecord, pointToLiveWorkbench, scopeLine, selectionBar, switchView } from './helpers'

test.use({ actionTimeout: 15_000 })

test('current real analyses support linked filtering, projection, local image conversation and exchange', async ({ page, browser }, testInfo) => {
  test.skip(!process.env.ATLAS_RUNTIME_JOURNEY || !process.env.ATLAS_LIVE_API, 'Requires real processor receipts and an explicitly enabled local model journey.')
  test.setTimeout(240_000)
  const api = process.env.ATLAS_LIVE_API!
  const runtime = JSON.parse(readFileSync(fileURLToPath(new URL('../../../reports/analysis-runtime-complete-20261006.json', import.meta.url)), 'utf8'))
  expect(runtime.completed).toBe(true)
  const ids = Object.fromEntries(Object.entries(runtime.runs as Record<string, { artifact_ids: string[] }>).map(([key, run]) => [key, run.artifact_ids[0]]))
  const artifact = await (await fetch(`${api}/api/v1/artifacts/${ids['outlier.knn']}`)).json()
  const unusual = [...artifact.data.items].sort((a, b) => b.output.outlier_score - a.output.outlier_score)[0]
  const pack = await (await fetch(`${api}/api/v1/datasets/clevr/pack`)).json()
  const record = pack.records.find((item: { id: string }) => item.id === unusual.id)
  expect(record).toBeTruthy()
  const projectionUrl = `${api}/api/v1/artifacts/${ids['project.umap']}`
  const projection = await (await fetch(projectionUrl)).json()
  const projectionHash = createHash('sha256').update(JSON.stringify(projection)).digest('hex')
  expect(projection.ids).toHaveLength(16)
  await pointToLiveWorkbench(page, api)
  await page.goto('/?mode=workbench#/dataset/clevr')
  await expect(page.locator('.sample-card').first()).toBeVisible()
  await page.getByRole('button', { name: 'Results for browsing' }).click()
  for (const id of Object.values(ids)) await page.getByLabel(`Use result ${id}`, { exact: true }).check()
  await page.keyboard.press('Escape')
  await addFieldFilter(page, 'source.image_index', String(record.source.image_index))
  await expect(scopeLine(page)).toContainText('1 match')
  await page.getByLabel(`Select record ${record.id}`).check()
  await page.getByLabel('Selection name').fill('Current local analysis linked acceptance')
  const savedResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/selections') && r.request().method() === 'POST')
  await selectionBar(page).getByRole('button', { name: 'Save', exact: true }).click()
  const saved = await (await savedResponse).json()
  expect(saved.ids).toEqual([record.id])
  expect(saved.query.result_snapshot_ids).toEqual(expect.arrayContaining(Object.values(ids)))
  await switchView(page, 'Map')
  await page.getByLabel('Projection', { exact: true }).selectOption(ids['project.umap'])
  const colourField = `prediction.${ids['detect.coco_v1']}.person_count`
  await page.getByLabel('Colour by').selectOption(colourField)
  await expect(page.locator('.map-strip')).toContainText('1 plotted')
  await page.getByRole('complementary', { name: 'Sample filters' }).getByRole('button', { name: 'Reset', exact: true }).click()
  await expect(page.locator('.map-strip')).toContainText('16 plotted')
  expect(createHash('sha256').update(JSON.stringify(await (await fetch(projectionUrl)).json())).digest('hex')).toBe(projectionHash)
  await switchView(page, 'Grid')
  const inspector = await inspectRecord(page, record.id)
  for (const processor of ['detect.coco_v1', 'detect.nudenet']) {
    await expect(inspector.locator(`[data-artifact-id="${ids[processor]}"]`)).toContainText('Completed')
  }
  await inspector.getByRole('tab', { name: 'Model outputs', exact: true }).click()
  await expect(inspector.locator(`[data-field-id="prediction.${ids['outlier.knn']}.status"]`)).toContainText('completed')
  await expect(inspector.locator(`[data-field-id="prediction.${ids['outlier.knn']}.outlier_score"]`)).toBeVisible()
  await selectionBar(page).getByRole('button', { name: 'Ask model', exact: true }).click()
  const drawer = await expectPanel(page, 'Ask model')
  await drawer.getByLabel('Provider').selectOption('local-ollama-qwen35')
  await drawer.getByRole('checkbox', { name: `Include image asset ${record.assets[0].id}` }).check()
  const contextResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/conversations/context') && r.request().method() === 'POST')
  await drawer.getByRole('button', { name: 'Review what will be sent' }).click()
  const contextHttp = await contextResponse; expect(contextHttp.ok()).toBe(true)
  const context = await contextHttp.json()
  expect(context.image_representations).toHaveLength(1)
  expect(context.image_representations[0].sha256).toMatch(/^[a-f0-9]{64}$/)
  await drawer.getByLabel('Message').fill('Describe only the visible shapes and colours in this image in one sentence. Do not infer any population statistics.')
  const conversationResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/conversation-jobs') && r.request().method() === 'POST', { timeout: 150_000 })
  await drawer.getByRole('button', { name: 'Send to provider' }).click()
  const conversationHttp = await conversationResponse; expect(conversationHttp.ok()).toBe(true)
  const job = await conversationHttp.json()
  let completedJob: { status?: string; result?: any; error?: string } = {}
  await expect.poll(async () => {
    completedJob = await (await fetch(`${api}/api/v1/conversation-jobs/${job.id}`)).json()
    return ['completed', 'failed', 'cancelled', 'interrupted'].includes(completedJob.status ?? '')
  }, { timeout: 150_000 }).toBe(true)
  expect(completedJob.status).toBe('completed')
  const conversation = completedJob.result
  expect(conversation.error).toBeFalsy(); expect(conversation.response?.length).toBeGreaterThan(0)
  expect(conversation.context_digest).toBe(context.context_digest)
  const retained = await (await fetch(`${api}/api/v1/conversations/${conversation.id}`)).json()
  expect(retained.provenance.input_sent.image_representations[0].sha256).toBe(context.image_representations[0].sha256)
  const downloaded = page.waitForEvent('download')
  await selectionBar(page).getByRole('button', { name: 'Export', exact: true }).click()
  const path = testInfo.outputPath('current-analysis-selection.json'); await (await downloaded).saveAs(path)
  const exchange = JSON.parse(readFileSync(path, 'utf8'))
  expect(exchange.records[0].prediction).not.toEqual({})
  expect(exchange.selection.query.result_snapshot_ids).toEqual(expect.arrayContaining(Object.values(ids)))
  await page.goto('/?mode=workbench#/collections')
  const importResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/selections/import') && r.request().method() === 'POST')
  await page.getByLabel('Import exchange').setInputFiles(path)
  const importedHttp = await importResponse; expect(importedHttp.ok()).toBe(true)
  const imported = await importedHttp.json(); expect(imported.ids).toEqual(saved.ids)
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-runtime-linked-journey-20261007.json', import.meta.url)), JSON.stringify({
    verified_at_utc: new Date().toISOString(), status: 'passed', browser: `Chromium ${browser.version()}`,
    dataset_id: 'clevr', source_snapshot_ids: runtime.snapshot_ids, parent_analysis_selection: runtime.selection_id,
    inspected_record_id: record.id, frozen_selection_id: saved.id, artifacts: ids,
    source_filter: 'source.image_index', filtered_matches: 1, projection_before_filter_points: 16, projection_filtered_points: 1,
    projection_reexpanded_points: 16, projection_sha256_unchanged: projectionHash, colour_field: colourField,
    provider_id: 'local-ollama-qwen35', external_model_requests: 0, conversation_id: conversation.id, context_digest: context.context_digest,
    original_image_context_sha256: context.image_representations[0].sha256,
    response_sha256: createHash('sha256').update(conversation.response).digest('hex'), response_characters: conversation.response.length,
    exported_checksum: exchange.checksum, imported_selection_id: imported.id, prediction_columns_retained: true,
    scope: 'Real local functional journey; outlier rank selects an inspection example and does not establish scientific validity or population prevalence.',
  }, null, 2) + '\n')
})
