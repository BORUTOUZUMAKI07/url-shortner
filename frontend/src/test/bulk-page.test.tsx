import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import BulkPage from "@/app/(authenticated)/bulk/page"

const { mockStoreHook, queryReturnMap, mockQueryClient } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  const queryReturnMap: Record<string, any> = {
    authMe: { data: { id: 1 }, isLoading: false },
    workspaces: { data: [{ id: 1, name: "Test" }], isLoading: false },
    folders: { data: [], isLoading: false },
    tags: { data: [], isLoading: false },
    urls: { data: { items: [], total: 0 }, isLoading: false },
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
    if (queryKey[0] === "folders") return queryReturnMap.folders
    if (queryKey[0] === "tags") return queryReturnMap.tags
    if (queryKey[0] === "urls") return queryReturnMap.urls
    return { data: [], isLoading: false }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn() },
  bulkApi: { create: vi.fn(), export: vi.fn(), disable: vi.fn(), reactivate: vi.fn(), delete: vi.fn(), qr: vi.fn() },
  workspacesApi: { list: vi.fn().mockResolvedValue([{ id: 1, name: "Test" }]) },
  foldersApi: { list: vi.fn().mockResolvedValue([]) },
  tagsApi: { list: vi.fn().mockResolvedValue([]) },
  urls: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
}))

describe("BulkPage", () => {
  beforeEach(() => {
    queryReturnMap.authMe = { data: { id: 1 }, isLoading: false }
    queryReturnMap.workspaces = { data: [{ id: 1, name: "Test" }], isLoading: false }
    queryReturnMap.folders = { data: [], isLoading: false }
    queryReturnMap.tags = { data: [], isLoading: false }
    queryReturnMap.urls = { data: { items: [], total: 0 }, isLoading: false }
  })

  it("renders the page title", () => {
    render(<BulkPage />)
    expect(screen.getByText("Bulk Operations")).toBeDefined()
  })

  it("shows create tab by default", () => {
    render(<BulkPage />)
    expect(screen.getAllByText("Bulk Create").length).toBeGreaterThan(0)
    expect(screen.getByText("Defaults")).toBeDefined()
    expect(screen.getByText("Export URLs")).toBeDefined()
  })

  it("renders tab buttons", () => {
    render(<BulkPage />)
    expect(screen.getByText("Create")).toBeDefined()
    expect(screen.getByText("Manage")).toBeDefined()
  })

  it("shows export button", () => {
    render(<BulkPage />)
    expect(screen.getByText("Export CSV")).toBeDefined()
  })

  it("renders textarea for URL input", () => {
    render(<BulkPage />)
    expect(screen.getByPlaceholderText(/https:\/\/example.com/)).toBeDefined()
  })
})
