import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://127.0.0.1:4187',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'npm run preview -- --port 4187 --strictPort',
      url: 'http://127.0.0.1:4187',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      // An empty workspace with only the shipped catalogue: a colleague's first run (e2e/fresh-workspace.spec.ts).
      command: `${process.env.ATLAS_PYTHON ?? 'python'} ../../scripts/e2e_workspace.py --port 4188 --fixtures test-results/e2e-fixtures`,
      url: 'http://127.0.0.1:4188/api/v1/capabilities',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
