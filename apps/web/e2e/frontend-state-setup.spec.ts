import { expect, test, type Page, type Route } from '@playwright/test'
import { build } from 'esbuild'
import { fileURLToPath } from 'node:url'

// Synthetic engineering fixtures only. Bundle the shipping hooks/components;
// network requests terminate at Playwright rather than a dataset or model.
const snapshot = 'synthetic-state-snapshot'
const fixturePage = (id: string, cursor: string | null = null) => ({
  snapshot_id: snapshot, unit: 'example', population_scope: 'preview',
  records: [{ id, dataset_id: 'synthetic-state', release_id: 'test-only', snapshot_id: snapshot, unit: 'example', text: id, assets: [], source: {} }],
  returned_count: 1, matched_count: 2, count_status: 'exact', cursor,
})
const facetCounts = {
  snapshot_id: snapshot, unit: 'example', population_scope: 'preview', denominator: 3, count_status: 'exact', sampling_applied: false, warnings: [],
  results: [{ field_id: 'source.group', kind: 'categorical', denominator: 3, missing: 0, truncated: false,
    counts: [{ value: 'A', count: 1 }, { value: 'B', count: 1 }, { value: 'C', count: 1 }] }],
}

let harness: string
test.beforeAll(async () => {
  const bundle = await build({
    stdin: { resolveDir: fileURLToPath(new URL('../src', import.meta.url)), sourcefile: 'frontend-state-harness.tsx', loader: 'tsx', contents: `
      import { useState } from 'react'
      import { createRoot } from 'react-dom/client'
      import { useBrowse, clauseFilter } from './dataset/model'
      import { FilterRail } from './dataset/FilterRail'
      import { AnalyzePanel } from './panels/AnalyzePanel'
      import { SettingsPage } from './pages/SettingsPage'
      import { queryPack } from './query'
      const snapshot = '${snapshot}'
      const fields = [{ id: 'source.group', name: 'Group', dtype: 'category', namespace: 'source', unit: 'example', values: ['A', 'B', 'C'], query_ops: ['eq', 'in'] }, { id: 'source.flag', name: 'Flag', dtype: 'boolean', namespace: 'source', unit: 'example', values: [true, false], query_ops: ['eq'] }]
      const pack = { dataset: { id: 'synthetic-state', name: 'Synthetic state fixture', snapshot_id: snapshot }, population_scope: 'preview', fields,
        records: ['A', 'B', 'C'].map(group => ({ id: group, dataset_id: 'synthetic-state', release_id: 'test-only', snapshot_id: snapshot, unit: 'example', assets: [], source: { group, flag: group === 'A' } })) }
      function BrowseHarness() {
        const [search, setSearch] = useState('old')
        const [enabled, setEnabled] = useState(true)
        const browse = useBrowse('synthetic-state', { snapshot_id: snapshot, search }, enabled)
        return <><button onClick={() => setSearch('new')}>New query</button><button onClick={() => setEnabled(false)}>Disable</button>
          <button onClick={browse.loadMore}>More</button><output aria-label="Browse state">{JSON.stringify({ ids: browse.records.map(row => row.id), loading: browse.loading, loadingMore: browse.loadingMore, hasMore: browse.hasMore, error: browse.error })}</output></>
      }
      function FilterHarness({ dynamic = false }) {
        const [search, setSearch] = useState('')
        const [clauses, setClauses] = useState([])
        const query = { snapshot_id: snapshot, search, filter: clauseFilter(clauses) }
        const rows = queryPack(pack, query).records.map(row => row.id)
        return <><input aria-label="Search fixture" value={search} onChange={event => setSearch(event.target.value)} />
          <FilterRail datasetId="synthetic-state" fields={dynamic ? fields.map(field => ({ ...field, values: null })) : fields} clauses={clauses} baseQuery={query} onAdd={clause => setClauses(current => [...current, clause])} onRemove={key => setClauses(current => current.filter(clause => clause.key !== key))} onClear={() => setClauses([])} matchedCount={rows.length} />
          <output aria-label="Matching fixture rows">{JSON.stringify(rows)}</output></>
      }
      function AdvancedHarness() {
        const group = (key, value, source) => ({ key, fieldId: 'source.group', fieldName: 'Group', op: 'eq', value, label: key, source })
        const facet = [group('A', 'A', 'facet'), group('B', 'B', 'facet')]
        const filtered = clauses => queryPack(pack, { snapshot_id: snapshot, filter: clauseFilter(clauses) }).records.map(row => row.id)
        return <><output aria-label="Facet rows">{JSON.stringify(filtered(facet))}</output>
          <output aria-label="Different facet fields">{JSON.stringify(filtered([...facet, { key: 'flag', fieldId: 'source.flag', fieldName: 'Flag', op: 'eq', value: true, label: 'Flag', source: 'facet' }]))}</output>
          <output aria-label="Facet with explicit constraint">{JSON.stringify(filtered([...facet, group('explicit', 'A')]))}</output>
          <output aria-label="Two explicit constraints">{JSON.stringify(filtered([group('explicit A', 'A'), group('explicit B', 'B')]))}</output></>
      }
      const screen = window.location.hash.slice(1)
      createRoot(document.getElementById('test-root')).render(screen === 'browse' ? <BrowseHarness /> : screen === 'filters' || screen === 'dynamic-filters' ? <FilterHarness dynamic={screen === 'dynamic-filters'} /> : screen === 'advanced' ? <AdvancedHarness /> : screen === 'models' ? <SettingsPage section="models" capabilities={null} onSection={() => {}} /> : <AnalyzePanel selected={['synthetic-row']} unit="example" saved={null} onSave={async () => null} onRan={() => {}} />)
    ` },
    bundle: true, write: false, format: 'iife', jsx: 'automatic',
    define: { 'import.meta.env.BASE_URL': JSON.stringify('/'), 'process.env.NODE_ENV': JSON.stringify('development') },
  })
  harness = bundle.outputFiles[0].text
})

