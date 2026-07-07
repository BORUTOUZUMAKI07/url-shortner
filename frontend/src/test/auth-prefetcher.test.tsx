import { describe, it, expect, vi } from "vitest"
import { render } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthPrefetcher } from "@/lib/auth-prefetcher"

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn().mockResolvedValue({ id: 1 }) },
}))

describe("AuthPrefetcher", () => {
  it("renders null", () => {
    const qc = new QueryClient()
    const { container } = render(
      <QueryClientProvider client={qc}>
        <AuthPrefetcher />
      </QueryClientProvider>
    )
    expect(container.innerHTML).toBe("")
  })
})
