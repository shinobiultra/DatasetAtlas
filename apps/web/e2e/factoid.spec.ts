import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

test.use({ screenshot: 'off', trace: 'off', video: 'off' })
test('FACTOID native user preview and complete scope open in the workbench', async ({ page }) => {
  test.skip(!process.env.ATLAS_LIVE_API, 'Requires the pinned native user population.')
  const api = process.env.ATLAS_LIVE_API!
  const response = await fetch(`${api}/api/v1/datasets/factoid`)
  expect(response.ok).toBeTruthy()
  const dataset = await response.json()
  expect(dataset.coverage.total_count).toBe(4150)
  expect(dataset.coverage.preview_count).toBe(100)
  await page.goto(`${api}/?mode=workbench#/dataset/factoid`)
  await expect(page.locator('.sample-card').first()).toBeVisible({ timeout: 60_000 })
  await page.locator('.sample-card .open').first().dblclick()
  await expect(page.locator('.focus-stage')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('group', { name: 'Population scope' }).getByRole('button', { name: 'Complete index' }).click()
  await expect(page.locator('.scopeline')).toContainText('4,150', { timeout: 60_000 })
  await expect(page.locator('.sample-card').first()).toBeVisible()
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-factoid-native-20261007.json', import.meta.url)), JSON.stringify({
    checked_at_utc: new Date().toISOString(), status: 'passed', snapshot_id: dataset.snapshot_id,
    native_user_population: 4150, preview_records: 100, native_user_inspection_opened: true, complete_scope_opened: true,
    source_scope: 'Native user rows, exact metadata/original retained; missing post text, historical membership and source rights remain unresolved.',
  }, null, 2) + '\n')
})
