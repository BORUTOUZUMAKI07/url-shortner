import { describe, it, expect } from "vitest"
import { render, screen } from "@/test/test-utils"
import { server } from "@/test/mocks/server"
import { http, HttpResponse } from "msw"
import WebhooksPage from "@/app/(authenticated)/webhooks/page"

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

describe("WebhooksPage", () => {
  it("renders the page title", async () => {
    render(<WebhooksPage />)
    expect(await screen.findByText("Webhooks")).toBeDefined()
  })

  it("shows empty state when no webhooks", async () => {
    render(<WebhooksPage />)
    expect(await screen.findByText("No webhooks yet")).toBeDefined()
  })

  it("renders add webhook button", async () => {
    render(<WebhooksPage />)
    expect(await screen.findByText("Add Webhook")).toBeDefined()
  })

  it("renders receiver log link", async () => {
    render(<WebhooksPage />)
    expect(await screen.findByText("Receiver Log")).toBeDefined()
  })

  it("lists webhooks when present", async () => {
    server.use(
      http.get(`${API}/webhooks/workspace/:workspaceId`, () => {
        return HttpResponse.json([
          { id: 1, url: "https://example.com/hook", events: ["url.created"], is_active: true, created_at: "2024-01-01" },
        ])
      })
    )
    render(<WebhooksPage />)
    expect(await screen.findByText("https://example.com/hook")).toBeDefined()
    expect(screen.getByText("Active")).toBeDefined()
    expect(screen.getByText("url.created")).toBeDefined()
  })
})
