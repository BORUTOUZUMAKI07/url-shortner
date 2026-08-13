"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useMe, useWorkspaces, useUrls, useWorkspaceMembers, useDeleteUrlMutation } from "@/queries"
import { apiKeysApi } from "@/lib/api"

export function useDashboard() {
  const { data: user, isLoading: userLoading } = useMe()
  const { data: workspaces = [], isLoading: workspacesLoading } = useWorkspaces()
  const [wsId, setWsId] = useState<number | null>(null)
  const { data: members = [] } = useWorkspaceMembers(wsId)
  const { data: urlsData, error: urlsError } = useUrls(wsId, { limit: 50 })
  const urlList = urlsData?.items || []
  const totalUrlsCount = urlsData?.total || 0

  // The "Active" stat must count every active URL across the workspace, not
  // just the ones in the currently-fetched page (limit 50). A second query with
  // status=active uses the API's `total` field for an accurate count.
  const { data: activeData } = useUrls(wsId, { status: "active", limit: 1 })
  const activeUrlsCount = activeData?.total || 0

  // The daily API-key quota is enforced per-user (by plan) but tracked per key
  // in Redis; the backend now exposes an aggregate endpoint that sums the
  // per-key counters in a single round trip instead of one call per key.
  const { data: quota } = useQuery({
    queryKey: ["api-key-quota-summary"],
    queryFn: async () => {
      const q = await apiKeysApi.quotaSummary()
      return { used: q.used, limit: q.limit }
    },
  })

  const deleteUrl = useDeleteUrlMutation()

  const myRole = members.find(m => m.user_id === user?.id)?.role
  const canEdit = myRole === "admin" || myRole === "editor"
  const isLoading = userLoading || workspacesLoading

  async function handleDelete(id: number) {
    await deleteUrl.mutateAsync(id)
  }

  const activeUrls = urlList.filter((u) => u.status === "active")
  const error = urlsError instanceof Error ? urlsError.message : ""

  return {
    urlList, totalUrlsCount, workspaces, wsId, members, error, quota,
    myRole, canEdit, activeUrls, activeUrlsCount, isLoading,
    setWsId, handleDelete,
  }
}
