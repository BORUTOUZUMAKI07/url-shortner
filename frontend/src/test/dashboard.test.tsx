import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import DashboardPage from "@/app/(authenticated)/dashboard/page"

const { mockDashboard } = vi.hoisted(() => {
  const state = { urlList: [] as any[], totalUrlsCount: 0 }
  return {
    mockDashboard: state,
  }
})

vi.mock("@/hooks/useDashboard", () => ({
  useDashboard: () => ({
    urlList: mockDashboard.urlList,
    totalUrlsCount: mockDashboard.totalUrlsCount,
    workspaces: [],
    wsId: null,
    error: null,
    quota: null,
    canEdit: true,
    activeUrls: [],
    isLoading: false,
    setWsId: vi.fn(),
  }),
}))

vi.mock("@/queries", () => ({
  useMe: () => ({ data: { id: 1, email: "test@test.com" } }),
  useWorkspaces: () => ({ data: [] }),
  useWorkspaceMembers: () => ({ data: [] }),
  useUrls: () => ({ data: { items: [], total: 0 }, error: null }),
  useFolders: () => ({ data: [] }),
  useTags: () => ({ data: [] }),
  useFavorites: () => ({ data: [] }),
  useDeleteUrlMutation: () => ({ mutate: vi.fn(), mutateAsync: vi.fn() }),
  useAddFavoriteMutation: () => ({ mutate: vi.fn() }),
  useRemoveFavoriteMutation: () => ({ mutate: vi.fn() }),
  useApiKeys: () => ({ data: [], isLoading: false }),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

describe("DashboardPage", () => {
  beforeEach(() => {
    document.title = ""
    mockDashboard.urlList = []
    mockDashboard.totalUrlsCount = 0
  })

  it("renders dashboard welcome", () => {
    render(<DashboardPage />)
    expect(screen.getByText(/Welcome back/i)).toBeDefined()
  })

  it("renders stats cards", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Total URLs")).toBeDefined()
    expect(screen.getByText("Active")).toBeDefined()
  })

  it("shows view all link", () => {
    mockDashboard.urlList = [{ id: 1, short_code: "abc", original_url: "https://example.com", status: "active", is_one_time: false, tags: [] }]
    mockDashboard.totalUrlsCount = 1
    render(<DashboardPage />)
    expect(screen.getByText("View all")).toBeDefined()
  })

  it("shows no URLs message when empty", () => {
    render(<DashboardPage />)
    expect(screen.getByText(/No URLs yet/i)).toBeDefined()
  })

  it("sets document title", () => {
    render(<DashboardPage />)
    expect(document.title).toBe("Dashboard - LinkForge")
  })
})
