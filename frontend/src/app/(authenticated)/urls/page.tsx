"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { useMe, useWorkspaces, useWorkspaceMembers, useUrls, useFolders, useTags, useFavorites, useDeleteUrlMutation, useAddFavoriteMutation, useRemoveFavoriteMutation } from "@/queries"
import { Search, ExternalLink, Trash2, BarChart3, Heart, FolderOpen, Tags } from "lucide-react"

export default function URLsPage() {
  useEffect(() => { document.title = "URLs - LinkForge" }, [])
  const router = useRouter()
  const { data: user } = useMe()
  const { data: workspaces = [] } = useWorkspaces()
  const [wsId, setWsId] = useState<number | null>(null)

  const { data: members = [] } = useWorkspaceMembers(wsId)
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

  const myRole = members.find((m) => m.user_id === user?.id)?.role
  const canEdit = myRole === "admin" || myRole === "editor"

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const error = urlsError instanceof Error ? urlsError.message : ""

  return (
    <div className="p-6">
      <div className="mb-6">
        <div>
          <h1 className="text-2xl font-bold">URLs</h1>
          <p className="text-sm text-muted-foreground">Manage your short links.</p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search URLs..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={String(wsId ?? "")} onChange={(e) => setWsId(e.target.value ? Number(e.target.value) : null)} className="w-40">
          <option value="">All workspaces</option>
          {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </Select>
        <Select value={folderFilter} onChange={(e) => setFolderFilter(e.target.value)} className="w-36">
          <option value="">All folders</option>
          {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </Select>
        <Select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} className="w-36">
          <option value="">All tags</option>
          {allTags.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
        </Select>
      </div>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>All URLs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <div className="px-6 pb-6">
              <div className="rounded-xl border-2 border-dashed border-zinc-700 p-12 text-center">
                <p className="text-muted-foreground">No URLs found. Create one or adjust filters.</p>
              </div>
            </div>
          ) : (
            <div className="divide-y">
              {items.map((url) => (
                <div key={url.id} className="flex items-center justify-between px-6 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <a href={`/${url.short_code}`} target="_blank" className="text-sm font-medium text-blue-400 hover:underline">
                        {url.short_code} <ExternalLink className="inline size-3" />
                      </a>
                      <Badge variant={url.status === "active" ? "success" : "secondary"}>{url.status}</Badge>
                      {url.is_one_time && <Badge variant="warning">One-time</Badge>}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">{url.original_url}</p>
                    {url.tags && url.tags.length > 0 && (
                      <div className="mt-1 flex gap-1">
                        {url.tags.map((t) => (
                          <span key={t} className="inline-flex items-center gap-1 rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-300">
                            <Tags className="size-2.5" /> {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    {favoriteSet.has(url.id) ? (
                      <Button variant="ghost" size="xs" onClick={() => removeFavorite.mutate(url.id)}>
                        <Heart className="size-3.5 text-red-400 fill-current" />
                      </Button>
                    ) : (
                      <Button variant="ghost" size="xs" onClick={() => addFavorite.mutate(url.id)}>
                        <Heart className="size-3.5 text-muted-foreground hover:text-red-400" />
                      </Button>
                    )}
                    <Link href={`/urls/${url.id}`}>
                      <Button variant="ghost" size="xs"><ExternalLink className="size-3.5" /></Button>
                    </Link>
                    <Link href={`/urls/${url.id}/analytics`}>
                      <Button variant="ghost" size="xs"><BarChart3 className="size-3.5" /></Button>
                    </Link>
                    <Button variant="ghost" size="xs" onClick={() => deleteUrl.mutate(url.id)}><Trash2 className="size-3.5 text-destructive" /></Button>
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
