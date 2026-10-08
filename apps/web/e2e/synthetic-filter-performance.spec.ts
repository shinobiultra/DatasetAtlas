import { expect, test } from '@playwright/test'
import { build } from 'esbuild'
import { cpus, totalmem } from 'node:os'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

test('shipping static query engine filters 10,000 synthetic records within the SPEC target', async ({ page, browser }) => {
  const bundle = await build({ entryPoints: [fileURLToPath(new URL('../src/query.ts', import.meta.url))], bundle: true, write: false, format: 'iife', globalName: 'AtlasQuery' })
  await page.goto('/')
  await page.addScriptTag({ content: bundle.outputFiles[0].text })
  const measured = await page.evaluate(() => {
    const engine = (window as any).AtlasQuery
    const pack = { dataset: { id: 'synthetic-filter', snapshot_id: 'test-only' }, population_scope: 'preview',
      fields: [{ id: 'source.group', dtype: 'category', unit: 'example', query_ops: ['eq'] }, { id: 'source.score', dtype: 'number', unit: 'example', query_ops: ['gte'] }],
      records: Array.from({ length: 10_000 }, (_, i) => ({ id: `fixture-${i}`, unit: 'example', assets: [], source: { group: i % 2 ? 'B' : 'A', score: i }, text: `Synthetic ${i}` })) }
    const query = { snapshot_id: 'test-only', unit: 'example', population_scope: 'preview', limit: 60,
      filter: { and: [{ field_id: 'source.group', op: 'eq', value: 'A' }, { field_id: 'source.score', op: 'gte', value: 5000 }] } }
    const timings: number[] = []
    let matched = 0
    for (let i = 0; i < 11; i++) { const start = performance.now(); matched = engine.queryPack(pack, query).matched_count; timings.push(performance.now() - start) }
    return { cold_ms: timings[0], warm_ms: timings.slice(1), matched_count: matched, user_agent: navigator.userAgent }
  })
  const report = { verified_at_utc: new Date().toISOString(), fixture: 'SYNTHETIC ENGINEERING TEST ONLY', status: 'passed',
    engine: 'Shipping queryPack module bundled without modification and executed in Chromium', population: 10000, target_ms: 200,
    scope: 'In-memory static filtering and query pagination; excludes pack download, DOM rendering and GPU paint',
    cache_conditions: 'First query after pack construction, followed by ten queries over the same loaded pack', ...measured,
    browser_version: browser.version(), host: { cpu: cpus()[0]?.model, logical_cpus: cpus().length, memory_gib: Math.round(totalmem() / 2 ** 30), platform: process.platform } }
  expect(measured.matched_count).toBe(2500)
  expect(Math.max(measured.cold_ms, ...measured.warm_ms)).toBeLessThan(200)
  writeFileSync(fileURLToPath(new URL('../../../reports/browser-preview-filter-performance-20261007.json', import.meta.url)), JSON.stringify(report, null, 2) + '\n')
})
