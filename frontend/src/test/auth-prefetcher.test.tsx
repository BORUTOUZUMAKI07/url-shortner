import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, waitFor, act } from "@/test/test-utils"
import { AuthPrefetcher } from "@/lib/auth-prefetcher"
import { useAuthStore } from "@/store/auth"
import { auth } from "@/lib/api"

const mockUser = {
  id: 1,
  email: "test@example.com",
  is_verified: true,
  role: "admin",
  plan: "free",
  is_superadmin: false,
  avatar_url: null,
  created_at: "2026-01-01T00:00:00Z",
}

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn() },
}))

describe("AuthPrefetcher", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, isLoading: true })
    vi.mocked(auth.me).mockReset()
    vi.mocked(auth.me).mockResolvedValue(mockUser)
  })

  it("renders null", () => {
    const { container } = render(<AuthPrefetcher />)
    expect(container.innerHTML).toBe("")
  })

  it("hydrates the auth store with the current user", async () => {
    render(<AuthPrefetcher />)
    await waitFor(() => expect(useAuthStore.getState().user?.email).toBe("test@example.com"))
  })

  it("leaves the store empty when the user cannot be loaded", async () => {
    vi.mocked(auth.me).mockRejectedValue(new Error("Request failed"))
    render(<AuthPrefetcher />)
    await act(async () => { await new Promise((r) => setTimeout(r, 20)) })
    expect(useAuthStore.getState().user).toBeNull()
  })
})
