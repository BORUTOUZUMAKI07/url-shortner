import { create } from "zustand"

// Re-exported rather than redeclared: this used to be a second, hand-copied
// copy of the API's User interface, so the two silently drifted (the store
// still required `role` after the API stopped sending it, breaking every
// setUser call site at the type level).
export type { User } from "@/lib/api"
import type { User } from "@/lib/api"

interface AuthState {
  user: User | null
  isLoading: boolean
  setUser: (user: User | null) => void
  setLoading: (loading: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  setUser: (user) => set({ user, isLoading: false }),
  setLoading: (isLoading) => set({ isLoading }),
  logout: () => {
    set({ user: null })
  },
}))