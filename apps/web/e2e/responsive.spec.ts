import { expect, test } from '@playwright/test'
import { sampleCards, selectionBar } from './helpers'

for (const width of [304, 390, 820]) {
  test(`narrow ${width}px catalogue and sample actions remain reachable`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/')
    await expect(page.locator('.ds-card[data-dataset-id="clevr"]')).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeHidden()
    await page.getByRole('button', { name: 'Filters', exact: true }).click()
    const filters = page.getByRole('complementary', { name: 'Catalogue filters' })
    await expect(filters).toBeVisible()
    await filters.getByRole('checkbox', { name: /Preview available/ }).check()
    await filters.getByRole('button', { name: 'Close catalogue filters' }).click()
    await expect(page.locator('.ds-card')).toHaveCount(3)
    await page.locator('.ds-card[data-dataset-id="clevr"]').click()
    await expect(sampleCards(page).first()).toBeVisible()
    const id = await sampleCards(page).first().getAttribute('data-record-id')
    await page.getByLabel(`Select record ${id}`).check()
    await selectionBar(page).getByRole('button', { name: 'Analyze', exact: true }).click()
    await expect(page.getByRole('complementary', { name: 'Analysis' })).toBeVisible()
    const bounds = await page.getByRole('complementary', { name: 'Analysis' }).boundingBox()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
    await page.getByRole('button', { name: 'Close panel' }).click()
    await page.getByRole('button', { name: 'Expand navigation' }).click()
    await page.getByRole('navigation', { name: 'Primary' }).getByRole('button', { name: 'Collections', exact: true }).click()
    await page.getByRole('button', { name: 'Collapse navigation' }).click()
    await expect(page.getByRole('heading', { name: 'Collections', exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  })
}

test('metadata-only entries can open and close their full source record', async ({ page }) => {
  await page.goto('/#/dataset/imagenet')
  await expect(page.getByText('No inspectable examples here yet.')).toBeVisible()
  await page.getByRole('button', { name: 'Open full record' }).click()
  await expect(page.getByRole('complementary', { name: 'About dataset' })).toBeVisible()
  await page.getByRole('button', { name: 'Close panel' }).click()
  await expect(page.getByRole('complementary', { name: 'About dataset' })).toHaveCount(0)
})


test('navigation collapses on desktop and stays closed when resizing to mobile', async ({ page }) => {
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Primary' })
  await page.getByRole('button', { name: 'Collapse navigation' }).click()
  await expect(nav).toBeVisible()
  await expect.poll(async () => Math.round((await nav.boundingBox())!.width)).toBe(56)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(nav).toBeHidden()
  await page.getByRole('button', { name: 'Expand navigation' }).click()
  await expect(nav).toBeVisible()
})
