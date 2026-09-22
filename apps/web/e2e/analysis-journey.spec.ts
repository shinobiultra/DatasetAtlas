import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expectPanel, inspectRecord, sampleCards, selectionBar } from './helpers'

test('Analyze estimates and runs real detector and image embeddings, then refreshes inspection', async ({ page }) => {
  test.skip(!process.env.ATLAS_ANALYSIS_JOURNEY || !process.env.ATLAS_LIVE_API, 'Requires prepared local model recipes and explicit real analysis opt-in.')
  test.setTimeout(240_000)
  const api = process.env.ATLAS_LIVE_API!
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), url = new URL(req.url())
    const res = await fetch(`${api}${url.pathname}${url.search}`, { method: req.method(), headers: { 'Content-Type': 'application/json', 'X-Atlas-Request': '1' }, body: req.method() === 'GET' ? undefined : req.postData() ?? undefined })
    await route.fulfill({ status: res.status, contentType: res.headers.get('content-type') ?? 'application/json', body: Buffer.from(await res.arrayBuffer()) })
  })
  await page.goto('/?mode=workbench#/dataset/coco')
  await expect(sampleCards(page).first()).toBeVisible()
  const recordId = (await sampleCards(page).first().getAttribute('data-record-id'))!
  await page.getByLabel(`Select record ${recordId}`).check()
  await selectionBar(page).getByRole('button', { name: 'Analyze', exact: true }).click()
  const panel = await expectPanel(page, 'Analysis')
  const runs = []
  for (const processor of ['detect.coco_v1', 'embed.siglip2']) {
    await panel.getByLabel('Analysis', { exact: true }).selectOption(processor)
    const estimateResponse = page.waitForResponse(r => r.url().endsWith('/runs/estimate'))
    await panel.getByRole('button', { name: 'Estimate resources and coverage' }).click()
    expect((await estimateResponse).ok()).toBe(true)
    await expect(panel.getByRole('button', { name: 'Run analysis', exact: true })).toBeEnabled()
    const started = page.waitForResponse(r => r.url().endsWith('/runs') && r.request().method() === 'POST')
    await panel.getByRole('button', { name: 'Run analysis', exact: true }).click()
    const response = await started
    expect(response.ok(), await response.text()).toBe(true)
    const initial = await response.json()
    let finished = initial
    await expect.poll(async () => {
      finished = await (await fetch(`${api}/api/v1/runs/${initial.id}`)).json()
      return finished.status
    }, { timeout: 150_000, intervals: [500, 1000, 2000] }).toBe('completed')
    expect(finished.artifact_ids.length).toBeGreaterThan(0)
    const artifact = await (await fetch(`${api}/api/v1/artifacts/${finished.artifact_ids[0]}`)).json()
    expect(artifact.ids).toEqual([recordId])
    expect(artifact.coverage.completed).toBe(1)
    runs.push({ run_id: finished.id, processor_id: processor, artifact_id: artifact.id, coverage: artifact.coverage, record_id: recordId })
  }
  await page.getByRole('button', { name: 'Close panel', exact: true }).click()
  await page.getByRole('button', { name: 'Refresh results', exact: true }).click()
  await expect(page.locator('.toasts')).toContainText('Results refreshed')
  const inspector = await inspectRecord(page, recordId)
  await expect(inspector.locator(`[data-artifact-id="${runs[0].artifact_id}"]`)).toContainText('Completed')
  await expect.poll(async () => (await page.request.get(`${api}/api/v1/datasets/coco/fields`)).json().then(fields => fields.some((f: { id: string }) => f.id.startsWith(`prediction.${runs[0].artifact_id}.`)))).toBe(true)
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-analysis-journey.json', import.meta.url)), JSON.stringify({ tested_at: new Date().toISOString(), scope: 'Real one-record analysis submitted from the rebuilt Analyze panel; results explicitly refreshed without a page reload.', runs }, null, 2) + '\n')
})
