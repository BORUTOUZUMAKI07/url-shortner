import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
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

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn().mockResolvedValue(mockUser) },
  billingApi: { upgrade: vi.fn() },
  getErrorMessage: vi.fn((e) => e instanceof Error ? e.message : "Error"),
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(() => ({ data: mockUser, isLoading: false })),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false, variables: null })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}))

describe("BillingPage", () => {
  beforeEach(() => {
    mockStore.user = mockUser
  })

  it("renders the page title", () => {
    render(<BillingPage />)
    expect(screen.getByText("Billing & Plans")).toBeDefined()
  })

  it("shows current plan", () => {
    render(<BillingPage />)
    expect(screen.getByText("free")).toBeDefined()
  })

  it("renders all plan cards", () => {
    render(<BillingPage />)
    expect(screen.getByText("Free")).toBeDefined()
    expect(screen.getByText("Pro")).toBeDefined()
    expect(screen.getByText("Enterprise")).toBeDefined()
  })

  it("renders back button", () => {
    render(<BillingPage />)
    expect(screen.getByText("Back")).toBeDefined()
  })

  it("shows upgrade buttons for non-current plans", () => {
    render(<BillingPage />)
    const buttons = screen.getAllByText("Upgrade")
    expect(buttons.length).toBeGreaterThanOrEqual(2)
  })

  it("shows Current badge on the free plan", () => {
    render(<BillingPage />)
    expect(screen.getByText("Current")).toBeDefined()
  })
})
