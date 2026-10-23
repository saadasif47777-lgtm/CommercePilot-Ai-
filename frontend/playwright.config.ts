import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:8011', headless: true, trace: 'retain-on-failure' },
  webServer: { command: 'cd .. && python -m tests.browser_server', url: 'http://127.0.0.1:8011/api/health', timeout: 30000, reuseExistingServer: false },
})
