"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { auth, foldersApi, workspacesApi } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Plus, Trash2, FolderOpen, Pencil } from "lucide-react"

export default function FoldersPage() {
  const router = useRouter()
  const { setUser } = useAuthStore()
  const [newName, setNewName] = useState("")
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState("")
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

  const { data: folders = [] } = useQuery({
    queryKey: ["folders", wsId],
    queryFn: () => foldersApi.list(wsId!),
    enabled: !!wsId,
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => foldersApi.create(name, wsId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders", wsId] })
      setNewName("")
    }
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => foldersApi.update(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders", wsId] })
      setEditingId(null)
      setEditName("")
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => foldersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders", wsId] })
    }
  })

  async function handleCreate() {
    if (!newName.trim() || !wsId) return
    createMutation.mutate(newName)
  }

  async function handleRename(id: number) {
    if (!editName.trim()) return
    updateMutation.mutate({ id, name: editName })
  }

  async function handleDelete(id: number) {
    deleteMutation.mutate(id)
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Folders</h1>
        <p className="text-sm text-muted-foreground">Group your URLs into folders.</p>
      </div>

      <Card className="mb-6">
        <CardHeader><CardTitle>Create Folder</CardTitle></CardHeader>
        <CardContent className="flex gap-2">
          <Input placeholder="Folder name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <Button onClick={handleCreate} className="bg-blue-600 text-white hover:bg-blue-700">
            <Plus className="mr-1 size-4" />Create
          </Button>
        </CardContent>
      </Card>

      {folders.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
          <FolderOpen className="mx-auto mb-3 size-10 text-muted-foreground" />
          <p className="text-lg font-medium">No folders yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Create folders to organize your URLs.</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {folders.map((f) => (
            <Card key={f.id} className="transition-colors hover:bg-muted/30">
              <CardHeader className="flex flex-row items-center justify-between">
                {editingId === f.id ? (
                  <div className="flex flex-1 items-center gap-2">
                    <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="h-8" />
                    <Button size="xs" onClick={() => handleRename(f.id)}>Save</Button>
                    <Button variant="ghost" size="xs" onClick={() => setEditingId(null)}>Cancel</Button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-2">
                      <FolderOpen className="size-4 text-muted-foreground" />
                      <CardTitle className="text-base">{f.name}</CardTitle>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="xs" onClick={() => { setEditingId(f.id); setEditName(f.name) }}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button variant="ghost" size="xs" onClick={() => handleDelete(f.id)}>
                        <Trash2 className="size-3.5 text-destructive" />
                      </Button>
                    </div>
                  </>
                )}
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
