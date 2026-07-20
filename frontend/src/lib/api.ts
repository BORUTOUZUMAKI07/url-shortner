import { clearTokenCookies, setTokenCookie } from "@/lib/token-cookie"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

function getToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem("access_token")
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem("refresh_token")
  if (!refreshToken) return false
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const data = await res.json()
    localStorage.setItem("access_token", data.access_token)
    if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token)
    return true
  } catch { return false }
}

function clearTokens() {
  localStorage.removeItem("access_token")
  localStorage.removeItem("refresh_token")
  clearTokenCookies()
}

async function handleUnauthorized() {
  const refreshed = await tryRefresh()
  if (refreshed) return true
  clearTokens()
  if (typeof window !== "undefined") window.location.href = "/login"
  return false
}

async function rawFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string>),
  }
  if (token) headers["Authorization"] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (res.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/register") && !path.startsWith("/auth/refresh")) {
    const recovered = await handleUnauthorized()
    if (recovered) {
      const newToken = getToken()
      headers["Authorization"] = `Bearer ${newToken}`
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers })
      if (retry.ok) return retry.json()
    }
    throw new Error("Session expired. Please login again.")
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body)
    throw new Error(msg || "Request failed")
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export function getErrorMessage(error: unknown, fallback = "Request failed"): string {
  return error instanceof Error ? error.message : fallback
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  return rawFetch<T>(path, options)
}

export async function apiFetchBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  if (token) headers["Authorization"] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    const recovered = await handleUnauthorized()
    if (recovered) {
      const newToken = getToken()
      headers["Authorization"] = `Bearer ${newToken}`
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers })
      if (retry.ok) return retry.blob()
    }
    throw new Error("Session expired. Please login again.")
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body)
    throw new Error(msg || "Request failed")
  }
  return res.blob()
}

export interface User {
  id: number; email: string; is_verified: boolean; role: string; plan: string; is_superadmin: boolean; avatar_url: string | null; created_at: string
}
export interface Token { access_token: string; refresh_token?: string; token_type: string }
export interface URLItem {
  id: number; short_code: string; original_url: string; workspace_id: number
  folder_id: number | null; custom_alias: string | null; domain: string | null
  is_ab_test: boolean; is_one_time: boolean; ios_url: string | null; android_url: string | null
  expires_at: string | null; status: string; qr_code: string | null; created_at: string
  tags?: string[]
}
export interface Workspace { id: number; name: string; owner_id: number; created_at: string }
export interface WorkspaceMember { id: number; workspace_id: number; user_id: number; email: string; role: string; joined_at: string }
export interface Folder { id: number; name: string; workspace_id: number; created_at: string }
export interface Tag { id: number; name: string; workspace_id: number; created_at: string }
export interface ApiKey {
  id: number; name: string; prefix: string; status: string; expires_at: string | null
  last_used_at: string | null; created_at: string
}
export interface ApiKeyCreateResponse extends ApiKey { key: string }
export interface Webhook { id: number; url: string; events: string[]; is_active: boolean; created_at: string }
export interface ReceivedWebhookEvent { id: number; webhook_id: number | null; workspace_id: number; event_type: string; payload: string; headers: string | null; signature: string | null; signature_valid: boolean; source_ip: string | null; created_at: string }
export interface AnalyticsSummary { short_code: string; total_clicks: number; unique_clicks: number; last_clicked_at: string | null }
export interface AnalyticsTimeseries { short_code: string; days: number; data: { date: string; clicks: number }[] }
export interface DeviceBreakdown { name: string; count: number }
export interface GeoBreakdown { country: string; city: string; count: number }
export interface AnalyticsDevices { short_code: string; browsers: DeviceBreakdown[]; os: DeviceBreakdown[]; devices: DeviceBreakdown[]; geo: GeoBreakdown[] }
export interface UTMItem { source: string; medium: string; campaign: string; count: number }
export interface RefererItem { referer: string; count: number }
export interface AuditLog { id: number; action: string; resource_type: string; resource_id: number; user_id: number; before_state: string | null; after_state: string | null; created_at: string }
export interface WorkspaceInvite { id: number; workspace_id: number; email: string; invited_by: number; role: string; status: string; token?: string; expires_at: string; created_at: string }
export interface Favorite { id: number; url_id: number; created_at: string }
export interface FavoriteCheck { favorited: boolean }

