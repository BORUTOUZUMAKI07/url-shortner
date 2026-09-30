import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import WorkspacesPage from "@/app/(authenticated)/workspaces/page"
import { server } from "@/test/mocks/server"
import { http, HttpResponse, delay } from "msw"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

describe("WorkspacesPage", () => {

  it("renders the page title", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Workspaces")).toBeDefined()
  })

  it("renders create workspace section", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Create Workspace")).toBeDefined()
  })

  // Overrides /workspaces to return [] — the global handler always returns a
  // workspace, so without the override the page could never legitimately show
  // the empty state. The old test read it synchronously during the
  // query-not-yet-resolved window, passing because of the false-empty-state
  // bug (same trap as the favorites test, see AGENTS.md "Frontend Batch 2").
  it("shows empty state when no workspaces", async () => {
    server.use(
      http.get(`${API}/workspaces`, () => HttpResponse.json([]))
    )
    render(<WorkspacesPage />)
    expect(await screen.findByText("No workspaces yet")).toBeDefined()
  })

  // Pins the real invariant: while the workspaces lookup is in flight the
  // empty state must NOT be rendered — an empty workspace and a loading query
  // are different states and the page must not claim the former.
  it("does not render the empty state while workspaces are loading", async () => {
    server.use(
      http.get(`${API}/workspaces`, async () => {
        await delay(50)
        return HttpResponse.json([])
      })
    )
    render(<WorkspacesPage />)
    expect(screen.queryByText("No workspaces yet")).toBeNull()
    expect(await screen.findByText("No workspaces yet")).toBeDefined()
  })

  it("renders accept invite button", () => {
    render(<WorkspacesPage />)
    expect(screen.getByText("Accept Invite")).toBeDefined()
  })
})
