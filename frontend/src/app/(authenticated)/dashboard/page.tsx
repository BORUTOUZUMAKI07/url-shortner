"use client"

import { useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { StatsCardSkeleton, TableSkeleton } from "@/components/ui/skeleton"
import { useDashboard } from "@/hooks/useDashboard"
import { useAuthStore } from "@/store/auth"
import {
  BarChart3, ExternalLink, Plus, Link2, Activity,
  AlertTriangle, ArrowRight,
} from "lucide-react"

export default function DashboardPage() {
  useEffect(() => { document.title = "Dashboard - LinkForge" }, [])
  const { user } = useAuthStore()

  const {
    urlList, totalUrlsCount, workspaces, wsId, error, quota,
    canEdit, activeUrls, isLoading,
    setWsId,
  } = useDashboard()

  const stats = [
    { title: "Total URLs", value: totalUrlsCount, icon: Link2, color: "blue" },
    { title: "Active", value: activeUrls.length, icon: Activity, color: "green" },
  ]

  const colorMap: Record<string, { ring: string; text: string; bg: string }> = {
    blue: { ring: "ring-blue-500/20", text: "text-blue-400", bg: "bg-blue-500/10" },
    green: { ring: "ring-green-500/20", text: "text-green-400", bg: "bg-green-500/10" },
  }

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="mb-8 space-y-2">
          <div className="h-8 w-64 animate-pulse rounded bg-zinc-800/50" />
          <div className="h-4 w-48 animate-pulse rounded bg-zinc-800/30" />
        </div>
        <StatsCardSkeleton />
        <div className="mt-6"><TableSkeleton rows={4} /></div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">
          Welcome back{user?.email ? `, ${user.email.split("@")[0]}` : ""}
        </h1>
        <p className="mt-1 text-sm text-zinc-400">Here&apos;s what&apos;s happening with your links.</p>
      </div>

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Select value={String(wsId ?? "")} onChange={(e) => setWsId(e.target.value ? Number(e.target.value) : null)} className="w-44">
          <option value="">All workspaces</option>
          {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </Select>
        {canEdit && (
          <Link href="/urls/new">
            <Button className="bg-blue-600 text-white hover:bg-blue-700">
              <Plus className="mr-1.5 size-4" />Create URL
            </Button>
          </Link>
        )}
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        {stats.map((s) => {
          const Icon = s.icon
          const c = colorMap[s.color]
          return (
            <Card key={s.title} className="border-zinc-800/50">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-3xl font-bold tracking-tight">{s.value}</p>
                    <p className="mt-1 text-sm text-zinc-400">{s.title}</p>
                  </div>
                  <div className={`rounded-lg ${c.bg} p-2.5 ring-1 ${c.ring}`}>
                    <Icon className={`size-5 ${c.text}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2 border-zinc-800/50">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-semibold">Recent URLs</CardTitle>
            {urlList.length > 0 && (
              <Link href="/urls">
                <Button variant="ghost" size="sm" className="text-xs gap-1 text-zinc-400 hover:text-white">
                  View all <ArrowRight className="size-3" />
                </Button>
              </Link>
            )}
          </CardHeader>
          <CardContent>
            {urlList.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="mb-4 rounded-full bg-zinc-800/50 p-4">
                  <Link2 className="size-8 text-zinc-500" />
                </div>
                <p className="font-medium">No URLs yet</p>
                <p className="mt-1 text-sm text-zinc-500">Create your first shortened URL to get started.</p>
                <Link href="/urls/new" className="mt-6">
                  <Button className="bg-blue-600 text-white hover:bg-blue-700">
                    <Plus className="mr-1.5 size-4" />Create URL
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-1">
                {urlList.slice(0, 5).map((url) => (
                  <div key={url.id} className="group flex items-center justify-between rounded-md border-l-2 border-transparent px-3 py-2.5 transition-colors hover:border-l-blue-500/50">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <a href={`/${url.short_code}`} target="_blank" className="text-sm font-medium text-zinc-100 hover:text-blue-400 transition-colors">
                          {url.short_code} <ExternalLink className="inline size-3" />
                        </a>
                        <Badge variant={url.status === "active" ? "success" : "secondary"} className="text-xs px-1.5 py-0">
                          {url.status}
                        </Badge>
                        {url.is_one_time && (
                          <Badge variant="warning" className="text-xs px-1.5 py-0">One-time</Badge>
                        )}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-zinc-500">{url.original_url}</p>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Link href={`/urls/${url.id}/analytics`}>
                        <Button variant="ghost" size="xs" className="text-zinc-500 hover:text-blue-400">
                          <BarChart3 className="size-3.5" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-zinc-800/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <Link href="/urls/new" className="flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors hover:bg-zinc-800/30">
              <Plus className="size-4 text-zinc-400" />
              <div>
                <p className="text-sm font-medium">Create URL</p>
                <p className="text-xs text-zinc-500">Shorten a new link</p>
              </div>
            </Link>
            <Link href="/urls" className="flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors hover:bg-zinc-800/30">
              <Link2 className="size-4 text-zinc-400" />
              <div>
                <p className="text-sm font-medium">View URLs</p>
                <p className="text-xs text-zinc-500">Browse all links</p>
              </div>
            </Link>
            <Link href="/workspaces" className="flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors hover:bg-zinc-800/30">
              <Activity className="size-4 text-zinc-400" />
              <div>
                <p className="text-sm font-medium">Workspaces</p>
                <p className="text-xs text-zinc-500">Manage teams</p>
              </div>
            </Link>
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {quota && quota.limit > 0 && quota.used / quota.limit > 0.8 && (
        <Card className="mb-6 border-amber-500/20 bg-amber-500/5">
          <CardContent className="flex items-center gap-3 pt-6">
            <AlertTriangle className="size-5 text-amber-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-300">API rate limit nearly reached</p>
              <p className="text-xs text-amber-200/70">{quota.used} / {quota.limit} requests used</p>
            </div>
            <Link href="/billing"><Button variant="outline" size="sm" className="border-amber-500/30 text-amber-300 hover:bg-amber-500/10">Upgrade</Button></Link>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
