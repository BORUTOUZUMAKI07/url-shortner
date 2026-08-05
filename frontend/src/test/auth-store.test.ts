import { describe, it, expect, vi, beforeEach } from "vitest"
import { useAuthStore } from "@/store/auth"

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, isLoading: true })
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

  it("logout clears user", () => {
    useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
  })

  it("logout clears user even when user was set", () => {
    useAuthStore.setState({ user: { id: 1, email: "test@test.com", is_verified: true, role: "admin", plan: "free", is_superadmin: false, avatar_url: null, created_at: "2024-01-01" }, isLoading: false })
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().user).toBeNull()
  })
})