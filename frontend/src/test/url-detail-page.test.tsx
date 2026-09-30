import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
import URLDetailPage from "@/app/(authenticated)/urls/[id]/page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
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
