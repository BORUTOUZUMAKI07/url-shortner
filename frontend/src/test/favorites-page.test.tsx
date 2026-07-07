import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import FavoritesPage from "@/app/(authenticated)/favorites/page"

const { mockStoreHook, queryReturnMap, mockQueryClient } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  const queryReturnMap: Record<string, any> = {
    authMe: { data: { id: 1 }, isLoading: false },
    favorites: { data: [], isLoading: false },
  }
  const mockQueryClient = { invalidateQueries: vi.fn() }
  return { mockStoreHook, queryReturnMap, mockQueryClient }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "authMe") return queryReturnMap.authMe
    if (queryKey[0] === "favorites") return queryReturnMap.favorites
    return { data: [], isLoading: false }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn() },
  favoritesApi: { list: vi.fn().mockResolvedValue([]) },
  urls: { get: vi.fn() },
}))

describe("FavoritesPage", () => {
  beforeEach(() => {
    queryReturnMap.authMe = { data: { id: 1 }, isLoading: false }
    queryReturnMap.favorites = { data: [], isLoading: false }
  })

  it("renders the page title", () => {
    render(<FavoritesPage />)
    expect(screen.getByText("Favorites")).toBeDefined()
  })

  it("shows empty state when no favorites", () => {
    render(<FavoritesPage />)
    expect(screen.getByText("No favorites yet")).toBeDefined()
  })
})
