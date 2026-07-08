"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select } from "@/components/ui/select"
import { urls } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { auth } from "@/lib/api"
import dynamic from "next/dynamic"

const BarChart = dynamic(() => import("recharts").then(mod => mod.BarChart), { ssr: false })
const Bar = dynamic(() => import("recharts").then(mod => mod.Bar), { ssr: false })
const XAxis = dynamic(() => import("recharts").then(mod => mod.XAxis), { ssr: false })
const YAxis = dynamic(() => import("recharts").then(mod => mod.YAxis), { ssr: false })
const CartesianGrid = dynamic(() => import("recharts").then(mod => mod.CartesianGrid), { ssr: false })
const Tooltip = dynamic(() => import("recharts").then(mod => mod.Tooltip), { ssr: false })
const ResponsiveContainer = dynamic(() => import("recharts").then(mod => mod.ResponsiveContainer), { ssr: false })
const PieChart = dynamic(() => import("recharts").then(mod => mod.PieChart), { ssr: false })
const Pie = dynamic(() => import("recharts").then(mod => mod.Pie), { ssr: false })
const Cell = dynamic(() => import("recharts").then(mod => mod.Cell), { ssr: false })
const Legend = dynamic(() => import("recharts").then(mod => mod.Legend), { ssr: false })
import { ArrowLeft, MousePointerClick, Users, BarChart3, Globe, Monitor, Smartphone, ExternalLink, Tags } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]

const DAYS_OPTIONS: Record<string, number | undefined> = { "24h": 1, "7d": 7, "30d": 30, "all": 90 }

