import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import { server } from "@/test/mocks/server"
import { http, HttpResponse } from "msw"
import URLDetailPage from "@/app/(authenticated)/urls/[id]/page"

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({
  useAuthStore: (selector?: (s: any) => any) => {
    const state = { user: { id: 1 }, setUser: vi.fn(), logout: vi.fn() }
    return selector ? selector(state) : state
  },
}))

describe("URLDetailPage", () => {
  it("renders the page title", async () => {
    render(<URLDetailPage />)
    expect(await screen.findByText("URL Details")).toBeDefined()
  })

  it("shows the short code", async () => {
    render(<URLDetailPage />)
    expect(await screen.findByText("/abc123")).toBeDefined()
  })

  it("shows url info", async () => {
    render(<URLDetailPage />)
    expect(await screen.findByText("Short Code")).toBeDefined()
    expect(screen.getByText("Info")).toBeDefined()
    expect(screen.getByText("Edit URL")).toBeDefined()
  })

  it("shows QR code section", async () => {
    render(<URLDetailPage />)
    expect(await screen.findByText("QR Code")).toBeDefined()
  })

  it("shows status badge", async () => {
    render(<URLDetailPage />)
    expect(await screen.findByText("active")).toBeDefined()
  })

  it("shows created date", async () => {
    render(<URLDetailPage />)
    expect(await screen.findByText(/1\/1\/2024/)).toBeDefined()
  })
})
