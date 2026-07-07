import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
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

const mockQueryClient = { invalidateQueries: vi.fn() }

let queryReturnMap: Record<string, any> = {
  authMe: { data: { id: 1 }, isLoading: false },
  workspaces: { data: [{ id: 1, name: "Test" }], isLoading: false },
  webhook_events: { data: [], refetch: vi.fn() },
}

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "authMe") return queryReturnMap.authMe
    if (queryKey[0] === "workspaces") return queryReturnMap.workspaces
    if (queryKey[0] === "webhook_events") return queryReturnMap.webhook_events
    return { data: [], isLoading: false }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => mockQueryClient),
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn() },
  webhookReceiverApi: { list: vi.fn().mockResolvedValue([]) },
  workspacesApi: { list: vi.fn().mockResolvedValue([{ id: 1, name: "Test" }]) },
}))

describe("WebhookReceiverPage", () => {
  beforeEach(() => {
    queryReturnMap = {
      authMe: { data: { id: 1 }, isLoading: false },
      workspaces: { data: [{ id: 1, name: "Test" }], isLoading: false },
      webhook_events: { data: [], refetch: vi.fn() },
    }
  })

  it("renders the page title", () => {
    render(<WebhookReceiverPage />)
    expect(screen.getByText("Webhook Receiver")).toBeDefined()
  })

  it("shows receiver URL section", () => {
    render(<WebhookReceiverPage />)
    expect(screen.getByText("Receiver URL")).toBeDefined()
  })

  it("shows empty state when no events", () => {
    render(<WebhookReceiverPage />)
    expect(screen.getByText("No events received yet")).toBeDefined()
  })
})
