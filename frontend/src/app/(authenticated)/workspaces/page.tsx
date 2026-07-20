"use client"

import { Suspense, useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { auth, getErrorMessage, workspacesApi } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Plus, Users, Building2, XCircle, UserPlus, LogIn, Trash2, Pencil } from "lucide-react"

export default function WorkspacesPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="size-6 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
      </div>
    }>
      <WorkspacesPageInner />
    </Suspense>
  )
}

function WorkspacesPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, setUser } = useAuthStore()
  const queryClient = useQueryClient()

  const [newName, setNewName] = useState("")
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("editor")
  const [selectedWs, setSelectedWs] = useState<number | null>(null)
  const [inviteToken, setInviteToken] = useState("")
  const [renaming, setRenaming] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState("")
  const [deleting, setDeleting] = useState<number | null>(null)

  const { isLoading: authLoading } = useQuery({
    queryKey: ["authMe"],
    queryFn: async () => {
      try {
        const token = searchParams.get("invite_token")
        if (token) sessionStorage.setItem("invite_token", token)
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

  useEffect(() => {
    const token = searchParams.get("invite_token")
    if (token) {
      workspacesApi.acceptInvite(token).then(() => {
        toast.success("Workspace invite accepted!")
        router.replace("/workspaces")
      }).catch((err: unknown) => {
        toast.error(getErrorMessage(err, "Failed to accept invite"))
      })
    }
  }, [searchParams, router])

  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspacesApi.list,
    enabled: !authLoading
  })

  // We fetch members and invites only for the selected workspace to optimize
  const { data: selectedMembers = [] } = useQuery({
    queryKey: ["workspace_members", selectedWs],
    queryFn: () => workspacesApi.members(selectedWs!),
    enabled: !!selectedWs
  })

  const { data: selectedInvites = [] } = useQuery({
    queryKey: ["workspace_invites", selectedWs],
    queryFn: () => workspacesApi.listInvites(selectedWs!),
    enabled: !!selectedWs
  })

  // Mock the old state shape for the UI
  const members = selectedWs ? { [selectedWs]: selectedMembers } : {}
  const invites = selectedWs ? { [selectedWs]: selectedInvites } : {}

  async function handleCreate() {
    if (!newName.trim()) return
    await workspacesApi.create(newName)
    queryClient.invalidateQueries({ queryKey: ["workspaces"] })
    setNewName("")
  }

  async function handleInvite() {
    if (!selectedWs || !inviteEmail.trim()) return
    try {
      const inv = await workspacesApi.invite(selectedWs, inviteEmail.trim(), inviteRole)
      toast.success(`Invitation sent to ${inviteEmail.trim()}`, { description: inv.token ? `Token: ${inv.token}` : undefined, duration: 10000 })
      queryClient.invalidateQueries({ queryKey: ["workspace_members", selectedWs] })
      queryClient.invalidateQueries({ queryKey: ["workspace_invites", selectedWs] })
      setInviteEmail("")
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Failed to send invite"))
    }
  }

  async function handleRemoveMember(wsId: number, memberId: number) {
    await workspacesApi.removeMember(wsId, memberId)
    queryClient.invalidateQueries({ queryKey: ["workspace_members", wsId] })
  }

  async function handleChangeRole(wsId: number, memberId: number, role: string) {
    await workspacesApi.updateMemberRole(wsId, memberId, role)
    queryClient.invalidateQueries({ queryKey: ["workspace_members", wsId] })
  }

  async function handleRename(wsId: number) {
    if (!renameValue.trim()) return
    await workspacesApi.rename(wsId, renameValue.trim())
    queryClient.invalidateQueries({ queryKey: ["workspaces"] })
    setRenaming(null)
    setRenameValue("")
  }

  async function handleDelete(wsId: number) {
    await workspacesApi.delete(wsId)
    queryClient.invalidateQueries({ queryKey: ["workspaces"] })
    setDeleting(null)
  }

  async function handleCancelInvite(wsId: number, inviteId: number) {
    try {
      await workspacesApi.cancelInvite(wsId, inviteId)
      queryClient.invalidateQueries({ queryKey: ["workspace_invites", wsId] })
      toast.success("Invite cancelled")
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Failed to cancel invite"))
    }
  }

  async function handleAcceptInvite() {
    if (!inviteToken.trim()) return
    try {
      await workspacesApi.acceptInvite(inviteToken.trim())
      toast.success("Invite accepted successfully!")
      setInviteToken("")
      queryClient.invalidateQueries({ queryKey: ["workspaces"] })
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Failed to accept invite"))
    }
  }

  const myRole = (wsId: number) => members[wsId]?.find(m => m.user_id === user?.id)?.role
  const isOwner = (wsId: number) => workspaces.find(w => w.id === wsId)?.owner_id === user?.id
  const isAdmin = (wsId: number) => isOwner(wsId) || myRole(wsId) === "admin"
  const canManage = (wsId: number) => isAdmin(wsId)

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold">Workspaces</h1>
            {user?.is_superadmin && <Badge className="bg-purple-600 text-white">Superadmin</Badge>}
          </div>
          <p className="text-sm text-muted-foreground">Collaborate with your team.</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline"><LogIn className="mr-1 size-4" />Accept Invite</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Accept Workspace Invite</DialogTitle></DialogHeader>
            <p className="text-sm text-muted-foreground">Paste the invite token from the email to accept.</p>
            <div className="flex gap-2">
              <Input placeholder="Paste invite token" value={inviteToken} onValueChange={(v) => setInviteToken(v)} />
              <Button onClick={handleAcceptInvite}>Accept</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="mb-6">
        <CardHeader><CardTitle>Create Workspace</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 sm:flex-row">
          <Input placeholder="Workspace name" value={newName} onValueChange={(v) => setNewName(v)} className="w-full" />
          <Button onClick={handleCreate} className="bg-blue-600 text-white hover:bg-blue-700 shrink-0">
            <Plus className="mr-1 size-4" />Create
          </Button>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {workspaces.length === 0 ? (
          <div className="rounded-xl border-2 border-dashed border-zinc-700 p-16 text-center">
            <Building2 className="mx-auto mb-3 size-10 text-muted-foreground" />
            <p className="text-lg font-medium">No workspaces yet</p>
            <p className="mt-1 text-sm text-muted-foreground">Create a workspace to collaborate.</p>
          </div>
        ) : (
          workspaces.map((ws) => (
            <Card key={ws.id}>
              <CardHeader className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  {renaming === ws.id ? (
                    <div className="flex gap-2">
                      <Input value={renameValue} onValueChange={(v) => setRenameValue(v)}
                        className="h-8 w-48" autoFocus onKeyDown={(e) => e.key === "Enter" && handleRename(ws.id)} />
                      <Button size="sm" onClick={() => handleRename(ws.id)}>Save</Button>
                      <Button size="sm" variant="outline" onClick={() => setRenaming(null)}>Cancel</Button>
                    </div>
                  ) : (
                    <>
                      <CardTitle>{ws.name}</CardTitle>
                      {isOwner(ws.id) && (
                        <Button variant="ghost" size="xs" onClick={() => { setRenaming(ws.id); setRenameValue(ws.name) }}>
                          <Pencil className="size-3.5" />
                        </Button>
                      )}
                    </>
                  )}
                  <p className="text-xs text-muted-foreground">Owner ID: {ws.owner_id}</p>
                </div>
                <div className="flex items-center gap-2">
                  {isOwner(ws.id) && (
                    <>
                      <Button variant="outline" size="sm"
                        onClick={() => setDeleting(ws.id)}
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                      {deleting === ws.id && (
                        <div className="flex gap-1">
                          <Button size="sm" variant="destructive" onClick={() => handleDelete(ws.id)}>Confirm</Button>
                          <Button size="sm" variant="outline" onClick={() => setDeleting(null)}>Cancel</Button>
                        </div>
                      )}
                    </>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedWs(selectedWs === ws.id ? null : ws.id)}
                  >
                    <Users className="mr-1 size-4" /> Members ({(members[ws.id] || []).length})
                  </Button>
                </div>
              </CardHeader>

              {selectedWs === ws.id && (
                <CardContent>
                  <p className="mb-3 text-sm font-medium">Members</p>
                  <div className="mb-4 space-y-2">
                    {members[ws.id]?.map((m) => (
                      <div key={m.id} className="flex flex-col gap-2 rounded-lg bg-muted px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium break-all">{m.email}</span>
                          {isOwner(ws.id) ? (
                            <Select value={m.role} onChange={(e) => handleChangeRole(ws.id, m.id, e.target.value)}
                              className="h-7 w-24 text-xs">
                              <option value="viewer">Viewer</option>
                              <option value="editor">Editor</option>
                              <option value="admin">Admin</option>
                            </Select>
                          ) : (
                            <Badge variant="outline" className="capitalize text-xs">{m.role}</Badge>
                          )}
                        </div>
                        {isAdmin(ws.id) && m.user_id !== user?.id && (
                          <Button variant="ghost" size="xs" onClick={() => handleRemoveMember(ws.id, m.id)}>
                            <XCircle className="size-3.5 text-destructive" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>

                  {invites[ws.id]?.length > 0 && (
                    <>
                      <p className="mb-2 text-sm font-medium">Pending Invites</p>
                      <div className="mb-4 space-y-2">
                        {invites[ws.id]?.map((inv) => (
                          <div key={inv.id} className="flex flex-col gap-2 rounded-lg bg-amber-500/10 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                            <span className="text-sm break-all">{inv.email} <span className="text-xs text-muted-foreground capitalize">({inv.role})</span>{inv.token && <span className="ml-2 text-xs text-muted-foreground">token: {inv.token.substring(0, 8)}...</span>}</span>
                            {isAdmin(ws.id) && (
                              <Button variant="ghost" size="xs" onClick={() => handleCancelInvite(ws.id, inv.id)}>
                                <XCircle className="size-3.5 text-destructive" />
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {canManage(ws.id) && (
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Input placeholder="Email to invite" value={inviteEmail} onValueChange={(v) => setInviteEmail(v)} className="w-full" />
                      <Select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="w-full sm:w-28">
                        <option value="viewer">Viewer</option>
                        <option value="editor">Editor</option>
                        <option value="admin">Admin</option>
                      </Select>
                      <Button onClick={handleInvite}><UserPlus className="mr-1 size-4" />Invite</Button>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
