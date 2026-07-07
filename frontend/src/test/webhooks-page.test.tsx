import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import WebhooksPage from "@/app/(authenticated)/webhooks/page"

const { mockStoreHook, queryReturnMap, mockQueryClient } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  const queryReturnMap: Record<string, any> = {
    authMe: { data: { id: 1 }, isLoading: false },
    workspaces: { data: [{ id: 1, name: "Test" }], isLoading: false },
    webhooks: { data: [], isLoading: false },
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
    if (queryKey[0] === "webhooks") return queryReturnMap.webhooks
    return { data: [], isLoading: false }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn() },
  webhooksApi: { list: vi.fn().mockResolvedValue([]), create: vi.fn(), delete: vi.fn() },
  workspacesApi: { list: vi.fn().mockResolvedValue([{ id: 1, name: "Test" }]) },
}))

describe("WebhooksPage", () => {
  beforeEach(() => {
    queryReturnMap.authMe = { data: { id: 1 }, isLoading: false }
    queryReturnMap.workspaces = { data: [{ id: 1, name: "Test" }], isLoading: false }
    queryReturnMap.webhooks = { data: [], isLoading: false }
  })

  it("renders the page title", () => {
    render(<WebhooksPage />)
    expect(screen.getByText("Webhooks")).toBeDefined()
  })

  it("shows empty state when no webhooks", () => {
    render(<WebhooksPage />)
    expect(screen.getByText("No webhooks yet")).toBeDefined()
  })

  it("renders add webhook button", () => {
    render(<WebhooksPage />)
    expect(screen.getByText("Add Webhook")).toBeDefined()
  })

  it("renders receiver log link", () => {
    render(<WebhooksPage />)
    expect(screen.getByText("Receiver Log")).toBeDefined()
  })

  it("lists webhooks when present", () => {
    queryReturnMap.webhooks = {
      data: [{ id: 1, url: "https://example.com/hook", events: ["url.created"], is_active: true, created_at: "2024-01-01" }],
      isLoading: false,
    }
    render(<WebhooksPage />)
    expect(screen.getByText("https://example.com/hook")).toBeDefined()
    expect(screen.getByText("Active")).toBeDefined()
    expect(screen.getByText("url.created")).toBeDefined()
  })
})
