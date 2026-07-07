import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import AuditLogsPage from "@/app/(authenticated)/audit-logs/page"

const { mockStoreHook, queryReturnMap, mockQueryClient } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  const queryReturnMap: Record<string, any> = {
    authMe: { data: { id: 1 }, isLoading: false },
    workspaces: { data: [{ id: 1, name: "Test" }], isLoading: false },
    auditLogs: { data: [], isLoading: false },
  }
  const mockQueryClient = { invalidateQueries: vi.fn() }
  return { mockStoreHook, queryReturnMap, mockQueryClient }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "authMe") return queryReturnMap.authMe
    if (queryKey[0] === "workspaces") return queryReturnMap.workspaces
    if (queryKey[0] === "auditLogs") return queryReturnMap.auditLogs
    return { data: [], isLoading: false }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn() },
  workspacesApi: { list: vi.fn().mockResolvedValue([{ id: 1, name: "Test" }]) },
  auditApi: { list: vi.fn().mockResolvedValue([]) },
}))

describe("AuditLogsPage", () => {
  beforeEach(() => {
    queryReturnMap.authMe = { data: { id: 1 }, isLoading: false }
    queryReturnMap.workspaces = { data: [{ id: 1, name: "Test" }], isLoading: false }
    queryReturnMap.auditLogs = { data: [], isLoading: false }
  })

  it("renders the page title", () => {
    render(<AuditLogsPage />)
    expect(screen.getByText("Audit Logs")).toBeDefined()
  })

  it("shows empty state when no logs", () => {
    render(<AuditLogsPage />)
    expect(screen.getByText("No audit logs yet")).toBeDefined()
  })

  it("renders log entries when present", () => {
    queryReturnMap.auditLogs = {
      data: [{ id: 1, action: "create", resource_type: "url", resource_id: 1, user_id: 1, before_state: null, after_state: null, created_at: "2024-01-01T00:00:00Z" }],
      isLoading: false,
    }
    render(<AuditLogsPage />)
    expect(screen.getByText("create")).toBeDefined()
    expect(screen.getByText("url")).toBeDefined()
  })
})
