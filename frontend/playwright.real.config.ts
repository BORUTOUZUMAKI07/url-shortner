import { defineConfig } from "@playwright/test"

/**
 * Real-backend E2E: Playwright drives the browser against the actual frontend
 * AND the actual backend (via the Next dev proxy on /api and /{short_code}).
 *
 * The backend must already be running against Docker testcontainers at
 * http://127.0.0.1:8000 — boot it with (from backend/):
 *     uv run python scripts/e2e_server.py
 */
export default defineConfig({
  testDir: "./e2e-real",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 150_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    navigationTimeout: 60_000,
  },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})