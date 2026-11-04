// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  fullyParallel: false,
  forbidOnly: true,
  retries: 3,
  workers: 1,
  timeout: 60000,
  expect: {
    timeout: 15000,
  },
  reporter: [
    ['list'],
    ['json', { outputFile: '../results/test-results.json' }],
  ],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',
    viewport: { width: 1280, height: 720 },
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: process.env.CHROME_PATH ? 'chrome' : undefined,
        launchOptions: {
          ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
          args: ['--disable-blink-features=AutomationControlled'],
        },
      },
    },
  ],
  outputDir: '../results/test-artifacts',
});