export default function AnalyticsPage() {
  const { id } = useParams()
  const router = useRouter()
  const { setUser } = useAuthStore()
  const [period, setPeriod] = useState("7d")

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
  const days = DAYS_OPTIONS[period]

  const { data: url } = useQuery({
    queryKey: ["url", urlId],
    queryFn: () => urls.get(urlId),
    enabled: !!urlId,
  })

  const short_code = url?.short_code

  const { data: summary } = useQuery({
    queryKey: ["analytics_summary", short_code, days],
    queryFn: () => urls.analytics(short_code!, days),
    enabled: !!short_code,
  })

  const { data: devices } = useQuery({
    queryKey: ["analytics_devices", short_code],
    queryFn: () => urls.devices(short_code!),
    enabled: !!short_code,
  })

  const { data: utmResponse } = useQuery({
    queryKey: ["analytics_utm", short_code],
    queryFn: () => urls.utm(short_code!),
    enabled: !!short_code,
  })

  const { data: refererResponse } = useQuery({
    queryKey: ["analytics_referrers", short_code],
    queryFn: () => urls.referrers(short_code!),
    enabled: !!short_code,
  })

  const actualSummary = summary?.[0]
  const timeseries = summary?.[1]
  const utmData = utmResponse?.data || []
  const refererData = refererResponse?.data || []

  if (!url) return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-2">
        <div className="size-6 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  )

  const stats = [
    { title: "Total Clicks", value: actualSummary?.total_clicks ?? 0, icon: MousePointerClick, color: "text-blue-400", bg: "bg-blue-500/10" },
    { title: "Unique Visitors", value: actualSummary?.unique_clicks ?? 0, icon: Users, color: "text-green-400", bg: "bg-green-500/10" },
    { title: "Status", value: url.status, icon: BarChart3, color: "text-purple-400", bg: "bg-purple-500/10" },
  ]

  return (
    <div className="p-6">
      <button onClick={() => router.push("/urls")} className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to URLs
      </button>

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-muted-foreground break-all">/{url.short_code} — {url.original_url}</p>
        </div>
        <Select value={period} onChange={(e) => setPeriod(e.target.value)} className="w-32">
          <option value="24h">24 hours</option>
          <option value="7d">7 days</option>
          <option value="30d">30 days</option>
          <option value="all">All time</option>
        </Select>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        {stats.map((s) => {
          const Icon = s.icon
          return (
            <Card key={s.title}>
              <CardContent className="flex items-center gap-4 pt-6">
                <div className={`rounded-lg ${s.bg} p-3`}>
                  <Icon className={`size-6 ${s.color}`} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{s.title}</p>
                  <p className="text-2xl font-bold capitalize">{s.value}</p>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="mb-6">
        <Card>
          <CardHeader><CardTitle>Clicks Over Time</CardTitle></CardHeader>
          <CardContent>
            {timeseries?.data?.length ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={timeseries.data}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="clicks" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="py-12 text-center text-sm text-muted-foreground">No data yet</p>}
          </CardContent>
        </Card>
      </div>

      {devices && (
        <Tabs defaultValue="browsers">
          <TabsList>
            <TabsTrigger value="browsers"><Monitor className="mr-1 size-4" />Browsers</TabsTrigger>
            <TabsTrigger value="devices"><Smartphone className="mr-1 size-4" />Devices</TabsTrigger>
            <TabsTrigger value="os">OS</TabsTrigger>
            <TabsTrigger value="geo"><Globe className="mr-1 size-4" />Geo</TabsTrigger>
            <TabsTrigger value="utm"><Tags className="mr-1 size-4" />UTM</TabsTrigger>
            <TabsTrigger value="referrers"><ExternalLink className="mr-1 size-4" />Referrers</TabsTrigger>
          </TabsList>
          <TabsContent value="browsers">
            <Card>
              <CardContent className="pt-6">
                {devices.browsers.length ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={devices.browsers} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={100}
                        label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
                        {devices.browsers.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Pie>
                      <Tooltip /><Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <p className="py-12 text-center text-sm text-muted-foreground">No data yet</p>}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="devices">
            <Card>
              <CardContent className="pt-6">
                {devices.devices.length ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={devices.devices} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={100}
                        label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
                        {devices.devices.map((_, i) => <Cell key={i} fill={COLORS[(i + 3) % COLORS.length]} />)}
                      </Pie>
                      <Tooltip /><Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <p className="py-12 text-center text-sm text-muted-foreground">No data yet</p>}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="os">
            <Card>
              <CardContent className="pt-6">
                {devices.os.length ? (
                  <div className="space-y-2">
                    {devices.os.map((o) => (
                      <div key={o.name} className="flex items-center justify-between rounded-lg bg-muted px-4 py-2.5">
                        <span className="text-sm font-medium">{o.name}</span>
                        <span className="text-sm text-muted-foreground">{o.count}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="py-12 text-center text-sm text-muted-foreground">No data yet</p>}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="geo">
            <Card>
              <CardContent className="pt-6">
                {devices.geo.length ? (
                  <div className="space-y-2">
                    {devices.geo.map((g, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg bg-muted px-4 py-2.5">
                        <span className="text-sm font-medium">{g.city ? `${g.city}, ${g.country}` : g.country}</span>
                        <span className="text-sm text-muted-foreground">{g.count}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="py-12 text-center text-sm text-muted-foreground">No geo data yet</p>}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="utm">
            <Card>
              <CardContent className="pt-6">
                {utmData.length ? (
                  <div className="space-y-2">
                    {utmData.map((u, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg bg-muted px-4 py-2.5">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium">{u.source}</p>
                          <p className="text-xs text-muted-foreground">
                            {[u.medium, u.campaign].filter(Boolean).join(" / ") || "—"}
                          </p>
                        </div>
                        <span className="ml-3 shrink-0 text-sm text-muted-foreground">{u.count}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="py-12 text-center text-sm text-muted-foreground">No UTM data yet. Add utm_source to your URL to track campaigns.</p>}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="referrers">
            <Card>
              <CardContent className="pt-6">
                {refererData.length ? (
                  <div className="space-y-2">
                    {refererData.map((r, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg bg-muted px-4 py-2.5">
                        <span className="truncate text-sm font-medium" title={r.referer}>{r.referer}</span>
                        <span className="ml-3 shrink-0 text-sm text-muted-foreground">{r.count}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="py-12 text-center text-sm text-muted-foreground">No referer data yet</p>}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