export const auth = {
  login: (email: string, password: string) => apiFetch<Token>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) => apiFetch<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => apiFetch<User>("/auth/me"),
  refresh: (refresh_token: string) => apiFetch<Token>("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token }) }),
  logout: () => apiFetch<{ detail: string }>("/auth/logout", { method: "POST" }),
  forgotPassword: (email: string) => apiFetch<{ detail: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, new_password: string) => apiFetch<{ detail: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) }),
  verifyEmail: (token: string) => apiFetch<{ detail: string }>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),
  providers: () => apiFetch<{ providers: string[] }>("/auth/providers"),
  oauth: async (provider: string) => {
    const res = await fetch(`${API_BASE}/auth/oauth/${provider}`, { method: "POST" })
    if (!res.ok) throw new Error("Failed to initiate OAuth")
    return res.json() as Promise<{ authorization_url: string }>
  },
}

export const urls = {
  create: (data: {
    original_url: string; workspace_id: number;
    custom_alias?: string; folder_id?: number; password?: string;
    expires_at?: string; tags?: string[]; is_one_time?: boolean;
    is_ab_test?: boolean; ios_url?: string; android_url?: string;
  }) => apiFetch<URLItem>("/urls", { method: "POST", body: JSON.stringify(data) }),
  list: (workspace_id: number | null, params?: { folder_id?: number; tag?: string; search?: string; status?: string; skip?: number; limit?: number }) => {
    const q = new URLSearchParams()
    if (workspace_id) q.set("workspace_id", String(workspace_id))
    if (params?.folder_id) q.set("folder_id", String(params.folder_id))
    if (params?.tag) q.set("tag", params.tag)
    if (params?.search) q.set("search", params.search)
    if (params?.status) q.set("status", params.status)
    if (params?.skip) q.set("skip", String(params.skip))
    if (params?.limit) q.set("limit", String(params.limit))
    return apiFetch<{items: URLItem[], total: number}>(`/urls?${q}`)
  },
  get: (id: number) => apiFetch<URLItem>(`/urls/${id}`),
  update: (id: number, data: {
    original_url?: string; folder_id?: number | null; status?: string;
    expires_at?: string | null; password?: string;
    is_ab_test?: boolean; ios_url?: string; android_url?: string;
    tags?: string[];
  }) => apiFetch<URLItem>(`/urls/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: number) => apiFetch<void>(`/urls/${id}`, { method: "DELETE" }),
  getQr: (id: number) => apiFetch<{ qr_code: string }>(`/urls/${id}/qr`),
  analytics: (short_code: string, days?: number) => {
    const q = days ? `?days=${days}` : ""
    return Promise.all([
      apiFetch<AnalyticsSummary>(`/analytics/${short_code}/summary${q}`),
      apiFetch<AnalyticsTimeseries>(`/analytics/${short_code}/timeseries${q}`),
    ])
  },
  devices: (short_code: string) =>
    apiFetch<AnalyticsDevices>(`/analytics/${short_code}/devices`),
  utm: (short_code: string) =>
    apiFetch<{ short_code: string; data: UTMItem[] }>(`/analytics/${short_code}/utm`),
  referrers: (short_code: string) =>
    apiFetch<{ short_code: string; data: RefererItem[] }>(`/analytics/${short_code}/referrers`),
}

export const workspacesApi = {
  list: () => apiFetch<Workspace[]>("/workspaces"),
  create: (name: string) => apiFetch<Workspace>("/workspaces", { method: "POST", body: JSON.stringify({ name }) }),
  get: (id: number) => apiFetch<Workspace>(`/workspaces/${id}`),
  rename: (id: number, name: string) => apiFetch<Workspace>(`/workspaces/${id}`, { method: "PUT", body: JSON.stringify({ name }) }),
  delete: (id: number) => apiFetch<void>(`/workspaces/${id}`, { method: "DELETE" }),
  members: (id: number) => apiFetch<WorkspaceMember[]>(`/workspaces/${id}/members`),
  invite: (id: number, email: string, role: string) =>
    apiFetch<WorkspaceInvite>(`/workspaces/${id}/invites`, { method: "POST", body: JSON.stringify({ email, role }) }),
  listInvites: (id: number) => apiFetch<WorkspaceInvite[]>(`/workspaces/${id}/invites`),
  cancelInvite: (workspaceId: number, inviteId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/invites/${inviteId}`, { method: "DELETE" }),
  acceptInvite: (token: string) => apiFetch<{ detail: string }>("/workspaces/invites/accept", { method: "POST", body: JSON.stringify({ token }) }),
  removeMember: (workspaceId: number, memberId: number) =>
    apiFetch<void>(`/workspaces/${workspaceId}/members/${memberId}`, { method: "DELETE" }),
  updateMemberRole: (workspaceId: number, memberId: number, role: string) =>
    apiFetch<WorkspaceMember>(`/workspaces/${workspaceId}/members/${memberId}/role`, { method: "PUT", body: JSON.stringify({ role }) }),
}

