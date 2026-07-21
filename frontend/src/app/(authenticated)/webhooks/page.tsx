"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { auth, webhooksApi, workspacesApi } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Webhook as WebhookIcon, Plus, Trash2, Radio } from "lucide-react"
import Link from "next/link"

const EVENT_OPTIONS = ["url.created", "url.clicked", "url.expired", "url.deleted"]

export default function WebhooksPage() {
  const router = useRouter()
  const { setUser } = useAuthStore()
  const [url, setUrl] = useState("")
  const [events, setEvents] = useState<string[]>(["url.created"])
  const [showForm, setShowForm] = useState(false)
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

  const wsId = workspaces?.[0]?.id

  const { data: hooks = [] } = useQuery({
    queryKey: ["webhooks", wsId],
    queryFn: () => webhooksApi.list(wsId!),
    enabled: !!wsId,
  })

  const createMutation = useMutation({
    mutationFn: (data: { url: string; event_types: string[] }) => webhooksApi.create(wsId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks", wsId] })
      setUrl("")
      setEvents(["url.created"])
      setShowForm(false)
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => webhooksApi.delete(id, wsId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks", wsId] })
    }
  })

  function toggleEvent(e: string) {
    setEvents((prev) => prev.includes(e) ? prev.filter((x) => x !== e) : [...prev, e])
  }

  async function handleCreate() {
    if (!url || !wsId) return
    createMutation.mutate({ url, event_types: events })
  }

  async function handleDelete(id: number) {
    if (!wsId) return
    deleteMutation.mutate(id)
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Webhooks</h1>
          <p className="text-sm text-muted-foreground">Receive real-time events about your URLs.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/webhooks/receiver">
            <Button variant="outline"><Radio className="mr-1 size-4" />Receiver Log</Button>
          </Link>
          <Button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white hover:bg-blue-700">
            <Plus className="mr-1 size-4" />Add Webhook
          </Button>
        </div>
      </div>

      {showForm && (
        <Card className="mb-6">
          <CardHeader><CardTitle>New Webhook</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Input placeholder="https://example.com/webhook" value={url} onChange={(e) => setUrl(e.target.value)} />
            <div>
              <p className="mb-2 text-sm font-medium">Event Types</p>
              <div className="flex flex-wrap gap-2">
                {EVENT_OPTIONS.map((e) => (
                  <button
                    key={e}
                    onClick={() => toggleEvent(e)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                      events.includes(e)
                        ? "border-blue-500 bg-blue-500/20 text-blue-300"
                        : "border-zinc-700 bg-background text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button onClick={handleCreate}>Create</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {hooks.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
          <WebhookIcon className="mx-auto mb-3 size-10 text-muted-foreground" />
          <p className="text-lg font-medium">No webhooks yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Create a webhook to receive real-time events.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {hooks.map((h) => (
            <div key={h.id} className="flex items-start justify-between rounded-lg border bg-card px-4 py-3 transition-colors hover:bg-muted/50 gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium break-all">{h.url}</span>
                  <Badge variant={h.is_active ? "success" : "secondary"} className="shrink-0">{h.is_active ? "Active" : "Disabled"}</Badge>
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {h.events.map((et) => (
                    <Badge key={et} variant="outline" className="text-xs">{et}</Badge>
                  ))}
                </div>
              </div>
              <Button variant="ghost" size="xs" onClick={() => handleDelete(h.id)} className="shrink-0">
                <Trash2 className="size-3.5 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
