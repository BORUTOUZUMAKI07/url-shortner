import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import AdminPage from "@/app/(authenticated)/admin/page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

const { mockSuperadmin } = vi.hoisted(() => {
  const mockSuperadmin = { id: 1, email: "admin@test.com", is_superadmin: true, is_verified: true, is_active: true, plan: "enterprise", avatar_url: null, created_at: "2024-01-01" }
  return { mockSuperadmin }
})

// The page reads the user from the shared ["me"] cache via useMe.
vi.mock("@/queries", () => ({
  useMe: () => ({ data: mockSuperadmin }),
}))

describe("AdminPage", () => {

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
