"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { useMe, useWorkspaces, useWorkspaceMembers, useUrls, useFolders, useTags, useFavorites, useDeleteUrlMutation, useAddFavoriteMutation, useRemoveFavoriteMutation } from "@/queries"
import { Search, ExternalLink, Trash2, BarChart3, Heart, Tags, Link2, Plus, Filter } from "lucide-react"

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
  const { data: urlsData, error: urlsError } = useUrls(wsId, {
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

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">URLs</h1>
          <p className="text-sm text-zinc-400">Manage your short links.</p>
        </div>
        <Link href="/urls/new">
          <Button className="bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-600/20">
            <Plus className="mr-1.5 size-4" />New URL
          </Button>
        </Link>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
          <Input placeholder="Search by original URL or short code..." value={search} onChange={(e) => setSearch(e.target.value)} className="border-zinc-800 bg-zinc-900/50 pl-9 text-sm placeholder:text-zinc-500 focus:border-blue-500" />
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
          {(search || folderFilter || tagFilter) && (
            <Button variant="ghost" size="sm" onClick={() => { setSearch(""); setFolderFilter(""); setTagFilter("") }} className="text-zinc-300">
              <Filter className="size-3.5 mr-1" /> Clear
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      <Card className="border-zinc-800/50">
        <CardHeader className="border-b border-zinc-800/50 pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Link2 className="size-4 text-blue-400" />
            All URLs
            {items.length > 0 && (
              <span className="ml-auto text-xs font-normal text-zinc-400">{items.length} link{items.length !== 1 ? "s" : ""}</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="mb-4 rounded-full bg-blue-500/10 p-4">
                <Link2 className="size-8 text-blue-400" />
              </div>
              <p className="font-medium">No URLs found</p>
              <p className="mt-1 text-sm text-zinc-400">
                {search || folderFilter || tagFilter ? "Try adjusting your filters." : "Create your first shortened URL."}
              </p>
              {!search && !folderFilter && !tagFilter && (
                <Link href="/urls/new" className="mt-6">
                  <Button className="bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-600/20">
                    <Plus className="mr-1.5 size-4" />Create URL
                  </Button>
                </Link>
              )}
            </div>
          ) : (
            <div className="divide-y divide-zinc-800/50">
              {items.map((url) => (
                <div key={url.id} className="group flex flex-col gap-2 px-6 py-4 transition-colors hover:bg-zinc-900/30 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <a href={`/${url.short_code}`} target="_blank" className="text-sm font-medium text-blue-400 hover:underline">
                        {url.short_code} <ExternalLink className="inline size-3" />
                      </a>
                      <Badge variant={url.status === "active" ? "success" : "secondary"} className="text-[10px] px-1.5 py-0">
                        {url.status === "active" ? "Live" : url.status}
                      </Badge>
                      {url.is_one_time && (
                        <Badge variant="warning" className="text-[10px] px-1.5 py-0">One-time</Badge>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-zinc-400">{url.original_url}</p>
                    {url.tags && url.tags.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {url.tags.map((t) => (
                          <span key={t} className="inline-flex items-center gap-1 rounded-md bg-zinc-800/50 px-1.5 py-0.5 text-[10px] text-zinc-300">
                            <Tags className="size-2.5" /> {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => favoriteSet.has(url.id) ? removeFavorite.mutate(url.id) : addFavorite.mutate(url.id)} className={`rounded-lg p-2 transition-colors ${favoriteSet.has(url.id) ? "text-red-400 hover:bg-red-500/10" : "text-zinc-400 hover:text-red-400 hover:bg-red-500/10"}`}>
                      <Heart className={`size-3.5 ${favoriteSet.has(url.id) ? "fill-current" : ""}`} />
                    </button>
                    <Link href={`/urls/${url.id}`} className="rounded-lg p-2 text-zinc-400 hover:text-blue-400 hover:bg-blue-500/10 transition-colors">
                      <ExternalLink className="size-3.5" />
                    </Link>
                    <Link href={`/urls/${url.id}/analytics`} className="rounded-lg p-2 text-zinc-400 hover:text-green-400 hover:bg-green-500/10 transition-colors">
                      <BarChart3 className="size-3.5" />
                    </Link>
                    <button onClick={() => deleteUrl.mutate(url.id)} className="rounded-lg p-2 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-colors">
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
