import { describe, it, expect, vi } from "vitest"
import { render, screen, waitFor } from "@/test/test-utils"
import LoginPage from "@/app/login/page"
import { server } from "@/test/mocks/server"
import { http, HttpResponse, delay } from "msw"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/login",
}))

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

// The social buttons used to be hardcoded: a provider whose secret was unset
// still rendered, and the flow only failed after a full consent round trip at
// token exchange. Now the page renders a button for exactly the providers the
// backend advertises as fully configured (id AND secret).
describe("LoginPage OAuth buttons", () => {
  it("renders both provider buttons when both are configured", async () => {
    server.use(
      http.get(`${API}/auth/providers`, () =>
        HttpResponse.json({ providers: ["google", "github"] })
      )
    )
    render(<LoginPage />)
    expect(await screen.findByRole("button", { name: "Google" })).toBeDefined()
    expect(screen.getByRole("button", { name: "GitHub" })).toBeDefined()
  })

  it("renders only the providers the backend reports as configured", async () => {
    server.use(
      http.get(`${API}/auth/providers`, () =>
        HttpResponse.json({ providers: ["google"] })
      )
    )
    render(<LoginPage />)
    expect(await screen.findByRole("button", { name: "Google" })).toBeDefined()
    expect(screen.queryByRole("button", { name: "GitHub" })).toBeNull()
  })

  it("hides the social section when no provider is configured", async () => {
    server.use(
      http.get(`${API}/auth/providers`, () =>
        HttpResponse.json({ providers: [] })
      )
    )
    render(<LoginPage />)
    expect(await screen.findByRole("button", { name: "Sign In" })).toBeDefined()
    await waitFor(() => expect(screen.queryByText("Or continue with")).toBeNull())
  })

  // Pins the invariant: while the providers lookup is in flight, no button may
  // claim a working flow — a hidden button is never a lie.
  it("shows no provider button while the check is in flight", async () => {
    server.use(
      http.get(`${API}/auth/providers`, async () => {
        await delay(50)
        return HttpResponse.json({ providers: ["google", "github"] })
      })
    )
    render(<LoginPage />)
    expect(screen.queryByRole("button", { name: "Google" })).toBeNull()
    expect(await screen.findByRole("button", { name: "Google" })).toBeDefined()
  })
})