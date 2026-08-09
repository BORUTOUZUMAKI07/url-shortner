import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import ApiKeysPage from "@/app/(authenticated)/api-keys/page"

const { mockQueries } = vi.hoisted(() => ({
  mockQueries: {
    useApiKeys: vi.fn(() => ({ data: [], isLoading: false })),
    useCreateApiKeyMutation: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  } as Record<string, any>,
}))

vi.mock("@/queries", () => mockQueries)

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiKeysPage />
    </QueryClientProvider>
  )
}

describe("ApiKeysPage", () => {
  beforeEach(() => {
    mockQueries.useApiKeys.mockReturnValue({ data: [], isLoading: false })
    mockQueries.useCreateApiKeyMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it("renders the page title", () => {
    renderPage()
    expect(screen.getByText("API Keys")).toBeDefined()
  })

  it("shows empty state when no keys", () => {
    renderPage()
    expect(screen.getByText(/No API keys yet/)).toBeDefined()
  })

  it("renders create button", () => {
    renderPage()
    expect(screen.getByText("Create Key")).toBeDefined()
  })

  it("renders input for key name", () => {
    renderPage()
    expect(screen.getByPlaceholderText(/Key name/)).toBeDefined()
  })

  it("lists API keys when present", () => {
    mockQueries.useApiKeys.mockReturnValueOnce({
      data: [{ id: 1, name: "Test Key", prefix: "lk_abc", status: "active", expires_at: null, last_used_at: null, created_at: "2024-01-01" }],
      isLoading: false,
    })
    renderPage()
    expect(screen.getByText("Test Key")).toBeDefined()
    expect(screen.getByText(/lk_abc/)).toBeDefined()
  })

  it("shows loading state", () => {
    mockQueries.useApiKeys.mockReturnValueOnce({ data: [], isLoading: true })
    renderPage()
    expect(screen.getByText("Loading...")).toBeDefined()
  })
})
