"use client"

import Image from "next/image"
import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { auth, foldersApi, getErrorMessage, tagsApi, urls } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { ExternalLink, ArrowLeft, BarChart3, Calendar, Hash, Globe, QrCode, Download, FolderOpen, Tags, type LucideIcon } from "lucide-react"

type UrlUpdateInput = Parameters<typeof urls.update>[1]
type InfoItem = {
  label: string
  value: string | number
  icon: LucideIcon
  link?: string
}

export default function URLDetailPage() {
  const { id } = useParams()
  useEffect(() => { document.title = "URL Details - LinkForge" }, [])
  const router = useRouter()
  const { setUser } = useAuthStore()
  const queryClient = useQueryClient()

  const [originalUrl, setOriginalUrl] = useState("")
  const [password, setPassword] = useState("")
  const [expiresAt, setExpiresAt] = useState("")
  const [isAbTest, setIsAbTest] = useState(false)
  const [iosUrl, setIosUrl] = useState("")
  const [androidUrl, setAndroidUrl] = useState("")
  const [error, setError] = useState("")
  const [selectedFolder, setSelectedFolder] = useState("")
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  useQuery({
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

  const urlId = Number(id)

  const { data: url } = useQuery({
    queryKey: ["url", urlId],
    queryFn: () => urls.get(urlId),
    enabled: !!urlId,
  })

  const { data: folders = [] } = useQuery({
    queryKey: ["folders", url?.workspace_id],
    queryFn: () => foldersApi.list(url!.workspace_id),
    enabled: !!url?.workspace_id,
  })

  const { data: allTags = [] } = useQuery({
    queryKey: ["tags", url?.workspace_id],
    queryFn: () => tagsApi.list(url!.workspace_id),
    enabled: !!url?.workspace_id,
  })

  useEffect(() => {
    if (!url) return
    queueMicrotask(() => {
      setOriginalUrl(url.original_url)
      setIsAbTest(url.is_ab_test)
      setIosUrl(url.ios_url || "")
      setAndroidUrl(url.android_url || "")
      if (url.expires_at) setExpiresAt(new Date(url.expires_at).toISOString().slice(0, 16))
      setSelectedFolder(url.folder_id ? String(url.folder_id) : "")
      setSelectedTags(url.tags || [])
    })
  }, [url])

  const updateMutation = useMutation({
    mutationFn: (data: UrlUpdateInput) => urls.update(urlId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["url", urlId] })
      setPassword("")
    },
    onError: (err: unknown) => {
      setError(getErrorMessage(err))
    }
  })

  async function handleSave() {
    if (!url) return
    setError("")
    updateMutation.mutate({
      original_url: originalUrl,
      folder_id: selectedFolder ? Number(selectedFolder) : null,
      password: password || undefined,
      expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      is_ab_test: isAbTest,
      ios_url: iosUrl || undefined,
      android_url: androidUrl || undefined,
      tags: selectedTags,
    })
  }

  async function handleDownloadQr() {
    if (!url) return
    const res = await urls.getQr(url.id)
    const byteCharacters = atob(res.qr_code)
    const byteNumbers = new Array(byteCharacters.length)
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i)
    }
    const byteArray = new Uint8Array(byteNumbers)
    const blob = new Blob([byteArray], { type: "image/png" })
    const link = document.createElement("a")
    link.download = `${url.short_code}-qr.png`
    link.href = URL.createObjectURL(blob)
    link.click()
    URL.revokeObjectURL(link.href)
  }

  if (!url) return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-2">
        <div className="size-6 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  )

  const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace("/api/v1", "") || "http://127.0.0.1:8000"

  const infoItems: InfoItem[] = [
    { label: "Short Code", value: url.short_code, icon: Hash, link: `${baseUrl}/${url.short_code}` },
    { label: "Created", value: new Date(url.created_at).toLocaleDateString(), icon: Calendar },
    { label: "Workspace ID", value: url.workspace_id, icon: Globe },
  ]
  if (url.folder_id) {
    const folder = folders.find((f) => f.id === url.folder_id)
    if (folder) infoItems.push({ label: "Folder", value: folder.name, icon: FolderOpen })
  }
  if (url.tags && url.tags.length > 0) {
    infoItems.push({ label: "Tags", value: url.tags.join(", "), icon: Tags })
  }
  if (url.expires_at) infoItems.push({ label: "Expires", value: new Date(url.expires_at).toLocaleDateString(), icon: Calendar })
  if (url.custom_alias) infoItems.push({ label: "Custom Alias", value: url.custom_alias, icon: Hash })

  return (
    <div className="p-6">
      <button onClick={() => router.push("/urls")} className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to URLs
      </button>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">URL Details</h1>
          <p className="text-sm text-muted-foreground break-all">/{url.short_code}</p>
          <Badge variant={url.status === "active" ? "success" : "secondary"} className="capitalize">{url.status}</Badge>
          {url.is_one_time && <Badge variant="warning">One-time</Badge>}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Edit URL</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {error && <p className="text-sm text-red-400">{error}</p>}
            <div>
              <label className="mb-1.5 block text-sm font-medium">Original URL</label>
              <Input value={originalUrl} onChange={(e) => setOriginalUrl(e.target.value)} />
            </div>
            <Separator />
            <p className="text-sm font-medium">Security & Expiration</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium">Password <span className="text-muted-foreground">(leave blank to keep)</span></label>
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="New password" />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">Expires At</label>
                <Input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
              </div>
            </div>
            <Separator />
            <p className="text-sm font-medium">Folder & Tags</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium">Folder</label>
                <Select value={selectedFolder} onChange={(e) => setSelectedFolder(e.target.value)}>
                  <option value="">No folder</option>
                  {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                </Select>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {allTags.map((t) => (
                <button key={t.id} type="button" onClick={() =>
                  setSelectedTags((prev) => prev.includes(t.name) ? prev.filter((x) => x !== t.name) : [...prev, t.name])
                }
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    selectedTags.includes(t.name)
                      ? "bg-blue-600 text-white"
                      : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                  }`}
                >
                  {t.name}
                </button>
              ))}
            </div>
            <Separator />
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">A/B Testing</p>
                <p className="text-xs text-muted-foreground">Different destinations per device</p>
              </div>
              <Switch checked={isAbTest} onCheckedChange={setIsAbTest} />
            </div>
            {isAbTest && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium">iOS URL</label>
                  <Input type="url" value={iosUrl} onChange={(e) => setIosUrl(e.target.value)} />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">Android URL</label>
                  <Input type="url" value={androidUrl} onChange={(e) => setAndroidUrl(e.target.value)} />
                </div>
              </div>
            )}
            <Button onClick={handleSave} disabled={updateMutation.isPending} className="bg-blue-600 text-white hover:bg-blue-700">
              {updateMutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Info</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {infoItems.map((item) => {
                const Icon = item.icon
                return (
                  <div key={item.label} className="flex items-center justify-between rounded-lg bg-muted px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Icon className="size-4 text-muted-foreground" />
                      <span className="text-sm text-muted-foreground">{item.label}</span>
                    </div>
                    {item.link ? (
                      <a href={item.link} target="_blank" className="text-sm font-medium text-blue-400 hover:underline flex items-center gap-1">
                        {item.value} <ExternalLink className="size-3" />
                      </a>
                    ) : (
                      <span className="text-sm font-medium">{item.value}</span>
                    )}
                  </div>
                )
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>QR Code</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {url.qr_code ? (
                <div className="flex flex-col items-center gap-3">
                  <Image src={`data:image/png;base64,${url.qr_code}`} alt="QR Code" width={160} height={160} className="rounded-lg" unoptimized />
                  <Button variant="outline" onClick={handleDownloadQr}>
                    <Download className="mr-1 size-4" /> Download PNG
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3 py-4">
                  <QrCode className="size-10 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">No QR code generated yet.</p>
                  <Button variant="outline" onClick={async () => {
                    await urls.getQr(url.id)
                    queryClient.invalidateQueries({ queryKey: ["url", urlId] })
                  }}>
                    <QrCode className="mr-1 size-4" /> Generate QR
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Separator className="my-6" />
      <Button variant="outline" onClick={() => router.push(`/urls/${url.id}/analytics`)}>
        <BarChart3 className="mr-1 size-4" /> View Analytics
      </Button>
    </div>
  )
}
