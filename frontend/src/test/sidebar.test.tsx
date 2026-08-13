import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test/test-utils"
import { Sidebar } from "@/components/layout/sidebar"

const { mockState } = vi.hoisted(() => ({
  mockState: {
    user: null as { id: number; email: string; is_superadmin: boolean } | null,
    logout: vi.fn(),
  },
}))

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}))

vi.mock("@/store/auth", () => ({
  useAuthStore: (selector?: (s: any) => any) => (selector ? selector(mockState) : mockState),
}))

describe("Sidebar", () => {
  beforeEach(() => {
    mockState.user = { id: 1, email: "test@test.com", is_superadmin: false }
  })

  it("renders brand link", () => {
    render(<Sidebar />)
    expect(screen.getByText("LinkForge")).toBeDefined()
  })

  it("renders nav items", () => {
    render(<Sidebar />)
    expect(screen.getByText("Dashboard")).toBeDefined()
    expect(screen.getByText("All URLs")).toBeDefined()
    expect(screen.getByText("Favorites")).toBeDefined()
    expect(screen.getByText("Profile")).toBeDefined()
  })

  it("renders logout button", () => {
    render(<Sidebar />)
    expect(screen.getByText("Logout")).toBeDefined()
  })

  it("renders logout button even when the user is not hydrated", () => {
    mockState.user = null
    render(<Sidebar />)
    expect(screen.getByText("Logout")).toBeDefined()
  })

  it("does not render admin link for non-superadmin", () => {
    render(<Sidebar />)
    expect(screen.queryByText("Admin")).toBeNull()
  })

  it("renders admin link for superadmin", () => {
    mockState.user = { id: 1, email: "test@test.com", is_superadmin: true }
    render(<Sidebar />)
    expect(screen.getByText("Admin")).toBeDefined()
  })

  it("highlights active nav item", () => {
    const { container } = render(<Sidebar />)
    const dashboardLink = container.querySelector('nav a[href="/dashboard"]')
    expect(dashboardLink?.className).toContain("bg-blue-500/10")
  })
})
