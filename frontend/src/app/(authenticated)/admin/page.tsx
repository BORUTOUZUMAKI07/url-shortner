"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { auth, adminApi, type AdminStats, type User, type Workspace, type URLItem } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Shield, Users, Link2, Building2, Trash2, Crown, RefreshCw, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react"

export default function AdminPage() {
  const router = useRouter()
  useEffect(() => { document.title = "Admin - LinkForge" }, [])
  const { user, setUser } = useAuthStore()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [totalUsers, setTotalUsers] = useState(0)
  const [page, setPage] = useState(0)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [totalWorkspaces, setTotalWorkspaces] = useState(0)
  const [wsPage, setWsPage] = useState(0)
  const [adminUrls, setAdminUrls] = useState<URLItem[]>([])
  const [totalAdminUrls, setTotalAdminUrls] = useState(0)
  const [urlPage, setUrlPage] = useState(0)
  const [tab, setTab] = useState<"stats" | "users" | "workspaces" | "urls">("stats")
  const limit = 20

  useEffect(() => {
    auth.me()
      .then((u) => {
        setUser(u)
        if (!u.is_superadmin) router.push("/dashboard")
      })
      .catch(() => router.push("/login"))
  }, [router, setUser])

  useEffect(() => {
    if (!user?.is_superadmin) return
    adminApi.stats().then(setStats)
  }, [user])

  useEffect(() => {
    if (!user?.is_superadmin) return
    adminApi.listUsers(page * limit, limit).then((r) => { setUsers(r.users); setTotalUsers(r.total) })
  }, [user, page])

  useEffect(() => {
    if (!user?.is_superadmin) return
    adminApi.listWorkspaces(wsPage * limit, limit).then((r) => { setWorkspaces(r.items); setTotalWorkspaces(r.total) })
  }, [user, wsPage])

  useEffect(() => {
    if (!user?.is_superadmin) return
    adminApi.listUrls(urlPage * limit, limit).then((r) => { setAdminUrls(r.urls); setTotalAdminUrls(r.total) })
  }, [user, urlPage])

  async function handleToggleSuperadmin(id: number) {
    await adminApi.toggleSuperadmin(id)
    adminApi.listUsers(page * limit, limit).then((r) => setUsers(r.users))
  }

  async function handleDeleteUser(id: number) {
    if (!confirm("Delete this user and all their data?")) return
    await adminApi.deleteUser(id)
    adminApi.listUsers(page * limit, limit).then((r) => setUsers(r.users))
    adminApi.stats().then(setStats)
  }

  if (!user?.is_superadmin) return null

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600">
          <Shield className="size-4.5" />
        </div>
        <h1 className="text-2xl font-heading font-semibold tracking-tight">Admin Panel</h1>
        <Badge className="bg-amber-600 text-white">Superadmin</Badge>
      </div>

      <div className="mb-6 flex gap-2">
        <Button variant={tab === "stats" ? "default" : "outline"} onClick={() => setTab("stats")}>
          <Crown className="mr-1 size-4" /> Stats
        </Button>
        <Button variant={tab === "users" ? "default" : "outline"} onClick={() => setTab("users")}>
          <Users className="mr-1 size-4" /> Users ({totalUsers})
        </Button>
        <Button variant={tab === "workspaces" ? "default" : "outline"} onClick={() => setTab("workspaces")}>
          <Building2 className="mr-1 size-4" /> Workspaces ({totalWorkspaces})
        </Button>
        <Button variant={tab === "urls" ? "default" : "outline"} onClick={() => setTab("urls")}>
          <Link2 className="mr-1 size-4" /> URLs ({totalAdminUrls})
        </Button>
      </div>

      {tab === "stats" && stats && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Users className="size-5" /> Users</CardTitle></CardHeader>
            <CardContent><p className="text-3xl font-bold">{stats.total_users}</p></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Building2 className="size-5" /> Workspaces</CardTitle></CardHeader>
            <CardContent><p className="text-3xl font-bold">{stats.total_workspaces}</p></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Link2 className="size-5" /> URLs</CardTitle></CardHeader>
            <CardContent><p className="text-3xl font-bold">{stats.total_urls}</p></CardContent>
          </Card>
        </div>
      )}

      {tab === "users" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>All Users</CardTitle>
            <Button variant="outline" size="sm" onClick={() => adminApi.listUsers(page * limit, limit).then((r) => setUsers(r.users))}>
              <RefreshCw className="size-4" />
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{u.email}</span>
                      {u.is_superadmin && <Badge className="bg-amber-600 text-white text-xs">Superadmin</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      ID: {u.id} · Plan: {u.plan} · Role: {u.role} · {u.is_verified ? "Verified" : "Unverified"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="outline" size="xs"
                      onClick={() => handleToggleSuperadmin(u.id)}
                    >
                      <Crown className={`size-3.5 ${u.is_superadmin ? "text-amber-500" : "text-muted-foreground"}`} />
                    </Button>
                    {u.id !== user.id && (
                      <Button variant="outline" size="xs" onClick={() => handleDeleteUser(u.id)}>
                        <Trash2 className="size-3.5 text-destructive" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
          <div className="flex items-center justify-between border-t px-4 py-3">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              <ChevronLeft className="size-4" /> Prev
            </Button>
            <span className="text-sm text-muted-foreground">Page {page + 1} of {Math.ceil(totalUsers / limit)}</span>
            <Button variant="outline" size="sm" disabled={(page + 1) * limit >= totalUsers} onClick={() => setPage(page + 1)}>
              Next <ChevronRight className="size-4" />
            </Button>
          </div>
        </Card>
      )}

      {tab === "workspaces" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>All Workspaces</CardTitle>
            <Button variant="outline" size="sm" onClick={() => adminApi.listWorkspaces(wsPage * limit, limit).then((r) => { setWorkspaces(r.items); setTotalWorkspaces(r.total) })}>
              <RefreshCw className="size-4" />
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {workspaces.map((w) => (
                <div key={w.id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <span className="font-medium">{w.name}</span>
                    <p className="text-xs text-muted-foreground">
                      ID: {w.id} · Owner ID: {w.owner_id} · Created {new Date(w.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
              {workspaces.length === 0 && (
                <p className="px-4 py-8 text-center text-sm text-muted-foreground">No workspaces found.</p>
              )}
            </div>
          </CardContent>
          <div className="flex items-center justify-between border-t px-4 py-3">
            <Button variant="outline" size="sm" disabled={wsPage === 0} onClick={() => setWsPage(wsPage - 1)}>
              <ChevronLeft className="size-4" /> Prev
            </Button>
            <span className="text-sm text-muted-foreground">Page {wsPage + 1} of {Math.max(1, Math.ceil(totalWorkspaces / limit))}</span>
            <Button variant="outline" size="sm" disabled={(wsPage + 1) * limit >= totalWorkspaces} onClick={() => setWsPage(wsPage + 1)}>
              Next <ChevronRight className="size-4" />
            </Button>
          </div>
        </Card>
      )}

      {tab === "urls" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>All URLs</CardTitle>
            <Button variant="outline" size="sm" onClick={() => adminApi.listUrls(urlPage * limit, limit).then((r) => { setAdminUrls(r.urls); setTotalAdminUrls(r.total) })}>
              <RefreshCw className="size-4" />
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {adminUrls.map((u) => (
                <div key={u.id} className="flex items-center justify-between gap-4 px-4 py-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">/{u.custom_alias || u.short_code}</span>
                      <Badge variant={u.status === "active" ? "success" : "outline"} className="text-xs capitalize">{u.status}</Badge>
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {u.original_url} · Workspace ID: {u.workspace_id} · Created {new Date(u.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <a href={u.original_url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-stone-400 hover:text-emerald-600">
                    <ExternalLink className="size-4" />
                  </a>
                </div>
              ))}
              {adminUrls.length === 0 && (
                <p className="px-4 py-8 text-center text-sm text-muted-foreground">No URLs found.</p>
              )}
            </div>
          </CardContent>
          <div className="flex items-center justify-between border-t px-4 py-3">
            <Button variant="outline" size="sm" disabled={urlPage === 0} onClick={() => setUrlPage(urlPage - 1)}>
              <ChevronLeft className="size-4" /> Prev
            </Button>
            <span className="text-sm text-muted-foreground">Page {urlPage + 1} of {Math.max(1, Math.ceil(totalAdminUrls / limit))}</span>
            <Button variant="outline" size="sm" disabled={(urlPage + 1) * limit >= totalAdminUrls} onClick={() => setUrlPage(urlPage + 1)}>
              Next <ChevronRight className="size-4" />
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
