"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  auth, urls, workspacesApi, foldersApi, tagsApi,
  apiKeysApi, webhooksApi, favoritesApi, auditApi,
} from "@/lib/api"

// --- Auth ---
// The single source of truth for the current user — there is deliberately no
// other copy (no zustand store; see AGENTS.md, "Frontend Batch 3").
//
// Reading: every component that needs the user calls useMe(). The layout's
// <Sidebar /> mounts one per authenticated page, warming the shared ["me"]
// entry, so each page's own useMe() reuses the same fetch.
//
// Writing: never mutate this hook's result by hand — write to the cache entry
// instead, so every reader re-renders from one place:
//   - new session (login / oauth handoff): `qc.setQueryData(["me"], user)`
//   - user fields change (profile email/avatar, billing plan): either
//     `qc.setQueryData(["me"], { ...user, field: value })` (optimistic, from a
//     mutation response) or `qc.invalidateQueries({ queryKey: ["me"] })`
//     (refetch server truth — enable-admin uses this).
//   - signed out: `qc.setQueryData(["me"], null)`.
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => auth.me(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}

// --- URLs ---
export function useUrls(workspaceId: number | null, params?: { folder_id?: number; tag?: string; search?: string; status?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["urls", workspaceId, params],
    queryFn: () => urls.list(workspaceId, params),
    // Hold the previous page's rows while the next one loads.
    //
    // `params` is part of the key, so changing a filter makes this a different
    // query: with no placeholder, `data` is undefined for the new key and the
    // list rendered its empty state — "No URLs found" plus a "create your first
    // URL" call to action — for the duration of every request. The search box
    // is debounced, so that flash happened on each pause in typing.
    placeholderData: (prev) => prev,
  })
}

export function useUrl(id: number) {
  return useQuery({
    queryKey: ["url", id],
    queryFn: () => urls.get(id),
    enabled: !!id,
  })
}

export function useCreateUrlMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof urls.create>[0]) => urls.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["urls"] }),
  })
}

export function useDeleteUrlMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => urls.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["urls"] }),
  })
}

// --- Workspaces ---
export function useWorkspaces() {
  return useQuery({
    queryKey: ["workspaces"],
    queryFn: () => workspacesApi.list(),
  })
}

export function useWorkspaceMembers(workspaceId: number | null) {
  return useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => workspacesApi.members(workspaceId!),
    enabled: !!workspaceId,
  })
}

// --- Folders ---
export function useFolders(workspaceId: number | null) {
  return useQuery({
    queryKey: ["folders", workspaceId],
    queryFn: () => foldersApi.list(workspaceId!),
    enabled: !!workspaceId,
  })
}

// --- Tags ---
export function useTags(workspaceId: number | null) {
  return useQuery({
    queryKey: ["tags", workspaceId],
    queryFn: () => tagsApi.list(workspaceId!),
    enabled: !!workspaceId,
  })
}

// --- API Keys ---
export function useApiKeys() {
  return useQuery({
    queryKey: ["api-keys"],
    queryFn: () => apiKeysApi.list(),
  })
}

export function useCreateApiKeyMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => apiKeysApi.create(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  })
}

// --- Favorites ---
export function useFavorites() {
  return useQuery({
    queryKey: ["favorites"],
    // Backend PaginationParams.limit defaults to 20 — fetch the whole list so
    // star state on /urls is correct for every favorite, not just the first 20.
    queryFn: () => favoritesApi.list(0, 100),
  })
}

export function useAddFavoriteMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (url_id: number) => favoritesApi.add(url_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  })
}

export function useRemoveFavoriteMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (url_id: number) => favoritesApi.remove(url_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  })
}

// --- Webhooks ---
export function useWebhooks(workspaceId: number | null) {
  return useQuery({
    queryKey: ["webhooks", workspaceId],
    queryFn: () => webhooksApi.list(workspaceId!),
    enabled: !!workspaceId,
  })
}

// --- Audit Logs ---
export function useAuditLogs(workspaceId: number | null, skip?: number, limit?: number) {
  return useQuery({
    queryKey: ["audit-logs", workspaceId, skip, limit],
    queryFn: () => auditApi.list(workspaceId!, skip, limit),
    enabled: !!workspaceId,
  })
}
