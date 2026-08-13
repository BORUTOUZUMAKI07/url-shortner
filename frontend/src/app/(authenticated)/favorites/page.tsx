"use client"

import { useRouter } from "next/navigation"
import Link from "next/link"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { auth, favoritesApi, urls, URLItem } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Heart, ExternalLink, BarChart3, HeartOff } from "lucide-react"

export default function FavoritesPage() {
  const router = useRouter()
  const { setUser } = useAuthStore()
  const queryClient = useQueryClient()

  const { isLoading: authLoading } = useQuery({
    queryKey: ["authMe"],
    queryFn: async () => {
      try {
        const user = await auth.me()
        setUser(user)
        return user
      } catch (err) {
        router.push("/login")
        throw err
      }
    },
    retry: false
  })

  const { data: urlsData = [], isError: urlsError, refetch: refetchFavorites } = useQuery({
    // Distinct key from the ["favorites"] used by useFavorites (which returns
    // Favorite[]); this one resolves to URLItem[]. Sharing a key made the two
    // shapes swap with the last-mounted page.
    queryKey: ["favorites-with-urls"],
    queryFn: async () => {
      const favs = await favoritesApi.list(0, 100)
      if (favs.length === 0) return []
      const ids = favs.map((f) => f.url_id).join(",")
      const { items } = await urls.list(null, { ids })
      const byId = new Map(items.map((u) => [u.id, u]))
      return favs
        .map((f) => byId.get(f.url_id))
        .filter((u): u is URLItem => !!u)
    },
    enabled: !authLoading
  })

  const removeMutation = useMutation({
    mutationFn: (url_id: number) => favoritesApi.remove(url_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] })
      queryClient.invalidateQueries({ queryKey: ["favorites-with-urls"] })
    }
  })

  async function handleRemove(url_id: number) {
    removeMutation.mutate(url_id)
  }

  const baseUrl = typeof window !== "undefined" ? window.location.origin : ""

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Favorites</h1>
        <p className="text-sm text-muted-foreground">Your bookmarked URLs.</p>
      </div>

      {urlsError ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-12 text-center">
          <Heart className="mx-auto mb-3 size-10 text-red-400" />
          <p className="text-lg font-medium">Failed to load favorites</p>
          <p className="mt-1 text-sm text-muted-foreground">Something went wrong while fetching your bookmarks.</p>
          <Button variant="outline" className="mt-4" onClick={() => refetchFavorites()}>Try again</Button>
        </div>
      ) : urlsData.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
          <Heart className="mx-auto mb-3 size-10 text-muted-foreground" />
          <p className="text-lg font-medium">No favorites yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Bookmark URLs from the URLs page.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {urlsData.map((url) => (
            <div key={url.id} className="flex flex-col gap-2 rounded-lg border bg-card px-4 py-3 transition-colors hover:bg-muted/50 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Heart className="size-3.5 text-red-400 shrink-0" />
                  <a href={`${baseUrl}/${url.short_code}`} target="_blank" className="text-sm font-medium text-blue-400 hover:underline break-all">
                    {url.short_code} <ExternalLink className="inline size-3" />
                  </a>
                  <Badge variant={url.status === "active" ? "success" : "secondary"}>{url.status}</Badge>
                  {url.is_one_time && <Badge variant="warning">One-time</Badge>}
                </div>
                <p className="truncate text-xs text-muted-foreground">{url.original_url}</p>
              </div>
              <div className="flex items-center gap-1">
                <Link href={`/urls/${url.id}/analytics`}>
                  <Button variant="ghost" size="xs"><BarChart3 className="size-3.5" /></Button>
                </Link>
                <Button variant="ghost" size="xs" onClick={() => handleRemove(url.id)}>
                  <HeartOff className="size-3.5 text-destructive" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
