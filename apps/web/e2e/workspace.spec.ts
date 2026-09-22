import { expect, test } from '@playwright/test'
import { expectPanel, sampleCards, scopeLine, selectionBar, switchView, tableRows } from './helpers'

/**
 * The browsing → inspection → comparison flow the interface is built around,
 * exercised against the published CLEVR preview.
 */

test('focused inspection takes the centre and returns to the same browsing state', async ({ page }) => {
  await page.goto('/#/dataset/clevr')
  await expect(sampleCards(page).first()).toBeVisible()
  const recordId = await sampleCards(page).first().getAttribute('data-record-id')

  await page.getByRole('button', { name: `Open focused inspection for ${recordId}` }).click()
  await expect(page.locator('.focus')).toBeVisible()
  await expect(page.locator('.focus-bar .pos')).toContainText('1 /')

  // The filmstrip is labelled as browsing order, not as a similarity result.
  await expect(page.getByText('Matching samples', { exact: true })).toBeVisible()
  await expect(page.getByText(/Neighbours in browsing order, not a similarity result/)).toBeVisible()

  // Previous is unavailable at the start; next advances the position.
  await expect(page.getByRole('button', { name: 'Previous sample' })).toBeDisabled()
  await page.getByRole('button', { name: 'Next sample' }).click()
  await expect(page.locator('.focus-bar .pos')).toContainText('2 /')

  await page.locator('.focus-bar').getByRole('button', { name: 'Close' }).click()
  await expect(page.locator('.focus')).toHaveCount(0)
  await expect(sampleCards(page).first()).toBeVisible()
})

test('compare pins two records and marks only comparable differences', async ({ page }) => {
  await page.goto('/#/dataset/clevr')
  await expect(sampleCards(page).first()).toBeVisible()
  const first = await sampleCards(page).nth(0).getAttribute('data-record-id')
  const second = await sampleCards(page).nth(1).getAttribute('data-record-id')

  await page.getByLabel(`Select record ${first}`).check()
  await page.getByLabel(`Select record ${second}`).check()
  await expect(selectionBar(page).locator('.count')).toHaveText('2 selected')
  await selectionBar(page).getByRole('button', { name: 'Compare' }).click()

  const compare = page.locator('.compare')
  await expect(compare).toBeVisible()
  await expect(compare.getByRole('region', { name: 'Comparison side A' })).toBeVisible()
  await expect(compare.getByRole('region', { name: 'Comparison side B' })).toBeVisible()
  // Two unrelated examples must not be presented as a recorded pair.
  await expect(compare.getByText('No recorded relation between A and B')).toBeVisible()

  const rows = compare.locator('table.aligned tbody tr')
  await expect(rows.first()).toBeVisible()
  const allRows = await rows.count()
  await compare.getByText('Differences only', { exact: true }).click()
  const differing = await rows.count()
  expect(differing).toBeLessThanOrEqual(allRows)
  for (const row of await rows.all()) await expect(row).toHaveAttribute('data-diff', 'true')
})

test('view switching preserves the population, filters and selection', async ({ page }) => {
  await page.goto('/#/dataset/clevr')
  await expect(sampleCards(page).first()).toBeVisible()
  const recordId = await sampleCards(page).first().getAttribute('data-record-id')
  await page.getByLabel(`Select record ${recordId}`).check()
  const matched = await scopeLine(page).innerText()

  await switchView(page, 'Table')
  await expect(tableRows(page).first()).toBeVisible()
  await expect(scopeLine(page)).toContainText(matched.split('·')[1].trim())
  await expect(selectionBar(page).locator('.count')).toHaveText('1 selected')

  await switchView(page, 'Grid')
  await expect(selectionBar(page).locator('.count')).toHaveText('1 selected')
  await expect(page.getByLabel(`Select record ${recordId}`)).toBeChecked()
})

test('exactly one contextual panel is open at a time', async ({ page }) => {
  await page.goto('/#/dataset/clevr')
  await expect(sampleCards(page).first()).toBeVisible()
  const recordId = await sampleCards(page).first().getAttribute('data-record-id')

  await page.getByRole('button', { name: `Inspect record ${recordId}` }).click()
  await expectPanel(page, 'Sample inspector')
  await expect(page.locator('.ctx')).toHaveCount(1)

  await page.getByRole('button', { name: 'About dataset' }).click()
  await expectPanel(page, 'About dataset')
  await expect(page.locator('.ctx')).toHaveCount(1)
  await expect(page.getByRole('complementary', { name: 'Sample inspector' })).toHaveCount(0)

  // Closing About restores the sample it replaced rather than emptying the slot.
  await page.getByRole('button', { name: 'Close panel' }).click()
  await expectPanel(page, 'Sample inspector')
})

test('the overview counts the filtered population and names each field origin', async ({ page }) => {
  await page.goto('/#/dataset/clevr/overview')
  await expect(page.getByRole('heading', { name: 'At a glance' })).toBeVisible()
  await expect(page.getByText(/not a measurement of what is browsable here/)).toBeVisible()
  const answers = page.locator('.ov-card').filter({ hasText: 'answer' }).first()
  await expect(answers).toContainText('Source annotations')
  await expect(answers).toContainText('100 records')
  await expect(page.getByRole('heading', { name: 'Population described' })).toBeVisible()
})

test('the catalogue filters by coverage and opens a dataset straight into its samples', async ({ page }) => {
  await page.goto('/')
  const rail = page.getByRole('complementary', { name: 'Catalogue filters' })
  await rail.getByRole('checkbox', { name: /Preview available/ }).check()
  await expect(page.locator('.ds-card')).toHaveCount(3)
  await page.locator('.ds-card[data-dataset-id="eurosat"]').click()
  await expect(page).toHaveURL(/#\/dataset\/eurosat$/)
  await expect(sampleCards(page).first()).toBeVisible()
})
