"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { auth, tagsApi, workspacesApi } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Plus, X, Tags as TagsIcon } from "lucide-react"

export default function TagsPage() {
  const router = useRouter()
  const { setUser } = useAuthStore()
  const [newName, setNewName] = useState("")
  const [selectedWsId, setSelectedWsId] = useState<number | null>(null)
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

  const { data: tags = [] } = useQuery({
    queryKey: ["tags", wsId],
    queryFn: () => tagsApi.list(wsId!),
    enabled: !!wsId,
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => tagsApi.create(name, wsId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags", wsId] })
      setNewName("")
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => tagsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags", wsId] })
    }
  })

  async function handleCreate() {
    if (!newName.trim() || !wsId) return
    createMutation.mutate(newName)
  }

  async function handleDelete(id: number) {
    deleteMutation.mutate(id)
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight">Tags</h1>
        <Select value={String(wsId ?? "")} onChange={(e) => setSelectedWsId(Number(e.target.value))} className="w-44">
          {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </Select>
        <p className="text-sm text-muted-foreground">Organize URLs with tags.</p>
      </div>

      <Card className="mb-6">
        <CardHeader><CardTitle>Create Tag</CardTitle></CardHeader>
        <CardContent className="flex gap-2">
          <Input placeholder="Tag name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <Button onClick={handleCreate} className="bg-blue-600 text-white hover:bg-blue-700">
            <Plus className="mr-1 size-4" />Create
          </Button>
        </CardContent>
      </Card>

      {tags.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
          <TagsIcon className="mx-auto mb-3 size-10 text-muted-foreground" />
          <p className="text-lg font-medium">No tags yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Create tags to organize your URLs.</p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {tags.map((t) => (
            <Badge key={t.id} variant="secondary" className="gap-1 py-1.5 pl-3 pr-2 text-sm">
              {t.name}
              <button onClick={() => handleDelete(t.id)} className="ml-1 rounded-full p-0.5 hover:bg-muted">
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
