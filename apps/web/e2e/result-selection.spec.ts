import { expect, test } from '@playwright/test'
import { addFieldFilter, sampleCards, scopeLine, stubCommonRoutes } from './helpers'

test('many historical runs do not break browsing and an older result remains selectable', async ({ page }) => {
  const id = 'synthetic-result-history', snapshot = 'test-snapshot'
  const dataset = { id, name: 'Synthetic result history', snapshot_id: snapshot, coverage: { preview_count: 1, unit: 'example' } }
  const artifacts = Array.from({ length: 40 }, (_, index) => ({
    id: `run-${index}`, kind: 'classify.test', unit: 'example', snapshot_ids: [snapshot], ids: ['test-row'], data: {},
  }))
  const queries: Array<{ result_snapshot_ids: string[]; filter: unknown }> = []
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    const common = stubCommonRoutes(path, id)
    if (common !== undefined) return route.fulfill({ json: common })
    if (path === '/capabilities') return route.fulfill({ json: { mode: 'workbench', operations: ['catalogue', 'query'] } })
    if (path === '/datasets') return route.fulfill({ json: [dataset] })
    if (path === `/datasets/${id}`) return route.fulfill({ json: dataset })
    if (path === '/artifacts') return route.fulfill({ json: artifacts })
    if (path === `/datasets/${id}/fields`) return route.fulfill({ json: artifacts.map(item => ({ id: `prediction.${item.id}.score`, name: item.id, namespace: 'prediction', unit: 'example', dtype: 'number', operations: ['eq'] })) })
    if (path === `/queries/${id}`) {
      const query = route.request().postDataJSON()
      queries.push(query)
      if (query.result_snapshot_ids.length > 32) return route.fulfill({ status: 422, json: { detail: 'Too many runs' } })
      return route.fulfill({ json: { records: [{ id: 'test-row', dataset_id: id, snapshot_id: snapshot, text: 'Test record', assets: [] }], matched_count: 1, returned_count: 1, count_status: 'exact', population_scope: 'preview', unit: 'example' } })
    }
    throw new Error(`Unexpected test request ${path}`)
  })
  await page.goto(`/?mode=workbench#/dataset/${id}`)
  await expect(sampleCards(page).first()).toBeVisible()
  expect(queries.at(-1)?.result_snapshot_ids).toEqual([])
  await page.getByRole('button', { name: 'Results for browsing' }).click()
  await page.getByLabel('Use result run-0', { exact: true }).check()
  await page.keyboard.press('Escape')
  await expect.poll(() => queries.at(-1)?.result_snapshot_ids).toEqual(['run-0'])
  await addFieldFilter(page, 'prediction.run-0.score', '1')
  await expect.poll(() => queries.at(-1)?.filter).toEqual({ field_id: 'prediction.run-0.score', op: 'eq', value: 1 })
  await page.getByRole('button', { name: 'Results for browsing' }).click()
  await page.getByLabel('Use result run-0', { exact: true }).uncheck()
  for (let i = 1; i <= 32; i++) await page.getByLabel(`Use result run-${i}`, { exact: true }).check()
  await expect(page.getByLabel('Use result run-39', { exact: true })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect.poll(() => queries.at(-1)?.result_snapshot_ids.length).toBe(32)
  expect(queries.at(-1)?.filter).toBeNull()
  expect(queries.every(query => query.result_snapshot_ids.length <= 32)).toBe(true)
  await expect(scopeLine(page)).toContainText('1 match')
})