async function openHarness(page: Page, screen: string) {
  await page.route('**/frontend-state-harness?mode=workbench', route => route.fulfill({ contentType: 'text/html', body: '<html><body><main id="test-root"></main></body></html>' }))
  await page.goto(`/frontend-state-harness?mode=workbench#${screen}`)
  await page.addScriptTag({ content: harness })
}
const state = async (page: Page) => JSON.parse(await page.getByLabel('Browse state').innerText())

test('changing a query during a delayed continuation resets pagination and excludes the stale page', async ({ page }) => {
  let delayed: Route | undefined
  await page.route('**/api/v1/queries/synthetic-state', route => {
    const query = route.request().postDataJSON()
    if (query.search === 'old' && query.cursor) { delayed = route; return }
    return route.fulfill({ json: fixturePage(query.search === 'new' ? query.cursor ? 'new-second' : 'new-first' : 'old-first', query.cursor ? null : 'next') })
  })
  await openHarness(page, 'browse')
  await expect.poll(async () => (await state(page)).ids).toEqual(['old-first'])
  await page.getByRole('button', { name: 'More', exact: true }).click()
  await expect.poll(() => Boolean(delayed)).toBe(true)
  await page.getByRole('button', { name: 'New query' }).click()
  await expect.poll(async () => (await state(page)).ids).toEqual(['new-first'])
  await delayed!.fulfill({ json: fixturePage('stale-old-second') }).catch(() => {})
  await expect.poll(async () => (await state(page)).loadingMore).toBe(false)
  await page.getByRole('button', { name: 'More', exact: true }).click()
  await expect.poll(async () => (await state(page)).ids).toEqual(['new-first', 'new-second'])
})

test('disabling a query invalidates an in-flight response and clears every browse state', async ({ page }) => {
  let delayed: Route | undefined
  await page.route('**/api/v1/queries/synthetic-state', route => { delayed = route })
  await openHarness(page, 'browse')
  await expect.poll(() => Boolean(delayed)).toBe(true)
  await page.getByRole('button', { name: 'Disable' }).click()
  await delayed!.fulfill({ json: fixturePage('stale-disabled-row', 'next') }).catch(() => {})
  await expect.poll(() => state(page)).toEqual({ ids: [], loading: false, loadingMore: false, hasMore: false, error: '' })
})

test('checkbox values are alternatives within a field and explicit advanced clauses remain constraints', async ({ page }) => {
  await openHarness(page, 'advanced')
  await expect(page.getByLabel('Facet rows')).toHaveText('["A","B"]')
  await expect(page.getByLabel('Different facet fields')).toHaveText('["A"]')
  await expect(page.getByLabel('Facet with explicit constraint')).toHaveText('["A"]')
  await expect(page.getByLabel('Two explicit constraints')).toHaveText('[]')
})

