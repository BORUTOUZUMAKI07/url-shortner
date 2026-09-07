import { defineConfig } from "vitest/config"
import path from "path"

const apiUrl = process.env.INTEGRATION_API_URL || "http://127.0.0.1:8000/api/v1"

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/integration/**/*.integration.test.ts"],
    setupFiles: ["./src/integration/setup.ts"],
    env: {
      NEXT_PUBLIC_API_URL: apiUrl,
    },
    testTimeout: 180_000,
    hookTimeout: 30_000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})