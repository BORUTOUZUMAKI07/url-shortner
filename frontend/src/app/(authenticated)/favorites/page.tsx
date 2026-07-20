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

  const { data: urlsData = [] } = useQuery({
    queryKey: ["favorites"],
    queryFn: async () => {
      const favs = await favoritesApi.list()
      const results = await Promise.allSettled(favs.map((f) => urls.get(f.url_id)))
      return results
        .filter(r => r.status === "fulfilled")
        .map(r => (r as PromiseFulfilledResult<URLItem>).value)
    },
    enabled: !authLoading
  })

  const removeMutation = useMutation({
    mutationFn: (url_id: number) => favoritesApi.remove(url_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] })
    }
  })

  async function handleRemove(url_id: number) {
    removeMutation.mutate(url_id)
  }

  const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace("/api/v1", "") || "http://127.0.0.1:8000"

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Favorites</h1>
        <p className="text-sm text-muted-foreground">Your bookmarked URLs.</p>
      </div>

      {urlsData.length === 0 ? (
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
