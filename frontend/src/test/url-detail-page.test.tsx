import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import URLDetailPage from "@/app/(authenticated)/urls/[id]/page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({
  useAuthStore: (selector?: (s: any) => any) => {
    const state = { user: { id: 1 }, setUser: vi.fn(), logout: vi.fn() }
    return selector ? selector(state) : state
  },
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn().mockResolvedValue({ id: 1, email: "test@test.com" }) },
  urls: {
    get: vi.fn().mockResolvedValue({ id: 1, short_code: "abc", original_url: "https://example.com", workspace_id: 1, folder_id: null, tags: [], status: "active", is_one_time: false, is_ab_test: false, ios_url: null, android_url: null, custom_alias: null, domain: null, expires_at: null, qr_code: null, created_at: "2024-01-01T00:00:00Z" }),
    update: vi.fn(),
    getQr: vi.fn().mockResolvedValue({ qr_code: "" }),
  },
  foldersApi: { list: vi.fn().mockResolvedValue([]) },
  tagsApi: { list: vi.fn().mockResolvedValue([]) },
  getErrorMessage: vi.fn((e) => e instanceof Error ? e.message : "Error"),
}))

const mockQueryClient = { invalidateQueries: vi.fn() }

const { queryReturnMap } = vi.hoisted(() => ({
  queryReturnMap: {
    authMe: { data: { id: 1, email: "test@test.com" }, isLoading: false },
    url: { data: { id: 1, short_code: "abc", original_url: "https://example.com", workspace_id: 1, folder_id: null, tags: [], status: "active", is_one_time: false, is_ab_test: false, ios_url: null, android_url: null, custom_alias: null, domain: null, expires_at: null, qr_code: null, created_at: "2024-01-01T00:00:00Z" }, isLoading: false },
    folders: { data: [], isLoading: false },
    tags: { data: [], isLoading: false },
  } as Record<string, any>,
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "authMe") return queryReturnMap.authMe
    if (queryKey[0] === "url") return queryReturnMap.url
    if (queryKey[0] === "folders") return queryReturnMap.folders
    if (queryKey[0] === "tags") return queryReturnMap.tags
    return { data: null, isLoading: true }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

describe("URLDetailPage", () => {
  beforeEach(() => {
    queryReturnMap.authMe = { data: { id: 1, email: "test@test.com" }, isLoading: false }
    queryReturnMap.url = { data: { id: 1, short_code: "abc", original_url: "https://example.com", workspace_id: 1, folder_id: null, tags: [], status: "active", is_one_time: false, is_ab_test: false, ios_url: null, android_url: null, custom_alias: null, domain: null, expires_at: null, qr_code: null, created_at: "2024-01-01T00:00:00Z" }, isLoading: false }
    queryReturnMap.folders = { data: [], isLoading: false }
    queryReturnMap.tags = { data: [], isLoading: false }
  })

  it("renders the page title", () => {
    render(<URLDetailPage />)
    expect(screen.getByText("URL Details")).toBeDefined()
  })

  it("shows the short code", () => {
    render(<URLDetailPage />)
    expect(screen.getByText("/abc")).toBeDefined()
  })

  it("shows url info", () => {
    render(<URLDetailPage />)
    expect(screen.getByText("Short Code")).toBeDefined()
    expect(screen.getByText("Info")).toBeDefined()
    expect(screen.getByText("Edit URL")).toBeDefined()
  })

  it("shows QR code section", () => {
    render(<URLDetailPage />)
    expect(screen.getByText("QR Code")).toBeDefined()
  })

  it("shows status badge", () => {
    render(<URLDetailPage />)
    expect(screen.getByText("active")).toBeDefined()
  })

  it("shows created date", () => {
    render(<URLDetailPage />)
    expect(screen.getByText(/1\/1\/2024/)).toBeDefined()
  })
})
