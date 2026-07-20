"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { auth, webhookReceiverApi, workspacesApi, ReceivedWebhookEvent } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Webhook, RefreshCw, Copy, CheckCircle2, XCircle, Terminal } from "lucide-react"

export default function WebhookReceiverPage() {
  const router = useRouter()
  const { setUser } = useAuthStore()
  const [selected, setSelected] = useState<ReceivedWebhookEvent | null>(null)
  const [copied, setCopied] = useState(false)
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

  const wsId = workspaces?.[0]?.id || null

  const { data: events = [], refetch: fetchEvents } = useQuery({
    queryKey: ["webhook_events", wsId],
    queryFn: () => webhookReceiverApi.list(wsId!),
    enabled: !!wsId,
    refetchInterval: 5000,
  })

  const receiverUrl = wsId ? `${window.location.origin}/api/v1/webhook-receiver` : ""

  async function copyUrl() {
    await navigator.clipboard.writeText(receiverUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function formatHeaders(raw: string | null): string {
    if (!raw) return "{}"
    try {
      const h = JSON.parse(raw)
      const allowed = ["content-type", "content-length", "x-webhook-signature", "x-webhook-event"]
      return JSON.stringify(Object.fromEntries(Object.entries(h).filter(([k]) => allowed.includes(k))), null, 2)
    } catch { return raw }
  }

  function formatPayload(raw: string): string {
    try { return JSON.stringify(JSON.parse(raw), null, 2) } catch { return raw }
  }

  const eventColors: Record<string, string> = {
    "url.created": "bg-green-500/10 text-green-400",
    "url.clicked": "bg-blue-500/10 text-blue-400",
    "url.expired": "bg-amber-500/10 text-amber-400",
    "url.deleted": "bg-red-500/10 text-red-400",
  }

  if (!wsId) return <div className="p-6"><p>Loading workspace...</p></div>

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Webhook Receiver</h1>
        <p className="text-sm text-muted-foreground">View webhook events delivered to your app in real time.</p>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Terminal className="size-5 text-blue-400" />
            <CardTitle className="text-base">Receiver URL</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="mb-2 text-sm text-muted-foreground">
            Register this URL as your webhook callback to receive events here.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-muted px-3 py-2 text-sm font-mono break-all">{receiverUrl}</code>
            <Button variant="outline" size="sm" onClick={copyUrl}>
              {copied ? <CheckCircle2 className="size-4 text-green-400" /> : <Copy className="size-4" />}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between mb-4 gap-2">
        <p className="text-sm text-muted-foreground">{events.length} event{events.length !== 1 ? "s" : ""} received</p>
        <Button variant="outline" size="sm" onClick={() => fetchEvents()} className="shrink-0">
          <RefreshCw className="mr-1 size-3.5" /> Refresh
        </Button>
      </div>

      {events.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
          <Webhook className="mx-auto mb-3 size-10 text-muted-foreground" />
          <p className="text-lg font-medium">No events received yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Create a webhook with callback URL <code className="rounded bg-muted px-1">{receiverUrl}</code> and trigger an event.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2 max-h-[50vh] overflow-y-auto lg:max-h-[70vh]">
            {events.map((ev) => (
              <div
                key={ev.id}
                onClick={() => setSelected(ev)}
                className={`flex items-center gap-3 rounded-lg border bg-card px-4 py-3 cursor-pointer transition-colors hover:bg-muted/50 ${
                  selected?.id === ev.id ? "ring-2 ring-blue-500" : ""
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${eventColors[ev.event_type] || "bg-muted text-muted-foreground"}`}>
                      {ev.event_type}
                    </span>
                    {ev.signature ? (
                      ev.signature_valid ? (
                        <CheckCircle2 className="size-3.5 text-green-400" />
                      ) : (
                        <XCircle className="size-3.5 text-red-400" />
                      )
                    ) : (
                      <XCircle className="size-3.5 text-muted-foreground" />
                    )}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {new Date(ev.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="lg:sticky lg:top-6 space-y-4">
            {selected ? (
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge className={eventColors[selected.event_type] || ""}>{selected.event_type}</Badge>
                    {selected.signature ? (
                      selected.signature_valid ? (
                        <Badge variant="success">Signature Valid</Badge>
                      ) : (
                        <Badge variant="destructive">Invalid Signature</Badge>
                      )
                    ) : (
                      <Badge variant="secondary">No Signature</Badge>
                    )}
                    <span className="ml-auto text-xs text-muted-foreground">{new Date(selected.created_at).toLocaleString()}</span>
                  </div>
                  {selected.source_ip && (
                    <p className="text-xs text-muted-foreground">Source: {selected.source_ip}</p>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Headers</p>
                    <pre className="rounded bg-muted p-2 text-xs overflow-x-auto">{formatHeaders(selected.headers)}</pre>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Payload</p>
                    <pre className="rounded bg-muted p-2 text-xs overflow-x-auto max-h-64 overflow-y-auto">{formatPayload(selected.payload)}</pre>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
                <Terminal className="mx-auto mb-3 size-10 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Select an event to inspect</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
