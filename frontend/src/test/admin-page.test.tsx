import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import AdminPage from "@/app/(authenticated)/admin/page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

const { mockSuperadmin, mockStore, mockStoreHook } = vi.hoisted(() => {
  const mockSuperadmin = { id: 1, email: "admin@test.com", is_superadmin: true, is_verified: true, role: "admin", plan: "enterprise", avatar_url: null, created_at: "2024-01-01" }
  const mockStore = { user: mockSuperadmin, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  mockStoreHook.getState = () => mockStore
  return { mockSuperadmin, mockStore, mockStoreHook }
})

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn().mockResolvedValue(mockSuperadmin) },
  adminApi: {
    stats: vi.fn().mockResolvedValue({ total_users: 10, total_workspaces: 5, total_urls: 100 }),
    listUsers: vi.fn().mockResolvedValue({ total: 1, users: [{ id: 1, email: "admin@test.com", is_superadmin: true, is_verified: true, role: "admin", plan: "enterprise", avatar_url: null, created_at: "2024-01-01" }] }),
    toggleSuperadmin: vi.fn(),
    deleteUser: vi.fn(),
  },
}))

describe("AdminPage", () => {
  beforeEach(() => {
    mockStore.user = mockSuperadmin
  })

  it("renders the page title", () => {
    render(<AdminPage />)
    expect(screen.getByText("Admin Panel")).toBeDefined()
  })

  it("renders stats tab", () => {
    render(<AdminPage />)
    expect(screen.getByText("Stats")).toBeDefined()
  })

  it("renders users tab", () => {
    render(<AdminPage />)
    expect(screen.getByText(/Users/)).toBeDefined()
  })

  it("displays stat cards with data", async () => {
    render(<AdminPage />)
    expect(await screen.findByText("10")).toBeDefined()
    expect(await screen.findByText("5")).toBeDefined()
    expect(await screen.findByText("100")).toBeDefined()
  })

  it("shows superadmin badge", () => {
    render(<AdminPage />)
    expect(screen.getByText("Superadmin")).toBeDefined()
  })
})
