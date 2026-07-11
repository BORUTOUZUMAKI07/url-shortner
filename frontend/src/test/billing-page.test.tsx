import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test/test-utils"
import BillingPage from "@/app/(authenticated)/billing/page"

const { mockUser, mockStore, mockStoreHook } = vi.hoisted(() => {
  const mockUser = { id: 1, email: "test@test.com", is_verified: true, role: "admin", plan: "free", is_superadmin: false, avatar_url: null, created_at: "2024-01-01" }
  const mockStore = { user: mockUser, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  mockStoreHook.getState = () => mockStore
  return { mockUser, mockStore, mockStoreHook }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

describe("BillingPage", () => {
  beforeEach(() => {
    mockStore.user = mockUser
  })

  it("renders the page title", async () => {
    render(<BillingPage />)
    expect(await screen.findByText("Billing & Plans")).toBeDefined()
  })

  it("shows current plan", async () => {
    render(<BillingPage />)
    expect(await screen.findByText("free")).toBeDefined()
  })

  it("renders all plan cards", async () => {
    render(<BillingPage />)
    expect(await screen.findByText("Free")).toBeDefined()
    expect(screen.getByText("Pro")).toBeDefined()
    expect(screen.getByText("Enterprise")).toBeDefined()
  })

  it("renders back button", async () => {
    render(<BillingPage />)
    expect(await screen.findByText("Back")).toBeDefined()
  })

  it("shows upgrade buttons for non-current plans", async () => {
    render(<BillingPage />)
    const buttons = await screen.findAllByText("Upgrade")
    expect(buttons.length).toBeGreaterThanOrEqual(2)
  })

  it("shows Current badge on the free plan", async () => {
    render(<BillingPage />)
    expect(await screen.findByText("Current")).toBeDefined()
  })
})
