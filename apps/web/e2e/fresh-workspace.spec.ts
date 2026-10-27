import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { readdirSync } from 'node:fs'

/** The shipped catalogue is the repository registry, so the expected count is read from it, not typed. */
const catalogueSize = readdirSync(fileURLToPath(new URL('../../../registry/datasets', import.meta.url))).filter(name => name.endsWith('.yaml')).length

/**
 * A colleague's first run: an empty workspace holding only the shipped catalogue.
 *
 * Served by scripts/e2e_workspace.py on its own port. Nothing here touches the maintainer's workspace.
 * The fixtures are synthetic and exist only for these tests.
 */
test.use({ baseURL: 'http://127.0.0.1:4188' })
const fixtures = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../test-results/e2e-fixtures')

async function brokenTiles(page: Page) {
  return page.evaluate(async () => {
    const images = [...document.querySelectorAll('img')].filter(image => image.src.includes('/api/v1/media/'))
    const statuses = await Promise.all(images.map(image => fetch(image.src).then(response => response.status)))
    return { shown: images.length, notOk: statuses.filter(status => status !== 200).length, undecoded: images.filter(image => image.complete && image.naturalWidth === 0).length }
  })
}

test('the plain URL is the workbench and no catalogue entry claims records it cannot open', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Workbench', { exact: true })).toBeVisible()
  await expect(page.getByText(new RegExp(`${catalogueSize} catalogue entries · 0 browsable here`))).toBeVisible()
  // Datasets with a recorded upstream preview are offered, never shown as ready (the filter rail is open at this width).
  await expect(page.getByLabel(/Preview on request/)).toBeVisible()
})

test('a dataset with a recorded preview offers to fetch it and states why nothing is shown yet', async ({ page }) => {
  await page.goto('/#/dataset/clevr')
  await expect(page.getByRole('heading', { name: 'Preview not fetched on this machine yet' })).toBeVisible()
  await expect(page.getByText(/before anything is fetched/)).toBeVisible()
  await page.getByRole('button', { name: 'Get preview' }).first().click()
  await expect(page.getByRole('dialog', { name: 'Dataset preparation' })).toBeVisible()
  await page.getByRole('button', { name: 'Review preparation plan' }).click()
  // The plan states its cost and the source; nothing has started.
  await expect(page.getByText(/not a claim of the paper-used revision/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Fetch preview' })).toBeEnabled()
})

test('a fresh public source reviews pinned files before acquisition', async ({ page }) => {
  const starts: string[] = []
  page.on('request', request => { if (new URL(request.url()).pathname.endsWith('/start')) starts.push(request.url()) })
  await page.goto('/#/dataset/advbench')
  await page.getByRole('button', { name: /Prepare|Get preview/ }).first().click()
  const planned = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/preparation/plan') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Review preparation plan' }).click()
  const response = await planned
  expect(response.status()).toBe(200)
  const plan = await response.json() as { ready: boolean; files: { url: string; sha256: string }[]; expected_download_bytes: number; max_download_bytes: number }
  expect(plan.ready).toBe(true)
  expect(plan.files.length).toBeGreaterThan(0)
  for (const file of plan.files) {
    expect(file.url).toMatch(/^https:\/\//)
    expect(file.sha256).toMatch(/^[a-f0-9]{64}$/)
  }
  expect(plan.expected_download_bytes).toBeLessThanOrEqual(plan.max_download_bytes)
  await expect(page.getByRole('button', { name: /^(Fetch preview|Download and prepare)$/ })).toBeEnabled()
  expect(starts).toEqual([])
})

test('add a folder of images, inspect it, build its preview and browse every image on a cold cache', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Add dataset' }).click()
  const dialog = page.getByRole('dialog', { name: 'Add your own dataset' })
  await dialog.getByLabel('Folder, file or Hugging Face URL').fill(path.join(fixtures, 'sorted-shapes'))
  await dialog.getByRole('button', { name: 'Inspect' }).click()
  const found = dialog.getByRole('region', { name: 'Inspection result' })
  await expect(found).toContainText('Folder or archive of images · 12 images')
  await expect(found).toContainText('labels: label')
  await dialog.getByLabel('Dataset name').fill('Sorted shapes')
  await dialog.getByRole('button', { name: 'Add and build preview' }).click()
  await expect(dialog.getByRole('button', { name: 'Open dataset' })).toBeVisible({ timeout: 60_000 })
  await dialog.getByRole('button', { name: 'Open dataset' }).click()
  await expect(page.getByRole('heading', { name: 'Sorted shapes' })).toBeVisible()
  await expect(page.locator('.scopeline')).toContainText('12')
  await expect.poll(async () => (await brokenTiles(page)).shown).toBeGreaterThanOrEqual(12)
  expect(await brokenTiles(page)).toMatchObject({ notOk: 0, undecoded: 0 })
})

test('a table with an image column reports its missing cells and loads every image', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Add dataset' }).click()
  const dialog = page.getByRole('dialog', { name: 'Add your own dataset' })
  await dialog.getByLabel('Folder, file or Hugging Face URL').fill(path.join(fixtures, 'scored/scored.csv'))
  await dialog.getByRole('button', { name: 'Inspect' }).click()
  const found = dialog.getByRole('region', { name: 'Inspection result' })
  await expect(found).toContainText('Table · 10 rows')
  await expect(dialog.getByLabel('Image column')).toHaveValue('file')
  await found.getByText('4 columns').click()
  await expect(found).toContainText('note')
  await expect(found).toContainText('1 missing')
  await dialog.getByLabel('Dataset name').fill('Scored pictures')
  await dialog.getByRole('button', { name: 'Add and build preview' }).click()
  await dialog.getByRole('button', { name: 'Open dataset' }).click({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: 'Scored pictures' })).toBeVisible()
  await expect(page.locator('.scopeline')).toContainText('10')
  await expect.poll(async () => (await brokenTiles(page)).shown).toBeGreaterThanOrEqual(10)
  expect((await brokenTiles(page)).notOk).toBe(0)
})
