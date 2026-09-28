import { defineConfig } from "vitest/config"
import path from "path"

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    exclude: ["e2e/**", "e2e-real/**", "node_modules/**", "src/integration/**"],
    // The page tests render real components that resolve a chain of msw-backed
    // queries (e.g. urls/[id]/analytics needs url -> summary -> timeseries).
    // That lands within a whisker of vitest's 5s default, so the suite went
    // red roughly one run in eight purely on machine load — a flaky test is
    // indistinguishable from a real regression, so it has to go.
    //
    // Note: raising the *per-query* `{ timeout }` on findBy* does NOT help,
    // because the test itself is killed at `testTimeout` first. This knob is
    // the one that governs. vitest.integration.config.ts does the same thing
    // (180s) for the same reason.
    testTimeout: 15_000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
