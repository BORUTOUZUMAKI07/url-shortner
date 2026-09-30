import { describe, it, expect } from "vitest"
import { render, screen } from "@/test/test-utils"
import { server } from "@/test/mocks/server"
import { http, HttpResponse } from "msw"
import FavoritesPage from "@/app/(authenticated)/favorites/page"

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

describe("FavoritesPage", () => {

  it("renders the page title", () => {
    render(<FavoritesPage />)
    expect(screen.getByText("Favorites")).toBeDefined()
  })

  // `findByText`, not `getByText`. The empty state is now behind an
  // `isPending` guard, because rendering it before the query resolved was the
  // bug: a page whose favorites had not loaded yet showed "No favorites yet"
  // and, on the first paint of every visit, told the user they had none.
  // A synchronous `getByText` passes only against that bug, so it was asserting
  // the defect rather than the intent. Every other page test in this directory
  // already awaits for the same reason.
  it("shows empty state when no favorites", async () => {
    render(<FavoritesPage />)
    expect(await screen.findByText("No favorites yet")).toBeDefined()
  })

  it("does not claim there are no favorites while the query is in flight", async () => {
    // Regression pin for the false-empty-state class of bug: the page must not
    // decide anything about the user's data before the data has arrived.
    // `retry: false` and `gcTime: 0` in test-utils mean the pending window is
    // observable — a handler that never resolves holds the query open.
    server.use(
      http.get(`${API}/favorites`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 50))
        return HttpResponse.json([])
      })
    )
    render(<FavoritesPage />)

    // Past first paint, still pending: the empty state must be absent.
    await screen.findByText("Favorites")
    expect(screen.queryByText("No favorites yet")).toBeNull()

    // Once it resolves, the honest empty state appears.
    expect(await screen.findByText("No favorites yet")).toBeDefined()
  })
})
