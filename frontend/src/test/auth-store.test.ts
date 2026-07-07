import { describe, it, expect, vi, beforeEach } from "vitest"
import { useAuthStore } from "@/store/auth"

vi.mock("@/lib/token-cookie", () => ({
  clearTokenCookies: vi.fn(),
}))

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, isLoading: true })
    localStorage.clear()
  })

  it("starts with no user and loading", () => {
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.isLoading).toBe(true)
  })

  it("setUser updates user and stops loading", () => {
    const mockUser = {
      id: 1,
      email: "test@test.com",
      is_verified: true,
      role: "admin",
      plan: "premium",
      is_superadmin: false,
      avatar_url: null,
      created_at: "2024-01-01",
    }
    useAuthStore.getState().setUser(mockUser)
    const state = useAuthStore.getState()
    expect(state.user).toEqual(mockUser)
    expect(state.isLoading).toBe(false)
  })

  it("setUser with null clears user", () => {
    useAuthStore.getState().setUser(null)
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.isLoading).toBe(false)
  })

  it("setLoading updates loading state", () => {
    useAuthStore.getState().setLoading(false)
    expect(useAuthStore.getState().isLoading).toBe(false)
    useAuthStore.getState().setLoading(true)
    expect(useAuthStore.getState().isLoading).toBe(true)
  })

  it("logout clears user and tokens", () => {
    localStorage.setItem("access_token", "test-token")
    localStorage.setItem("refresh_token", "test-refresh")
    useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(localStorage.getItem("access_token")).toBeNull()
    expect(localStorage.getItem("refresh_token")).toBeNull()
  })

  it("logout clears tokens even when no user is set", () => {
    useAuthStore.setState({ user: null, isLoading: false })
    localStorage.setItem("access_token", "orphaned-token")
    useAuthStore.getState().logout()
    expect(localStorage.getItem("access_token")).toBeNull()
  })
})
