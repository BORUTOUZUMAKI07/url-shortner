import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import TagsPage from "@/app/(authenticated)/tags/page"

const { mockStoreHook, queryReturnMap, mockQueryClient } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  mockStoreHook.getState = () => mockStore
  const queryReturnMap: Record<string, any> = {
    authMe: { data: { id: 1, email: "test@test.com" }, isLoading: false },
    workspaces: { data: [{ id: 1, name: "Test" }], isLoading: false },
    tags: { data: [], isLoading: false },
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
    if (queryKey[0] === "tags") return queryReturnMap.tags
    return { data: [], isLoading: false }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn() },
  tagsApi: { list: vi.fn(), create: vi.fn(), delete: vi.fn() },
  workspacesApi: { list: vi.fn().mockResolvedValue([{ id: 1, name: "Test" }]) },
}))

describe("TagsPage", () => {
  beforeEach(() => {
    queryReturnMap.authMe = { data: { id: 1, email: "test@test.com" }, isLoading: false }
    queryReturnMap.workspaces = { data: [{ id: 1, name: "Test" }], isLoading: false }
    queryReturnMap.tags = { data: [], isLoading: false }
  })

  it("renders the page title", () => {
    render(<TagsPage />)
    expect(screen.getByText("Tags")).toBeDefined()
  })

  it("renders create tag section", () => {
    render(<TagsPage />)
    expect(screen.getByText("Create Tag")).toBeDefined()
  })

  it("shows empty state when no tags", () => {
    render(<TagsPage />)
    expect(screen.getByText("No tags yet")).toBeDefined()
  })

  it("lists tags when present", () => {
    queryReturnMap.tags = { data: [{ id: 1, name: "urgent", workspace_id: 1, created_at: "2024-01-01" }], isLoading: false }
    render(<TagsPage />)
    expect(screen.getByText("urgent")).toBeDefined()
  })
})
