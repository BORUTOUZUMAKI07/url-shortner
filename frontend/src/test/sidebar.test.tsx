import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { Sidebar } from "@/components/layout/sidebar"

const { mockSidebarUser, mockAuthLogout } = vi.hoisted(() => ({
  mockSidebarUser: { id: 1, email: "test@test.com", is_superadmin: false },
  mockAuthLogout: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}))

vi.mock("@/store/auth", () => ({
  useAuthStore: (selector?: (s: any) => any) => {
    const state = { user: mockSidebarUser, logout: vi.fn() }
    return selector ? selector(state) : state
  },
}))

vi.mock("@/lib/api", () => ({
  auth: { logout: mockAuthLogout },
}))

describe("Sidebar", () => {
  beforeEach(() => {
    mockSidebarUser.is_superadmin = false
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

  it("does not render admin link for non-superadmin", () => {
    render(<Sidebar />)
    expect(screen.queryByText("Admin")).toBeNull()
  })

  it("renders admin link for superadmin", () => {
    mockSidebarUser.is_superadmin = true
    render(<Sidebar />)
    expect(screen.getByText("Admin")).toBeDefined()
  })

  it("highlights active nav item", () => {
    const { container } = render(<Sidebar />)
    const dashboardLink = container.querySelector('nav a[href="/dashboard"]')
    expect(dashboardLink?.className).toContain("bg-primary/10")
  })
})
