import { expect, test } from '@playwright/test'
import { expectPanel, sampleCards, selectionBar, stubCommonRoutes } from './helpers'

const id = 'synthetic-feature-controls', snapshot = 'fixture-snapshot'
const record = { id: 'fixture-row', dataset_id: id, release_id: 'fixture', snapshot_id: snapshot, unit: 'example', text: 'Synthetic engineering fixture', assets: [], source: { score: 1 } }
const dataset = { id, name: 'Synthetic feature controls', release: 'fixture', snapshot_id: snapshot, coverage: { preview_count: 1, unit: 'example' } }

test('context review binds fields and tools, async polling retries and cancellation stays available', async ({ page }) => {
  let approved: any, sent: any, cancelled = false, polls = 0
  await page.route('**/api/v1/**', route => {
    const request = route.request(), path = new URL(request.url()).pathname.replace('/api/v1', '')
    if (path === '/providers') return route.fulfill({ json: [{ config: { id: 'fixture-local', model: 'Synthetic provider', base_url: 'http://127.0.0.1:1234/v1', timeout_seconds: 60 }, capabilities: { tool_calls: { status: 'supported' } } }] })
    if (path === '/conversations' || path === '/conversation-jobs' && request.method() === 'GET') return route.fulfill({ json: [] })
    if (path === '/records') return route.fulfill({ json: [record] })
    if (path === '/conversations/context') {
      approved = request.postDataJSON()
      return route.fulfill({ json: { context_digest: 'fixture-approved-context', external_send_allowed: true, request: approved } })
    }
    if (path === '/conversation-jobs' && request.method() === 'POST') {
      sent = request.postDataJSON()
      return route.fulfill({ json: { id: 'conversation-job:fixture', status: 'running', progress: { phase: 'awaiting_provider' } } })
    }
    if (path.startsWith('/conversation-jobs/') && path.endsWith('/cancel')) {
      cancelled = true
      return route.fulfill({ json: { id: 'conversation-job:fixture', status: 'cancelling' } })
    }
    if (path.startsWith('/conversation-jobs/')) {
      polls++
      if (polls === 1) return route.fulfill({ status: 503, json: { detail: 'Synthetic transient status failure' } })
      return route.fulfill({ json: { id: 'conversation-job:fixture', status: cancelled ? 'cancelled' : 'running', progress: { phase: 'awaiting_provider' }, result: cancelled ? { status: 'cancelled', outgoing_receipt_retained: true } : undefined } })
    }
    const common = stubCommonRoutes(path, id)
    if (common !== undefined) return route.fulfill({ json: common })
    if (path === '/capabilities') return route.fulfill({ json: { mode: 'workbench', operations: ['catalogue', 'query', 'providers', 'conversation-jobs'] } })
    if (path === '/datasets') return route.fulfill({ json: [dataset] })
    if (path === `/datasets/${id}`) return route.fulfill({ json: dataset })
    if (path === '/artifacts') return route.fulfill({ json: [] })
    if (path === `/datasets/${id}/fields`) return route.fulfill({ json: [{ id: 'source.score', name: 'score', namespace: 'source', dtype: 'number', unit: 'example', operations: ['eq'] }] })
    if (path === `/queries/${id}`) return route.fulfill({ json: { records: [record], matched_count: 1, returned_count: 1, count_status: 'exact', population_scope: 'preview', unit: 'example' } })
    throw new Error(`Unexpected synthetic request ${path}`)
  })
  await page.goto(`/?mode=workbench#/dataset/${id}`)
  await expect(sampleCards(page).first()).toBeVisible()
  await page.getByLabel('Select record fixture-row').check()
  await selectionBar(page).getByRole('button', { name: 'Ask model', exact: true }).click()
  const panel = await expectPanel(page, 'Ask model')
  await panel.getByLabel('Provider', { exact: true }).selectOption('fixture-local')
  await panel.getByLabel('Message', { exact: true }).fill('Synthetic request')
  await panel.getByRole('button', { name: 'Review what will be sent' }).click()
  await expect(panel.getByRole('button', { name: 'Send to provider' })).toBeEnabled()
  await panel.getByLabel('score · source', { exact: true }).first().check()
  await expect(panel.getByRole('button', { name: 'Send to provider' })).toBeDisabled()
  await panel.getByLabel('Allow bounded read-only exploration tools').check()
  await panel.getByLabel('Tool-call limit').fill('2')
  await panel.getByRole('button', { name: 'Review what will be sent' }).click()
  expect(approved.fields).toEqual(['source.score'])
  expect(approved.snapshot_ids).toEqual([snapshot])
  await panel.getByRole('button', { name: 'Send to provider' }).click()
  expect(sent.context_digest).toBe('fixture-approved-context')
  expect(sent.use_tools).toBe(true)
  expect(sent.max_tool_calls).toBe(2)
  await expect(panel.getByText(/Request status temporarily unavailable/)).toBeVisible()
  await expect(panel.getByRole('button', { name: 'Cancel model request' })).toBeEnabled()
  await panel.getByRole('button', { name: 'Cancel model request' }).click()
  await expect(panel.getByText(/outgoing_receipt_retained/)).toBeVisible()
  await expect(panel.getByRole('button', { name: 'Review what will be sent' })).toBeEnabled()
  expect(cancelled).toBe(true)
})
