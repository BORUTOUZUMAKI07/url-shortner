"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { useMe, useWorkspaces, useWorkspaceMembers, useUrls, useFolders, useTags, useFavorites, useDeleteUrlMutation, useAddFavoriteMutation, useRemoveFavoriteMutation } from "@/queries"
import { Search, ExternalLink, Trash2, BarChart3, Heart, Tags, Link2, Plus, X, Copy } from "lucide-react"
import { buildShortUrl, buildShareableShortUrl } from "@/lib/utils"
import { toast } from "sonner"

export default function URLsPage() {
  useEffect(() => { document.title = "URLs - LinkForge" }, [])
  useMe()
  const { data: workspaces = [] } = useWorkspaces()
  const [wsId, setWsId] = useState<number | null>(null)

  useWorkspaceMembers(wsId)
  const { data: folders = [] } = useFolders(wsId)
  const { data: allTags = [] } = useTags(wsId)
  const { data: favorites = [] } = useFavorites()
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [folderFilter, setFolderFilter] = useState("")
  const [tagFilter, setTagFilter] = useState("")
  const { data: urlsData, error: urlsError, isPending: urlsPending } = useUrls(wsId, {
    search: debouncedSearch || undefined,
    folder_id: folderFilter ? Number(folderFilter) : undefined,
    tag: tagFilter || undefined,
    limit: 50,
  })
  const items = urlsData?.items || []

  const deleteUrl = useDeleteUrlMutation()
  const addFavorite = useAddFavoriteMutation()
  const removeFavorite = useRemoveFavoriteMutation()
  const favoriteSet = new Set(favorites.map((f) => f.url_id))

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const error = urlsError instanceof Error ? urlsError.message : ""

  const hasFilters = !!(search || folderFilter || tagFilter)
  const clearFilters = () => { setSearch(""); setFolderFilter(""); setTagFilter("") }

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600">
          <Link2 className="size-4.5" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-semibold tracking-tight">URLs</h1>
          <p className="text-sm text-stone-500">Manage your short links.</p>
        </div>
        </div>
        <Link href="/urls/new">
          <Button className="bg-emerald-600 text-white hover:bg-emerald-700">
            <Plus className="mr-1.5 size-4" />New URL
          </Button>
        </Link>
      </div>

      <div className="mb-4 rounded-lg border border-stone-200/50 p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-stone-500" />
            <Input
              placeholder="Search by original URL or short code..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="border-stone-300/50 pl-9 text-sm placeholder:text-stone-500 focus:border-stone-300"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Select value={String(wsId ?? "")} onChange={(e) => setWsId(e.target.value ? Number(e.target.value) : null)} className="w-full sm:w-36">
              <option value="">All workspaces</option>
              {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
            <Select value={folderFilter} onChange={(e) => setFolderFilter(e.target.value)} className="w-full sm:w-32">
              <option value="">All folders</option>
              {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </Select>
            <Select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} className="w-full sm:w-32">
              <option value="">All tags</option>
              {allTags.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
            </Select>
          </div>
        </div>
        {hasFilters && (
          <div className="mt-3 flex items-center gap-2 border-t border-stone-200/50 pt-3">
            <span className="text-xs text-stone-500">Filters active:</span>
            {search && (
              <button onClick={() => setSearch("")} className="inline-flex items-center gap-1 rounded-md bg-stone-200/50 px-2 py-1 text-xs text-stone-600 hover:bg-stone-300/50 transition-colors">
                &ldquo;{search}&rdquo; <X className="size-3" />
              </button>
            )}
            {folderFilter && (
              <button onClick={() => setFolderFilter("")} className="inline-flex items-center gap-1 rounded-md bg-stone-200/50 px-2 py-1 text-xs text-stone-600 hover:bg-stone-300/50 transition-colors">
                {folderFilter} <X className="size-3" />
              </button>
            )}
            {tagFilter && (
              <button onClick={() => setTagFilter("")} className="inline-flex items-center gap-1 rounded-md bg-stone-200/50 px-2 py-1 text-xs text-stone-600 hover:bg-stone-300/50 transition-colors">
                {tagFilter} <X className="size-3" />
              </button>
            )}
            <button onClick={clearFilters} className="ml-auto text-xs text-stone-500 hover:text-stone-600 transition-colors">
              Clear all
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      <Card className="border-stone-200/50">
        <CardHeader className="border-b border-stone-200/50 pb-3">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm font-semibold">All URLs</CardTitle>
            {(urlsData?.total ?? 0) > 0 && (
              // The server's `total`, not `items.length`. `items` is one page
              // (the request asks for 50), so a workspace with 300 URLs
              // labelled the page "50 links" — and the accurate total was
              // already in scope, unused. The dashboard reads `total` for the
              // same reason.
              <span className="text-xs text-stone-500">
                {urlsData!.total} link{urlsData!.total !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {urlsPending && items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="size-5 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent" />
              <p className="mt-3 text-sm text-stone-500">Loading URLs...</p>
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="mb-4 rounded-full bg-stone-200/50 p-4">
                <Link2 className="size-8 text-stone-500" />
              </div>
              <p className="font-medium">No URLs found</p>
              <p className="mt-1 text-sm text-stone-500">
                {hasFilters ? "Try adjusting your filters." : "Create your first shortened URL."}
              </p>
              {!hasFilters && (
                <Link href="/urls/new" className="mt-6">
                  <Button className="bg-emerald-600 text-white hover:bg-emerald-700">
                    <Plus className="mr-1.5 size-4" />Create URL
                  </Button>
                </Link>
              )}
            </div>
          ) : (
            <div className="divide-y divide-stone-200/50">
              {items.map((url) => (
                <div key={url.id} className="group flex flex-col gap-2 px-6 py-3.5 transition-colors hover:bg-white/30 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <a href={buildShortUrl(url)} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-stone-900 hover:text-emerald-600 transition-colors">
                        {url.short_code} <ExternalLink className="inline size-3" />
                      </a>
                      <button
                        onClick={() => { navigator.clipboard.writeText(buildShareableShortUrl(url)); toast.success("Short URL copied") }}
                        className="rounded-md p-1 text-stone-400 hover:text-emerald-600 hover:bg-emerald-500/10 transition-colors"
                        title="Copy short URL"
                      >
                        <Copy className="size-3.5" />
                      </button>
                      <Badge variant={url.status === "active" ? "success" : "secondary"} className="text-xs px-1.5 py-0">
                        {url.status === "active" ? "Live" : url.status}
                      </Badge>
                      {url.is_one_time && (
                        <Badge variant="warning" className="text-xs px-1.5 py-0">One-time</Badge>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-stone-500">{url.original_url}</p>
                    {url.tags && url.tags.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {url.tags.map((t) => (
                          <span key={t} className="inline-flex items-center gap-1 rounded-md bg-stone-200/50 px-1.5 py-0.5 text-xs text-stone-500">
                            <Tags className="size-2.5" /> {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => favoriteSet.has(url.id) ? removeFavorite.mutate(url.id) : addFavorite.mutate(url.id)} className={`rounded-md p-1.5 transition-colors ${favoriteSet.has(url.id) ? "text-red-600 hover:bg-red-500/10" : "text-stone-500 hover:text-red-600 hover:bg-red-500/10"}`}>
                      <Heart className={`size-3.5 ${favoriteSet.has(url.id) ? "fill-current" : ""}`} />
                    </button>
                    <Link href={`/urls/${url.id}`} className="rounded-md p-1.5 text-stone-500 hover:text-stone-600 hover:bg-stone-200/50 transition-colors">
                      <ExternalLink className="size-3.5" />
                    </Link>
                    <Link href={`/urls/${url.id}/analytics`} className="rounded-md p-1.5 text-stone-500 hover:text-stone-600 hover:bg-stone-200/50 transition-colors">
                      <BarChart3 className="size-3.5" />
                    </Link>
                    <button onClick={() => deleteUrl.mutate(url.id)} className="rounded-md p-1.5 text-stone-500 hover:text-red-600 hover:bg-red-500/10 transition-colors">
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
