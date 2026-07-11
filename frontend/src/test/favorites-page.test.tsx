import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import FavoritesPage from "@/app/(authenticated)/favorites/page"

const { mockStoreHook } = vi.hoisted(() => {
  const mockStore = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  return { mockStoreHook }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

describe("FavoritesPage", () => {

  it("renders the page title", () => {
    render(<FavoritesPage />)
    expect(screen.getByText("Favorites")).toBeDefined()
  })

  it("shows empty state when no favorites", () => {
    render(<FavoritesPage />)
    expect(screen.getByText("No favorites yet")).toBeDefined()
  })
})
