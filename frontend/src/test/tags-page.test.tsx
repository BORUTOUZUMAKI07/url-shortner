import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import { server } from "@/test/mocks/server"
import { http, HttpResponse } from "msw"
import TagsPage from "@/app/(authenticated)/tags/page"

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

const { mockStoreHook } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  mockStoreHook.getState = () => mockStore
  return { mockStoreHook }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

describe("TagsPage", () => {
  it("renders the page title", async () => {
    render(<TagsPage />)
    expect(await screen.findByText("Tags")).toBeDefined()
  })

  it("renders create tag section", async () => {
    render(<TagsPage />)
    expect(await screen.findByText("Create Tag")).toBeDefined()
  })

  it("shows empty state when no tags", async () => {
    render(<TagsPage />)
    expect(await screen.findByText("No tags yet")).toBeDefined()
  })

  it("lists tags when present", async () => {
    server.use(
      http.get(`${API}/tags`, () => {
        return HttpResponse.json([
          { id: 1, name: "urgent", workspace_id: 1, created_at: "2024-01-01" },
        ])
      })
    )
    render(<TagsPage />)
    expect(await screen.findByText("urgent")).toBeDefined()
  })
})
