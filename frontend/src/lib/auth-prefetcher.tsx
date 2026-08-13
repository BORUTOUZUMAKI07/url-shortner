"use client"

import { useQuery } from "@tanstack/react-query"
import { auth } from "@/lib/api"
import { useAuthStore } from "@/store/auth"

export function AuthPrefetcher() {
  const setUser = useAuthStore((s) => s.setUser)

  // Layout-level hydration: pages like /dashboard never call auth.me()/setUser
  // themselves (they only read `user`), so landing directly on them via the
  // proxy bounce (/login -> /dashboard for an already-signed-in user) left the
  // store empty and the sidebar rendered no user/logout section. Resolving
  // ["me"] here populates the store on every authenticated page.
  useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const user = await auth.me()
      setUser(user)
      return user
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  return null
}
