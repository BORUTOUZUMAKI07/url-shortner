import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test/test-utils"
import AdminPage from "@/app/(authenticated)/admin/page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

const { mockSuperadmin, mockStore, mockStoreHook } = vi.hoisted(() => {
  const mockSuperadmin = { id: 1, email: "admin@test.com", is_superadmin: true, is_verified: true, is_active: true, plan: "enterprise", avatar_url: null, created_at: "2024-01-01" }
  const mockStore = { user: mockSuperadmin, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  mockStoreHook.getState = () => mockStore
  return { mockSuperadmin, mockStore, mockStoreHook }
})

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

describe("AdminPage", () => {
  beforeEach(() => {
    mockStore.user = mockSuperadmin
  })

  it("renders the page title", async () => {
    render(<AdminPage />)
    expect(await screen.findByText("Admin Panel")).toBeDefined()
  })

  it("renders stats tab", async () => {
    render(<AdminPage />)
    expect(await screen.findByText("Stats")).toBeDefined()
  })

  it("renders users tab", async () => {
    render(<AdminPage />)
    expect(await screen.findByText(/Users/)).toBeDefined()
  })

  it("displays stat cards with data", async () => {
    render(<AdminPage />)
    expect(await screen.findByText("10")).toBeDefined()
    expect(await screen.findByText("5")).toBeDefined()
    expect(await screen.findByText("100")).toBeDefined()
  })

  it("shows superadmin badge", async () => {
    render(<AdminPage />)
    expect(await screen.findByText("Superadmin")).toBeDefined()
  })
})
