import { describe, it, expect, vi } from "vitest"
import { render, screen, waitFor } from "@/test/test-utils"
import WebhookReceiverPage from "@/app/(authenticated)/webhooks/receiver/page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({
  useAuthStore: (selector?: (s: any) => any) => {
    const state = { user: { id: 1, email: "test@test.com" }, setUser: vi.fn() }
    return selector ? selector(state) : state
  },
}))

describe("WebhookReceiverPage", () => {
  it("renders the page title", async () => {
    render(<WebhookReceiverPage />)
    await waitFor(() => {
      expect(screen.getByText("Webhook Receiver")).toBeDefined()
    })
  })

  it("shows receiver URL section", async () => {
    render(<WebhookReceiverPage />)
    await waitFor(() => {
      expect(screen.getByText("Receiver URL")).toBeDefined()
    })
  })

  it("shows empty state when no events", async () => {
    render(<WebhookReceiverPage />)
    await waitFor(() => {
      expect(screen.getByText("No events received yet")).toBeDefined()
    })
  })
})
