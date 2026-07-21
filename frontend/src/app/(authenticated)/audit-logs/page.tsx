"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { auth, workspacesApi, auditApi } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { History, ShieldAlert, ChevronDown, ChevronUp, Loader2 } from "lucide-react"

function formatJson(raw: string | null): string {
  if (!raw) return ""
  try { return JSON.stringify(JSON.parse(raw), null, 2) } catch { return raw }
}

export default function AuditLogsPage() {
  const router = useRouter()
  const { setUser } = useAuthStore()
  const [expanded, setExpanded] = useState<number | null>(null)

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

  const { data: workspaces, isLoading: isLoadingWs } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspacesApi.list,
    enabled: !authLoading
  })

  const wsId = workspaces?.[0]?.id

  const { data: logs = [], isLoading: isLoadingLogs } = useQuery({
    queryKey: ["auditLogs", wsId],
    queryFn: () => auditApi.list(wsId!),
    enabled: !!wsId,
  })

  const actionColors: Record<string, string> = {
    create: "bg-green-500/10 text-green-400",
    update: "bg-blue-500/10 text-blue-400",
    delete: "bg-red-500/10 text-red-400",
    login: "bg-purple-500/10 text-purple-400",
    invite: "bg-amber-500/10 text-amber-400",
    update_role: "bg-amber-500/10 text-amber-400",
    rename: "bg-amber-500/10 text-amber-400",
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Audit Logs</h1>
        <p className="text-sm text-muted-foreground">Track all events across your workspace.</p>
      </div>

      {isLoadingWs || isLoadingLogs ? (
        <div className="flex h-32 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : logs.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
          <ShieldAlert className="mx-auto mb-3 size-10 text-muted-foreground" />
          <p className="text-lg font-medium">No audit logs yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Actions in your workspace will appear here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-3 rounded-lg border bg-card px-4 py-3">
              <div className="mt-0.5">
                <History className="size-4 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${actionColors[log.action] || "bg-muted text-muted-foreground"}`}>
                    {log.action}
                  </span>
                  <span className="text-sm text-muted-foreground">{log.resource_type}</span>
                  <span className="text-xs text-muted-foreground">#{log.resource_id}</span>
                  <Badge variant="outline" className="ml-auto text-xs">
                    {new Date(log.created_at).toLocaleString()}
                  </Badge>
                </div>
                {log.before_state || log.after_state ? (
                  <div className="mt-2">
                    <button
                      onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                      className="flex items-center gap-1 text-xs text-blue-400 hover:underline"
                    >
                      {expanded === log.id ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                      Show details
                    </button>
                    {expanded === log.id && (
                      <div className="mt-2 space-y-2 text-xs">
                        {log.before_state && (
                          <div>
                            <p className="font-medium text-muted-foreground">Before</p>
                            <pre className="rounded bg-muted p-2 overflow-x-auto max-h-48 overflow-y-auto">{formatJson(log.before_state)}</pre>
                          </div>
                        )}
                        {log.after_state && (
                          <div>
                            <p className="font-medium text-muted-foreground">After</p>
                            <pre className="rounded bg-muted p-2 overflow-x-auto max-h-48 overflow-y-auto">{formatJson(log.after_state)}</pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
