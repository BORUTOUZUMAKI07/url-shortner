import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import WorkspacesPage from "@/app/(authenticated)/workspaces/page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

describe("WorkspacesPage", () => {

  it("renders the page title", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Workspaces")).toBeDefined()
  })

  it("renders create workspace section", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Create Workspace")).toBeDefined()
  })

  it("shows empty state when no workspaces", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("No workspaces yet")).toBeDefined()
  })

  it("renders accept invite button", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Accept Invite")).toBeDefined()
  })
})
