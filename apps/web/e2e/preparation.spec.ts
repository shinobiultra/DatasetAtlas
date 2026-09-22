import { expect, test } from '@playwright/test'
import { pointToLiveWorkbench } from './helpers'

const live = process.env.ATLAS_LIVE_API

test('on-demand plan shows source population and budgets without starting a download', async ({ page }) => {
  test.skip(!live, 'Requires a local workbench with AlgoPuzzleVQA prepared')
  await pointToLiveWorkbench(page, live!)
  await page.goto('/?mode=workbench#/dataset/algopuzzlevqa')
  await page.getByRole('button', { name: 'Prepare full data', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Prepare full dataset' })).toBeVisible()
  await page.getByRole('button', { name: 'Review preparation plan' }).click()
  await expect(page.getByRole('button', { name: 'Download and prepare', exact: true })).toBeEnabled()
  await expect(page.getByText(/^0 B download/)).toBeVisible()
  await expect(page.getByText(/not a claim of the paper-used revision/)).toBeVisible()
})

test('safe-view display requests derivatives without changing record assets', async ({ page }) => {
  test.skip(!live, 'Requires a local workbench')
  await pointToLiveWorkbench(page, live!)
  await page.addInitScript(() => localStorage.setItem('atlas.safe-view', 'true'))
  await page.goto('/?mode=workbench#/dataset/clevr')
  const image = page.locator('.sample-media img').first()
  await expect(image).toBeVisible()
  await expect(image).toHaveAttribute('src', /representation=safe-view/)
  await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0)
})
