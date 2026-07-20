"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { useApiKeys, useCreateApiKeyMutation } from "@/queries"
import { Key, Plus, Copy, XCircle } from "lucide-react"

export default function ApiKeysPage() {
  const { data: keys = [], isLoading } = useApiKeys()
  const createKey = useCreateApiKeyMutation()
  const [newName, setNewName] = useState("")
  const [newKey, setNewKey] = useState<string | null>(null)

  async function handleCreate() {
    if (!newName.trim()) return
    const res = await createKey.mutateAsync(newName)
    setNewKey(res.key)
    setNewName("")
  }

  async function handleRevoke(id: number) {
    const { apiKeysApi } = await import("@/lib/api")
    await apiKeysApi.revoke(id)
    window.location.reload()
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">API Keys</h1>
        <p className="text-sm text-muted-foreground">Manage API keys for programmatic access.</p>
      </div>

      {newKey && (
        <Card className="mb-6 border-amber-500/30 bg-amber-500/10">
          <CardContent className="pt-6">
            <p className="mb-2 text-sm font-medium text-amber-300">Your new API key - copy it now, you won&apos;t see it again!</p>
            <div className="flex gap-2">
              <code className="flex-1 rounded border border-amber-500/30 bg-zinc-900 px-3 py-2 text-sm break-all text-amber-200">{newKey}</code>
              <Button variant="outline" size="sm" onClick={() => { navigator.clipboard.writeText(newKey); setNewKey(null) }}>
                <Copy className="mr-1 size-3" />Copy
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="mb-6 flex gap-2">
        <Input placeholder="Key name (e.g. CI/CD)" value={newName} onChange={(e) => setNewName(e.target.value)} className="max-w-xs" />
        <Button onClick={handleCreate} disabled={createKey.isPending} className="bg-blue-600 text-white hover:bg-blue-700">
          <Plus className="mr-1 size-4" />{createKey.isPending ? "Creating..." : "Create Key"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : keys.length === 0 ? (
            <p className="text-sm text-muted-foreground">No API keys yet. Create one above.</p>
          ) : (
            <div className="space-y-3">
              {keys.map((key) => (
                <div key={key.id} className="flex flex-col gap-2 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <Key className="size-4 text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{key.name}</p>
                      <p className="text-xs text-muted-foreground">Prefix: {key.prefix}...</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={key.status === "active" ? "success" : "secondary"}>{key.status}</Badge>
                    <Button variant="ghost" size="xs" onClick={() => handleRevoke(key.id)}>
                      <XCircle className="size-4 text-destructive" />
                    </Button>
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