export interface AdminStats { total_users: number; total_workspaces: number; total_urls: number }
export interface AdminListResponse<T> { total: number; items: T[] }
export const adminApi = {
  stats: () => apiFetch<AdminStats>("/admin/stats"),
  listUsers: (skip = 0, limit = 50) => apiFetch<{ total: number; users: User[] }>(`/admin/users?skip=${skip}&limit=${limit}`),
  getUser: (id: number) => apiFetch<User>(`/admin/users/${id}`),
  toggleSuperadmin: (id: number) => apiFetch<{ detail: string }>(`/admin/users/${id}/toggle-superadmin`, { method: "PATCH" }),
  deleteUser: (id: number) => apiFetch<{ detail: string }>(`/admin/users/${id}`, { method: "DELETE" }),
  listWorkspaces: (skip = 0, limit = 50) => apiFetch<AdminListResponse<Workspace>>(`/admin/workspaces?skip=${skip}&limit=${limit}`),
  listUrls: (skip = 0, limit = 50) => apiFetch<{ total: number; urls: URLItem[] }>(`/admin/urls?skip=${skip}&limit=${limit}`),
}

export const foldersApi = {
  list: (workspace_id: number) => apiFetch<Folder[]>(`/folders?workspace_id=${workspace_id}`),
  create: (name: string, workspace_id: number) =>
    apiFetch<Folder>("/folders", { method: "POST", body: JSON.stringify({ name, workspace_id }) }),
  update: (id: number, name: string) =>
    apiFetch<Folder>(`/folders/${id}`, { method: "PUT", body: JSON.stringify({ name }) }),
  delete: (id: number) => apiFetch<void>(`/folders/${id}`, { method: "DELETE" }),
}

export const tagsApi = {
  list: (workspace_id: number) => apiFetch<Tag[]>(`/tags?workspace_id=${workspace_id}`),
  create: (name: string, workspace_id: number) =>
    apiFetch<Tag>("/tags", { method: "POST", body: JSON.stringify({ name, workspace_id }) }),
  delete: (id: number) => apiFetch<void>(`/tags/${id}`, { method: "DELETE" }),
}

export const apiKeysApi = {
  list: () => apiFetch<ApiKey[]>("/api-keys"),
  create: (name: string, expires_at?: string) =>
    apiFetch<ApiKeyCreateResponse>("/api-keys", { method: "POST", body: JSON.stringify({ name, expires_at }) }),
  revoke: (id: number) => apiFetch<void>(`/api-keys/${id}`, { method: "DELETE" }),
  rotate: (id: number) => apiFetch<ApiKeyCreateResponse>(`/api-keys/${id}/rotate`, { method: "POST" }),
  quota: (id: number) => apiFetch<{ used: number; limit: number }>(`/api-keys/${id}/quota`),
}

function generateWebhookSecret(): string {
  const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
  let result = "whsec_"
  for (let i = 0; i < 32; i++) result += chars.charAt(Math.floor(Math.random() * chars.length))
  return result
}

export const webhooksApi = {
  list: (workspace_id: number) => apiFetch<Webhook[]>(`/webhooks/workspace/${workspace_id}`),
  create: (workspace_id: number, data: { url: string; event_types: string[] }) =>
    apiFetch<Webhook>(`/webhooks/workspace/${workspace_id}`, { method: "POST", body: JSON.stringify({ url: data.url, events: data.event_types, secret: generateWebhookSecret() }) }),
  delete: (webhook_id: number, workspace_id: number) =>
    apiFetch<void>(`/webhooks/${webhook_id}/workspace/${workspace_id}`, { method: "DELETE" }),
}

