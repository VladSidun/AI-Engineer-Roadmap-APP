import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  fullyParallel: false,
  timeout: 120_000,
  reporter: 'list',
  use: {
    ...devices['Desktop Chrome'],
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
    viewport: { width: 1440, height: 900 },
    baseURL: process.env.QUEST_E2E_URL ?? 'http://127.0.0.1:8017',
  },
})