test('facet checkboxes use alternative values and remain removable after the count response omits a selected value', async ({ page }) => {
  await page.route('**/api/v1/aggregate/synthetic-state', route => {
    const query = route.request().postDataJSON().query
    return route.fulfill({ json: query.filter ? { ...facetCounts, results: [{ ...facetCounts.results[0], counts: [{ value: 'A', count: 1 }] }] } : facetCounts })
  })
  await openHarness(page, 'filters')
  await page.getByTitle('Group = A', { exact: true }).getByRole('checkbox').check()
  await page.getByTitle('Group = B', { exact: true }).getByRole('checkbox').check()
  await expect(page.getByLabel('Matching fixture rows')).toHaveText('["A","B"]')
  await expect(page.getByTitle('Group = B', { exact: true }).getByRole('checkbox')).toBeChecked()
  await page.getByTitle('Group = B', { exact: true }).getByRole('checkbox').uncheck()
  await expect(page.getByLabel('Matching fixture rows')).toHaveText('["A"]')
})

test('rapid search edits debounce facet aggregation', async ({ page }) => {
  const searches: string[] = []
  await page.route('**/api/v1/aggregate/synthetic-state', route => {
    const query = route.request().postDataJSON().query
    searches.push(query.search)
    return route.fulfill({ json: facetCounts })
  })
  await openHarness(page, 'filters')
  await expect.poll(() => searches).toEqual([''])
  await page.getByRole('textbox', { name: 'Search fixture' }).pressSequentially('abc', { delay: 30 })
  await expect.poll(() => searches).toEqual(['', 'abc'])
})

test('categories discovered from aggregates remain selectable after narrowing the same field', async ({ page }) => {
  let filtered = false
  await page.route('**/api/v1/aggregate/synthetic-state', route => {
    const query = route.request().postDataJSON().query
    filtered = Boolean(query.filter)
    return route.fulfill({ json: filtered ? { ...facetCounts, results: [{ ...facetCounts.results[0], counts: [{ value: 'A', count: 1 }] }] } : facetCounts })
  })
  await openHarness(page, 'dynamic-filters')
  await page.getByTitle('Group = A', { exact: true }).getByRole('checkbox').check()
  await expect.poll(() => filtered).toBe(true)
  await page.getByTitle('Group = B', { exact: true }).getByRole('checkbox').check()
  await expect(page.getByLabel('Matching fixture rows')).toHaveText('["A","B"]')
})

test('changing a facet query aborts its obsolete in-flight count', async ({ page }) => {
  let delayed: Route | undefined
  await page.route('**/api/v1/aggregate/synthetic-state', route => {
    if (!route.request().postDataJSON().query.search) { delayed = route; return }
    return route.fulfill({ json: facetCounts })
  })
  await openHarness(page, 'filters')
  await expect.poll(() => Boolean(delayed)).toBe(true)
  const cancelled = page.waitForEvent('requestfailed', { predicate: request => request.url().endsWith('/aggregate/synthetic-state'), timeout: 5000 })
  await page.getByRole('textbox', { name: 'Search fixture' }).fill('changed')
  expect((await cancelled).failure()?.errorText).toContain('ERR_ABORTED')
  await delayed!.fulfill({ json: facetCounts }).catch(() => {})
})

test('unavailable analyses stay inspectable and expose setup while execution is blocked', async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    return route.fulfill({ json: path.endsWith('/processors') ? [{ id: 'embed.minilm', name: 'MiniLM', description: 'Text embeddings', available: false, reason: 'Pinned local MiniLM weights are missing.', requires_local_model: true, input_units: ['example'] }] : [] })
  })
  await openHarness(page, 'analysis')
  await page.getByRole('combobox', { name: 'Analysis', exact: true }).selectOption('embed.minilm')
  await expect(page.getByText('Pinned local MiniLM weights are missing.', { exact: true })).toBeVisible()
  await expect(page.getByText('atlas models status', { exact: true })).toBeVisible()
  await expect(page.getByText('atlas models fetch', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Estimate resources and coverage' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Run analysis' })).toBeDisabled()
})

test('model settings show unavailable reasons and an explicit local setup path', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/processors') ? [
    { id: 'embed.minilm', name: 'MiniLM', description: 'Text embeddings', available: false, reason: 'Pinned local MiniLM weights are missing.', requires_local_model: true },
  ] : [] }))
  await openHarness(page, 'models')
  await expect(page.getByText('Pinned local MiniLM weights are missing.', { exact: true })).toBeVisible()
  await expect(page.getByText('atlas models status', { exact: true })).toBeVisible()
  await expect(page.getByText('atlas models fetch', { exact: true })).toBeVisible()
})