export const bulkApi = {
  create: (workspace_id: number, urls: {
    original_url: string; custom_alias?: string; folder_id?: string; tags?: string;
    expires_at?: string; password?: string; domain?: string; is_ab_test?: boolean;
    is_one_time?: boolean; ios_url?: string; android_url?: string
  }[]) => {
    const csvHeader = "original_url,custom_alias,folder_id,tags,expires_at,password,domain,is_ab_test,is_one_time,ios_url,android_url"
    const csvRows = urls.map((u) =>
      [u.original_url, u.custom_alias || "", u.folder_id || "", u.tags || "", u.expires_at || "",
       u.password || "", u.domain || "", u.is_ab_test ? "true" : "false", u.is_one_time ? "true" : "false",
       u.ios_url || "", u.android_url || ""].join(",")
    ).join("\n")
    const blob = new Blob([csvHeader + "\n" + csvRows], { type: "text/csv" })
    const form = new FormData()
    form.append("file", blob, "urls.csv")
    return apiFetch<{ created: number }>(`/urls/bulk/create?workspace_id=${workspace_id}`, { method: "POST", body: form, headers: {} })
  },
  update: (workspace_id: number, ids: number[], data: { original_url?: string; folder_id?: number | null; status?: string }) =>
    apiFetch<{ updated: number }>(`/urls/bulk/update?workspace_id=${workspace_id}&url_ids=${ids.join(",")}`, {
      method: "POST", body: JSON.stringify({ expires_at: data.status === "active" ? undefined : null }),
    }),
  disable: (workspace_id: number, ids: number[]) =>
    apiFetch<{ updated: number }>(`/urls/bulk/disable?workspace_id=${workspace_id}&url_ids=${ids.join(",")}`, { method: "POST" }),
  reactivate: (workspace_id: number, ids: number[]) =>
    apiFetch<{ updated: number }>(`/urls/bulk/reactivate?workspace_id=${workspace_id}&url_ids=${ids.join(",")}`, { method: "POST" }),
  delete: (workspace_id: number, ids: number[]) =>
    apiFetch<{ deleted: number }>(`/urls/bulk/delete?workspace_id=${workspace_id}&url_ids=${ids.join(",")}`, { method: "POST" }),
  export: (workspace_id: number) =>
    apiFetchBlob(`/urls/bulk/export?workspace_id=${workspace_id}`).then((blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url; a.download = "urls.csv"; a.click()
      URL.revokeObjectURL(url)
      return { csv: "" }
    }),
  qr: (workspace_id: number, ids: number[]) =>
    apiFetchBlob(`/urls/bulk/qr?workspace_id=${workspace_id}&url_ids=${ids.join(",")}`).then((blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url; a.download = "qrcodes.zip"; a.click()
      URL.revokeObjectURL(url)
      return { qr_codes: [] }
    }),
}

export const favoritesApi = {
  list: (skip?: number, limit?: number) => {
    const q = new URLSearchParams()
    if (skip) q.set("skip", String(skip))
    if (limit) q.set("limit", String(limit))
    return apiFetch<Favorite[]>(`/favorites${q.toString() ? `?${q}` : ""}`)
  },
  add: (url_id: number) => apiFetch<Favorite>("/favorites", { method: "POST", body: JSON.stringify({ url_id }) }),
  check: (url_id: number) => apiFetch<FavoriteCheck>(`/favorites/check/${url_id}`),
  remove: (url_id: number) => apiFetch<void>(`/favorites/${url_id}`, { method: "DELETE" }),
}

export const profileApi = {
  changePassword: (current_password: string, new_password: string) =>
    apiFetch<{ detail: string }>("/profile/password", { method: "PUT", body: JSON.stringify({ current_password, new_password }) }),
  changeEmail: (new_email: string, current_password: string) =>
    apiFetch<{ detail: string }>("/profile/email", { method: "PUT", body: JSON.stringify({ new_email, current_password }) }),
  uploadAvatar: (avatar: string) =>
    apiFetch<{ detail: string; avatar_url: string }>("/profile/avatar", { method: "POST", body: JSON.stringify({ avatar }) }),
}

export const billingApi = {
  upgrade: (plan: string) =>
    apiFetch<{ detail: string; plan: string }>("/billing/upgrade", { method: "POST", body: JSON.stringify({ plan }) }),
}

export const webhookReceiverApi = {
  list: (workspace_id: number, skip?: number, limit?: number) => {
    const q = new URLSearchParams()
    if (skip) q.set("skip", String(skip))
    if (limit) q.set("limit", String(limit))
    return apiFetch<ReceivedWebhookEvent[]>(`/webhook-receiver/events/${workspace_id}${q.toString() ? `?${q}` : ""}`)
  },
}

export const auditApi = {
  list: (workspace_id: number, skip?: number, limit?: number) => {
    const q = new URLSearchParams()
    if (skip) q.set("skip", String(skip))
    if (limit) q.set("limit", String(limit))
    return apiFetch<AuditLog[]>(`/audit-logs/workspace/${workspace_id}${q.toString() ? `?${q}` : ""}`)
  },
  resource: (resource_type: string, resource_id: number, skip?: number, limit?: number) => {
    const q = new URLSearchParams()
    if (skip) q.set("skip", String(skip))
    if (limit) q.set("limit", String(limit))
    return apiFetch<AuditLog[]>(`/audit-logs/resource/${resource_type}/${resource_id}${q.toString() ? `?${q}` : ""}`)
  },
  actor: (actor_id: number, skip?: number, limit?: number) => {
    const q = new URLSearchParams()
    if (skip) q.set("skip", String(skip))
    if (limit) q.set("limit", String(limit))
    return apiFetch<AuditLog[]>(`/audit-logs/actor/${actor_id}${q.toString() ? `?${q}` : ""}`)
  },
}
