"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { auth, adminApi, type AdminStats, type User } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Shield, Users, Link2, Building2, Trash2, Crown, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react"

export default function AdminPage() {
  const router = useRouter()
  useEffect(() => { document.title = "Admin - LinkForge" }, [])
  const { user, setUser } = useAuthStore()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [totalUsers, setTotalUsers] = useState(0)
  const [page, setPage] = useState(0)
  const [tab, setTab] = useState<"stats" | "users">("stats")
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
      <div className="mb-6 flex items-center gap-2">
        <Shield className="size-6 text-purple-500" />
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <Badge className="bg-purple-600 text-white">Superadmin</Badge>
      </div>

      <div className="mb-6 flex gap-2">
        <Button variant={tab === "stats" ? "default" : "outline"} onClick={() => setTab("stats")}>
          <Crown className="mr-1 size-4" /> Stats
        </Button>
        <Button variant={tab === "users" ? "default" : "outline"} onClick={() => setTab("users")}>
          <Users className="mr-1 size-4" /> Users ({totalUsers})
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
                      {u.is_superadmin && <Badge className="bg-purple-600 text-white text-xs">Superadmin</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      ID: {u.id} · Plan: {u.plan} · Role: {u.role} · {u.is_verified ? "Verified" : "Unverified"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="outline" size="xs"
                      onClick={() => handleToggleSuperadmin(u.id)}
                    >
                      <Crown className={`size-3.5 ${u.is_superadmin ? "text-purple-500" : "text-muted-foreground"}`} />
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
    </div>
  )
}
