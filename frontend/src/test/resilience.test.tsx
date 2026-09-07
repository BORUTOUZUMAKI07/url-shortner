import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { http, HttpResponse } from "msw"
import { server } from "./mocks/server"
import ApiKeysPage from "@/app/(authenticated)/api-keys/page"
import FavoritesPage from "@/app/(authenticated)/favorites/page"
import URLDetailPage from "@/app/(authenticated)/urls/[id]/page"
import CreateURLPage from "@/app/(authenticated)/urls/new/page"
import type { ReactNode } from "react"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useParams: () => ({ id: "1" }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}))

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

const serverError = (detail = "boom") => HttpResponse.json({ detail }, { status: 500 })

describe("resilience: list queries surface API 500s without crashing", () => {
  it("api-keys page shows the error state and a working retry button", async () => {
    server.use(http.get("/api/v1/api-keys", () => serverError()))
    renderWithClient(<ApiKeysPage />)

    expect(await screen.findByText("Failed to load API keys")).toBeDefined()
    const retry = screen.getByRole("button", { name: "Try again" })
    fireEvent.click(retry)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Try again" })).toBeDefined()
    })
  })

  it("favorites page shows the error banner when the favorites fetch fails", async () => {
    server.use(http.get("/api/v1/favorites", () => serverError()))
    renderWithClient(<FavoritesPage />)

    expect(await screen.findByText("Failed to load favorites")).toBeDefined()
    const retry = screen.getByRole("button", { name: "Try again" })
    fireEvent.click(retry)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Try again" })).toBeDefined()
    })
  })

  it("url detail page shows the error state when the URL fetch fails", async () => {
    server.use(http.get("/api/v1/urls/1", () => serverError()))
    renderWithClient(<URLDetailPage />)

    expect(await screen.findByRole("button", { name: "Try again" })).toBeDefined()
    const retry = screen.getByRole("button", { name: "Try again" })
    fireEvent.click(retry)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Try again" })).toBeDefined()
    })
  })
})

describe("resilience: create mutation surfaces a failed request", () => {
  it("create-short-url form shows the server error instead of navigating", async () => {
    server.use(http.post("/api/v1/urls", () => serverError("Server exploded")))
    renderWithClient(<CreateURLPage />)

    const submit = await waitFor(() => {
      const button = screen.getByRole("button", { name: "Create URL" })
      expect(button).toBeEnabled()
      return button
    })
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example\.com/), {
      target: { value: "https://example.com/failing-create" },
    })
    fireEvent.click(submit)

    expect(await screen.findByText("Server exploded")).toBeDefined()
  })
})