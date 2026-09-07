import { describe, it, expect } from "vitest"
import { apiKeysApi, auth, urls, workspacesApi } from "@/lib/api"

const PASSWORD = "StrongPass1!"

async function registerAndLogin(): Promise<{ email: string; workspaceId: number }> {
  const email = `it-${Math.random().toString(36).slice(2, 12)}@example.com`
  await auth.register(email, PASSWORD)
  await auth.login(email, PASSWORD)
  const [workspace] = await workspacesApi.list()
  if (!workspace) throw new Error("expected the default workspace after registration")
  return { email, workspaceId: workspace.id }
}

const API_ROOT = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1").replace(/\/api\/v1$/, "")

describe("urls API against a real backend", () => {
  it("creates, lists, reads back, and redirects a short URL", async () => {
    const { workspaceId } = await registerAndLogin()
    const original = "https://example.com/integration-destination"

    const created = await urls.create({ original_url: original, workspace_id: workspaceId })
    expect(created.short_code).toBeTruthy()
    expect(created.original_url).toBe(original)

    const { items } = await urls.list(null, { limit: 50 })
    expect(items.some((u) => u.id === created.id)).toBe(true)

    const detail = await urls.get(created.id)
    expect(detail.original_url).toBe(original)

    // Public redirect over the wire (no auto-follow: we want the 307 + Location).
    const res = await fetch(`${API_ROOT}/${created.short_code}`, { redirect: "manual" })
    expect([301, 302, 307, 308]).toContain(res.status)
    expect(res.headers.get("location")).toBe(original)
  })

  it("creates, lists, and revokes an API key", async () => {
    await registerAndLogin()

    const created = await apiKeysApi.create("integration-test")
    expect(created.key).toMatch(/^lf_/)

    const keys = await apiKeysApi.list()
    expect(keys.some((k) => k.id === created.id)).toBe(true)

    const quota = await apiKeysApi.quotaSummary()
    expect(quota.limit).toBeGreaterThan(0)

    await apiKeysApi.revoke(created.id)
    await expect(apiKeysApi.list()).resolves.toBeTruthy()
  })
})