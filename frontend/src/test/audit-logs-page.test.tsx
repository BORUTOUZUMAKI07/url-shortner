import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import { server } from "@/test/mocks/server"
import { http, HttpResponse } from "msw"
import AuditLogsPage from "@/app/(authenticated)/audit-logs/page"

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

const { mockStoreHook } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  return { mockStoreHook }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

describe("AuditLogsPage", () => {
  it("renders the page title", async () => {
    render(<AuditLogsPage />)
    expect(await screen.findByText("Audit Logs")).toBeDefined()
  })

  it("shows empty state when no logs", async () => {
    render(<AuditLogsPage />)
    expect(await screen.findByText("No audit logs yet")).toBeDefined()
  })

  it("renders log entries when present", async () => {
    server.use(
      http.get(`${API}/audit-logs/workspace/:workspaceId`, () => {
        return HttpResponse.json([
          { id: 1, action: "create", resource_type: "url", resource_id: 1, user_id: 1, before_state: null, after_state: null, created_at: "2024-01-01T00:00:00Z" },
        ])
      })
    )
    render(<AuditLogsPage />)
    expect(await screen.findByText("create")).toBeDefined()
    expect(screen.getByText("url")).toBeDefined()
  })
})
