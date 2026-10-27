import { expect, test, type Page } from '@playwright/test'
import { stubCommonRoutes } from './helpers'

const ID = 'synthetic-remote-resampling'
const SNAPSHOT = 'synthetic-retained-sample'

async function fixture(page: Page, firstPlanReady?: Promise<void>) {
  const dataset = {
    id: ID, name: 'Synthetic huge native mixture', adapter: 'remote_columnar', snapshot_id: SNAPSHOT,
    coverage: { preview_count: 1, unit: 'example', complete_data: 'exceeds_storage_budget' },
    evidence: [{ kind: 'sampled_native_preview', sampling: { seed: 11 } }],
  }
  const row = { id: `${ID}:example:1`, dataset_id: ID, snapshot_id: SNAPSHOT, unit: 'example',
    text: 'Synthetic retained preview', assets: [], source: {} }
  const plans: Record<string, unknown>[] = []
  let starts = 0
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname.replace('/api/v1', '')
    const common = stubCommonRoutes(path, ID)
    if (common !== undefined) return route.fulfill({ json: common })
    if (path === '/capabilities') return route.fulfill({ json: { mode: 'workbench', operations: ['catalogue', 'query', 'selection'], api_version: '1' } })
    if (path === '/datasets') return route.fulfill({ json: [dataset] })
    if (path === `/datasets/${ID}`) return route.fulfill({ json: dataset })
    if (path === `/datasets/${ID}/fields` || path === '/artifacts') return route.fulfill({ json: [] })
    if (path === `/datasets/${ID}/pack`) return route.fulfill({ json: { dataset, records: [row], fields: [],
      sampling: { method: 'sha256_counter_two_stage_row_groups', seed: 11, population_count: 100_000 } } })
    if (path === `/queries/${ID}`) return route.fulfill({ json: { snapshot_id: SNAPSHOT, unit: 'example', population_scope: 'preview',
      records: [row], matched_count: 1, returned_count: 1, count_status: 'exact', cursor: null } })
    if (path === `/datasets/${ID}/preparation/plan`) {
      const body = request.postDataJSON()
      plans.push(body)
      if (plans.length === 1) await firstPlanReady
      return route.fulfill({ json: { id: 'synthetic-new-plan', ready: true, scope: 'All synthetic native configurations',
        kind: 'huggingface_remote_sample', sample: { size: 100, seed: body.sample_seed },
        source_identity: 'Pinned synthetic release', source_total_bytes: 4_000_000_000_000,
        expected_download_bytes: body.max_download_bytes, download_is_upper_bound: true,
        available_bytes: 8_000_000_000, required_free_bytes: body.max_output_bytes + 200_000_000,
        requirements: [], files: [] } })
    }
    if (path === '/preparation/synthetic-new-plan/start') {
      starts += 1
      return route.fulfill({ json: { id: 'synthetic-new-plan', status: 'queued' } })
    }
    if (path === '/preparation/synthetic-new-plan') return route.fulfill({ json: { id: 'synthetic-new-plan', status: 'running' } })
    throw new Error(`Unexpected synthetic resampling API ${path}`)
  })
  await page.goto(`/?mode=workbench#/dataset/${ID}`)
  return { plans, starts: () => starts }
}

test('another remote sample freezes a new seed and reviewed budgets before execution', async ({ page }) => {
  const state = await fixture(page)
  await page.getByRole('button', { name: 'Get another sample', exact: true }).click()
  await expect(page.getByLabel('Source access')).toHaveValue('sample')
  await expect(page.getByLabel('Sample seed')).toHaveValue(/^\d+$/)
  await page.getByLabel('Sample seed').fill('73')
  await page.getByLabel('Download limit (GB)').fill('0.05')
  await page.getByLabel('Prepared data limit (GB)').fill('0.04')
  expect(state.starts()).toBe(0)
  await expect(page.getByRole('button', { name: 'Fetch another sample', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Review preparation plan', exact: true }).click()
  await expect(page.getByText('100 rows · sample seed 73', { exact: true })).toBeVisible()
  expect(state.plans).toEqual([{ source_mode: 'sample', sample_seed: 73, max_download_bytes: 50_000_000, max_output_bytes: 40_000_000 }])
  expect(state.starts()).toBe(0)
  await page.getByLabel('Download limit (GB)').fill('0.06')
  await expect(page.getByRole('button', { name: 'Fetch another sample', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Review preparation plan', exact: true }).click()
  await page.getByRole('button', { name: 'Fetch another sample', exact: true }).click()
  await expect.poll(() => state.starts()).toBe(1)
  expect(state.plans[1].max_download_bytes).toBe(60_000_000)
})

test('invalid sample seed cannot submit a remote preparation plan', async ({ page }) => {
  const state = await fixture(page)
  await page.getByRole('button', { name: 'Get another sample', exact: true }).click()
  await page.getByLabel('Sample seed').fill('1.5')
  await page.getByRole('button', { name: 'Review preparation plan', exact: true }).click()
  await expect(page.getByText(/Sample seed must be a whole number/)).toBeVisible()
  expect(state.plans).toHaveLength(0)
  expect(state.starts()).toBe(0)
})

test('changing seed while a source plan loads discards the previous plan', async ({ page }) => {
  let release: (() => void) | undefined
  const held = new Promise<void>(resolve => { release = resolve })
  const state = await fixture(page, held)
  await page.getByRole('button', { name: 'Get another sample', exact: true }).click()
  await page.getByLabel('Sample seed').fill('73')
  await page.getByRole('button', { name: 'Review preparation plan', exact: true }).click()
  await expect.poll(() => state.plans.length).toBe(1)
  await page.getByLabel('Sample seed').fill('74')
  release!()
  await expect(page.getByRole('button', { name: 'Review preparation plan', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Fetch another sample', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Review preparation plan', exact: true }).click()
  await expect(page.getByText('100 rows · sample seed 74', { exact: true })).toBeVisible()
  expect(state.starts()).toBe(0)
})
