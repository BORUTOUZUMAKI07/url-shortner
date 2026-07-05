import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import URLsPage from "@/app/(authenticated)/urls/page"

vi.mock("@/queries", () => ({
  useMe: () => ({ data: { id: 1, email: "test@test.com" } }),
  useWorkspaces: () => ({ data: [{ id: 1, name: "Test Workspace" }] }),
  useWorkspaceMembers: () => ({ data: [{ user_id: 1, role: "admin" }] }),
  useUrls: () => ({
    data: {
      items: [
        {
          id: 1,
          short_code: "abc123",
          original_url: "https://example.com",
          status: "active",
          is_one_time: false,
          tags: [],
        },
      ],
      total: 1,
    },
    error: null,
  }),
  useFolders: () => ({ data: [] }),
  useTags: () => ({ data: [] }),
  useFavorites: () => ({ data: [] }),
  useDeleteUrlMutation: () => ({ mutate: vi.fn() }),
  useAddFavoriteMutation: () => ({ mutate: vi.fn() }),
  useRemoveFavoriteMutation: () => ({ mutate: vi.fn() }),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))

describe("URLsPage", () => {
  it("renders the page title", () => {
    render(<URLsPage />)
    expect(screen.getByText("URLs")).toBeDefined()
  })

  it("shows filter options", () => {
    render(<URLsPage />)
    expect(screen.getByText("All workspaces")).toBeDefined()
    expect(screen.getByText("All folders")).toBeDefined()
    expect(screen.getByText("All tags")).toBeDefined()
  })

  it("renders URL list items", () => {
    render(<URLsPage />)
    expect(screen.getByText("abc123")).toBeDefined()
  })

  it("sets document title", () => {
    document.title = ""
    render(<URLsPage />)
    expect(document.title).toBe("URLs - LinkForge")
  })
})
