import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import WorkspacesPage from "@/app/(authenticated)/workspaces/page"

const { mockStore, mockStoreHook, mockQueryClient } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com", role: "admin" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  mockStoreHook.getState = () => mockStore
  const mockQueryClient = { invalidateQueries: vi.fn() }
  return { mockStore, mockStoreHook, mockQueryClient }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "authMe") return { data: mockStore.user, isLoading: false }
    if (queryKey[0] === "workspaces") return { data: [], isLoading: false }
    if (queryKey[0] === "workspace_members") return { data: [], isLoading: false }
    if (queryKey[0] === "workspace_invites") return { data: [], isLoading: false }
    return { data: [], isLoading: false }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn().mockResolvedValue({ id: 1, email: "test@test.com" }) },
  workspacesApi: { list: vi.fn().mockResolvedValue([]), create: vi.fn(), members: vi.fn().mockResolvedValue([]), listInvites: vi.fn().mockResolvedValue([]), acceptInvite: vi.fn(), invite: vi.fn(), removeMember: vi.fn(), updateMemberRole: vi.fn(), rename: vi.fn(), delete: vi.fn(), cancelInvite: vi.fn() },
  getErrorMessage: vi.fn((e) => e instanceof Error ? e.message : "Error"),
}))

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

describe("WorkspacesPage", () => {
  beforeEach(() => {
    mockStore.user = { id: 1, email: "test@test.com", role: "admin" }
  })

  it("renders the page title", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Workspaces")).toBeDefined()
  })

  it("renders create workspace section", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Create Workspace")).toBeDefined()
  })

  it("shows empty state when no workspaces", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("No workspaces yet")).toBeDefined()
  })

  it("renders accept invite button", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Accept Invite")).toBeDefined()
  })
})
