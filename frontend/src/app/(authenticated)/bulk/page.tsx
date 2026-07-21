"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { auth, bulkApi, workspacesApi, foldersApi, tagsApi, urls } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Upload, Download, UploadCloud, ToggleLeft, ToggleRight, Trash2, QrCode, Search } from "lucide-react"

type BulkActionResult = { updated?: number; deleted?: number }

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed"
}

export default function BulkPage() {
  const router = useRouter()
  const { setUser } = useAuthStore()
  const [selectedWsId, setSelectedWsId] = useState<number | null>(null)
  const [urlsInput, setUrlsInput] = useState("")
  const [folderId, setFolderId] = useState("")
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [expiresAt, setExpiresAt] = useState("")
  const [password, setPassword] = useState("")
  const [isAbTest, setIsAbTest] = useState(false)
  const [isOneTime, setIsOneTime] = useState(false)
  const [iosUrl, setIosUrl] = useState("")
  const [androidUrl, setAndroidUrl] = useState("")
  const [domain, setDomain] = useState("")
  const [result, setResult] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [tab, setTab] = useState<"create" | "manage">("create")
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

  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspacesApi.list,
    enabled: !authLoading
  })

  const wsId = selectedWsId || workspaces?.[0]?.id

  const { data: folders = [] } = useQuery({
    queryKey: ["folders", wsId],
    queryFn: () => foldersApi.list(wsId!),
    enabled: !!wsId,
  })

  const { data: tags = [] } = useQuery({
    queryKey: ["tags", wsId],
    queryFn: () => tagsApi.list(wsId!),
    enabled: !!wsId,
  })

  const { data: urlsResponse } = useQuery({
    queryKey: ["urls", wsId],
    queryFn: () => urls.list(wsId!),
    enabled: !!wsId,
  })
  const allUrls = urlsResponse?.items ?? []

  function setWsId(id: number) {
    setSelectedWsId(id)
    setSelectedTags([])
    setFolderId("")
    setIsAbTest(false)
    setIsOneTime(false)
    setIosUrl("")
    setAndroidUrl("")
    setDomain("")
    setPassword("")
    setExpiresAt("")
  }

  function toggleUrl(id: number) {
    setSelectedIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  function toggleTag(name: string) {
    setSelectedTags((prev) => prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name])
  }

  async function handleBulkCreate() {
    if (!wsId || !urlsInput.trim()) return
    setLoading(true)
    const tagsStr = selectedTags.length > 0 ? selectedTags.join(",") : ""
    const lines = urlsInput.split("\n").filter(Boolean).map((line) => {
      const parts = line.split(",").map((s) => s.trim())
      return {
        original_url: parts[0],
        custom_alias: parts[1] || undefined,
        folder_id: folderId || undefined,
        tags: tagsStr || undefined,
        expires_at: expiresAt || undefined,
        password: password || undefined,
        domain: domain || undefined,
        is_ab_test: isAbTest || undefined,
        ios_url: isAbTest && iosUrl ? iosUrl : undefined,
        android_url: isAbTest && androidUrl ? androidUrl : undefined,
        is_one_time: isOneTime || undefined,
      }
    })
    try {
      const res = await bulkApi.create(wsId, lines)
      setResult(`Created ${res.created} URLs successfully!`)
      queryClient.invalidateQueries({ queryKey: ["urls", wsId] })
    } catch (err: unknown) {
      setResult(`Error: ${getErrorMessage(err)}`)
    } finally { setLoading(false) }
  }

  async function handleExport() {
    if (!wsId) return
    await bulkApi.export(wsId)
  }

  async function handleBulkAction(action: "disable" | "reactivate" | "delete") {
    if (!wsId || selectedIds.length === 0) return
    setLoading(true)
    try {
      let res: BulkActionResult
      if (action === "disable") res = await bulkApi.disable(wsId, selectedIds)
      else if (action === "reactivate") res = await bulkApi.reactivate(wsId, selectedIds)
      else res = await bulkApi.delete(wsId, selectedIds)
      setResult(`${action === "delete" ? "Deleted" : action === "disable" ? "Disabled" : "Reactivated"} ${res.updated ?? res.deleted ?? 0} URLs`)
      queryClient.invalidateQueries({ queryKey: ["urls", wsId] })
      setSelectedIds([])
    } catch (err: unknown) {
      setResult(`Error: ${getErrorMessage(err)}`)
    } finally { setLoading(false) }
  }

  async function handleBulkQr() {
    if (!wsId || selectedIds.length === 0) return
    await bulkApi.qr(wsId, selectedIds)
    setResult(`Downloading QR codes for ${selectedIds.length} URLs`)
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Bulk Operations</h1>
        <p className="text-sm text-muted-foreground">Create, manage, and export URLs in bulk.</p>
      </div>

      <div className="mb-4 flex gap-2">
        <Button variant={tab === "create" ? "default" : "outline"} onClick={() => setTab("create")}><Upload className="mr-1 size-4" />Create</Button>
        <Button variant={tab === "manage" ? "default" : "outline"} onClick={() => setTab("manage")}><Search className="mr-1 size-4" />Manage</Button>
      </div>

      {tab === "create" ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="rounded-lg bg-blue-500/10 p-2"><UploadCloud className="size-5 text-blue-400" /></div>
                <CardTitle>Bulk Create</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">One URL per line: <code className="rounded bg-muted px-1 py-0.5">url,custom_alias</code></p>
              <Textarea className="h-40 font-mono text-sm" placeholder="https://example.com/1,my-link" value={urlsInput} onChange={(e) => setUrlsInput(e.target.value)} />
              <Button onClick={handleBulkCreate} disabled={loading} className="bg-blue-600 text-white hover:bg-blue-700">
                <Upload className="mr-1 size-4" />{loading ? "Creating..." : "Bulk Create"}
              </Button>
              {result && <p className={`text-sm ${result.startsWith("Error") ? "text-red-400" : "text-green-400"}`}>{result}</p>}
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Defaults</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <Label>Workspace</Label>
                  <Select value={String(wsId ?? "")} onChange={(e) => setWsId(Number(e.target.value))}>
                    {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                  </Select>
                </div>
                <div>
                  <Label>Folder <span className="text-muted-foreground">(optional)</span></Label>
                  <Select value={folderId} onChange={(e) => setFolderId(e.target.value)}>
                    <option value="">No folder</option>
                    {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </Select>
                </div>
                <div>
                  <Label>Tags <span className="text-muted-foreground">(optional)</span></Label>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {tags.map((t) => (
                      <button key={t.id} type="button" onClick={() => toggleTag(t.name)}
                        className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                          selectedTags.includes(t.name)
                            ? "bg-blue-600 text-white"
                            : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                        }`}
                      >
                        {t.name}
                      </button>
                    ))}
                    {tags.length === 0 && <p className="text-xs text-muted-foreground">No tags in this workspace</p>}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Expires At <span className="text-muted-foreground">(optional)</span></Label>
                    <Input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
                  </div>
                  <div>
                    <Label>Password <span className="text-muted-foreground">(optional)</span></Label>
                    <Input type="password" placeholder="protect links" value={password} onChange={(e) => setPassword(e.target.value)} />
                  </div>
                  <div>
                    <Label>Custom Domain <span className="text-muted-foreground">(optional)</span></Label>
                    <Input placeholder="short.example.com" value={domain} onChange={(e) => setDomain(e.target.value)} />
                  </div>
                </div>

                <Separator />
                <div className="space-y-3">
                  <div className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <p className="text-sm font-medium">A/B Testing</p>
                      <p className="text-xs text-muted-foreground">Different destinations for iOS / Android</p>
                    </div>
                    <Switch checked={isAbTest} onCheckedChange={setIsAbTest} />
                  </div>
                  {isAbTest && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label>iOS URL</Label>
                        <Input type="url" placeholder="https://apps.apple.com/..." value={iosUrl} onChange={(e) => setIosUrl(e.target.value)} />
                      </div>
                      <div>
                        <Label>Android URL</Label>
                        <Input type="url" placeholder="https://play.google.com/..." value={androidUrl} onChange={(e) => setAndroidUrl(e.target.value)} />
                      </div>
                    </div>
                  )}
                  <div className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <p className="text-sm font-medium">One-Time Access</p>
                      <p className="text-xs text-muted-foreground">Link expires after first click</p>
                    </div>
                    <Switch checked={isOneTime} onCheckedChange={setIsOneTime} />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Export URLs</CardTitle></CardHeader>
              <CardContent>
                <p className="mb-3 text-sm text-muted-foreground">Download all URLs as CSV.</p>
                <Button variant="outline" onClick={handleExport}><Download className="mr-1 size-4" />Export CSV</Button>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {allUrls.length === 0 ? (
            <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
              <Search className="mx-auto mb-3 size-10 text-muted-foreground" />
              <p className="text-lg font-medium">No URLs to manage</p>
              <p className="mt-1 text-sm text-muted-foreground">Create some URLs first.</p>
            </div>
          ) : (
            <>
              {selectedIds.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleBulkAction("disable")}>
                    <ToggleLeft className="mr-1 size-4" />Disable ({selectedIds.length})
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleBulkAction("reactivate")}>
                    <ToggleRight className="mr-1 size-4" />Reactivate ({selectedIds.length})
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => handleBulkAction("delete")}>
                    <Trash2 className="mr-1 size-4" />Delete ({selectedIds.length})
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleBulkQr}>
                    <QrCode className="mr-1 size-4" />QR Codes ({selectedIds.length})
                  </Button>
                </div>
              )}

              <div className="space-y-1">
                <div className="flex items-center gap-2 px-1 py-2 text-xs font-medium text-muted-foreground">
                  <div className="w-8" />
                  <span className="flex-1">URL</span>
                  <span className="w-20 text-center">Status</span>
                </div>
                {allUrls.map((u) => (
                  <div key={u.id} className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 transition-colors hover:bg-muted/50">
                    <input type="checkbox" checked={selectedIds.includes(u.id)} onChange={() => toggleUrl(u.id)}
                      className="size-4 accent-blue-500" />
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-sm font-medium">{u.short_code}</p>
                      <p className="truncate text-xs text-muted-foreground">{u.original_url}</p>
                    </div>
                    <span className={`w-20 text-center text-xs font-medium capitalize ${u.status === "active" ? "text-green-400" : "text-muted-foreground"}`}>{u.status}</span>
                  </div>
                ))}
              </div>
              {result && <p className={`mt-2 text-sm ${result.startsWith("Error") ? "text-red-400" : "text-green-400"}`}>{result}</p>}
            </>
          )}
        </div>
      )}
    </div>
  )
}
