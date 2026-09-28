const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

/** The backend's `limit` ceiling (`deps.py`: `Query(20, ge=1, le=100)`).
 *  Used as the default for list endpoints so a caller that omits `limit` gets
 *  everything a flat, unpaginated table can show — not the server's silent
 *  default of 20. */
const MAX_LIST_LIMIT = 100

let refreshPromise: Promise<boolean> | null = null

// Single-flight: concurrent 401s (e.g. a burst of parallel dashboard queries
// after the access token expires) share ONE refresh call instead of firing N
// refreshes with the same refresh token. Without this, the backend's refresh
// rotation + reuse detection would treat the duplicates as token replay and
// revoke the session family.
function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
        })
        if (!res.ok) return false
        const data = await res.json()
        return !!data.access_token
      } catch { return false }
    })().finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

/** The httpOnly auth cookies CANNOT be cleared from JavaScript.
 *
 * This used to write `document.cookie = "access_token=; max-age=0"` and the same
 * for `refresh_token`. That is a silent no-op: the backend sets both with
 * `httponly=True`, so the browser never exposes them to script and script cannot
 * delete them. The function looked like a safety net and was not one.
 *
 * Real clearing happens server-side, in three places:
 *   - `POST /auth/logout` deletes both cookies;
 *   - `POST /auth/refresh` deletes both when the token is rejected, so a dead
 *     refresh cookie stops being replayed for the rest of its max_age;
 *   - `proxy.ts` deletes the access token when it is expired or unparseable.
 *
 * The redirect below is what actually recovers the UX.
 */
function clearTokens() {
  // Intentionally empty — see above. Kept as the single call site so the
  // explanation lives next to the call rather than being rediscovered.
}

async function handleUnauthorized() {
  const refreshed = await tryRefresh()
  if (refreshed) return true
  clearTokens()
  // ?expired=1 tells the proxy middleware NOT to bounce /login back to
  // /dashboard when a stale-but-unexpired cookie is still present, which would
  // otherwise loop. The httpOnly cookie may not be removable from JS.
  if (typeof window !== "undefined") window.location.href = "/login?expired=1"
  return false
}

/** Endpoints where a 401 is a legitimate ANSWER, not a dead session.
 *
 * Each of these can return 401 for a reason that a token refresh cannot fix,
 * and running recovery on them actively makes things worse:
 *
 *  - `/auth/oauth/exchange`: the one-time handoff code expired or was already
 *    redeemed. Recovery redirected to /login?expired=1, throwing away the code,
 *    the `redirect` deep link, and the page's own "OAuth login failed" message —
 *    which could never render, because the document was already navigating. The
 *    user got a blank sign-in form and no explanation. The code is consumed
 *    server-side, so it cannot be retried either; it has to be reported.
 *  - `/profile/*`: a wrong `current_password`. The backend used to answer 401
 *    here, so the client refreshed, retried with the same wrong password, and
 *    reported "Session expired" instead of naming the bad field. (The backend
 *    now answers 400, so this is belt-and-braces, but the client must not
 *    depend on one endpoint's status code staying a certain value.)
 */
const NON_SESSION_401 = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/oauth/exchange", "/profile/"]

/** Pull the server's own message out of an error response. */
async function errorFromResponse(res: Response, fallback: string): Promise<Error> {
  const body = await res.json().catch(() => null)
  const detail = body?.detail
  const msg = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : ""
  return new Error(msg || fallback)
}

async function rawFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string>),
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" })
  if (res.status === 401 && !NON_SESSION_401.some((p) => path.startsWith(p))) {
    const recovered = await handleUnauthorized()
    if (recovered) {
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" })
      if (retry.ok) return retry.status === 204 ? (undefined as T) : retry.json()
      // The retry failed for some other reason (403/404/409/422/500). Throwing
      // the fixed "Session expired" string here threw away the server's actual
      // explanation, so a genuine failure was reported as a login problem.
      if (retry.status !== 401) throw await errorFromResponse(retry, "Request failed")
    }
    throw new Error("Session expired. Please login again.")
  }
  if (!res.ok) throw await errorFromResponse(res, res.statusText || "Request failed")
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
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" })
  if (res.status === 401 && !NON_SESSION_401.some((p) => path.startsWith(p))) {
    const recovered = await handleUnauthorized()
    if (recovered) {
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" })
      if (retry.ok) return retry.blob()
      if (retry.status !== 401) throw await errorFromResponse(retry, "Download failed")
    }
    throw new Error("Session expired. Please login again.")
  }
  if (!res.ok) throw await errorFromResponse(res, res.statusText || "Download failed")
  return res.blob()
}
export interface User {
  id: number; email: string; is_verified: boolean; is_active: boolean; plan: string; is_superadmin: boolean; avatar_url: string | null; created_at: string
}
export interface Token { access_token: string; refresh_token?: string; token_type: string }
/** Bulk create reports per-row failures alongside the success count.
 *  `errors` is one entry per rejected row (bad URL, duplicate alias, folder not
 *  in the workspace, ...) — omitting it reported a partial import as a clean
 *  success. See `bulk_service.create`. */
export interface BulkCreateResult {
  created: number
  errors?: string[]
  short_codes?: string[]
}
/** The OAuth handoff exchange mints the session *and* returns the user, so the
 *  client never has to spend a second round trip on /auth/me. */
export interface TokenWithUser extends Token { user: User }
export interface URLItem {
  id: number; short_code: string; original_url: string; workspace_id: number
  folder_id: number | null; custom_alias: string | null; domain: string | null
  is_ab_test: boolean; is_one_time: boolean; ios_url: string | null; android_url: string | null
  expires_at: string | null; status: string; qr_code: string | null; created_at: string
  tags?: string[]
  title: string | null; description: string | null; og_image: string | null
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
export interface AnalyticsSummary { short_code: string; days: number; total_clicks: number; unique_clicks: number; last_clicked_at: string | null }
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
  logout: async () => {
    // Deliberately NOT apiFetch: a 401 here must not trigger the session-expired
    // redirect machinery (which would fight the proxy's /login -> /dashboard
    // bounce and loop). The backend clears the cookies regardless of token
    // validity, so this succeeds for any session state.
    const res = await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" })
    if (!res.ok) throw new Error("Logout failed")
    return res.json() as Promise<{ detail: string }>
  },
  forgotPassword: (email: string) => apiFetch<{ detail: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, new_password: string) => apiFetch<{ detail: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) }),
  verifyEmail: (token: string) => apiFetch<{ detail: string }>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),
  resendVerification: () => apiFetch<{ detail: string }>("/auth/resend-verification", { method: "POST" }),
  resendVerificationForEmail: (email: string) =>
    apiFetch<{ detail: string }>("/auth/verify-email/resend", { method: "POST", body: JSON.stringify({ email }) }),
  providers: () => apiFetch<{ providers: string[] }>("/auth/providers"),
  exchangeOauth: (code: string) =>
    apiFetch<TokenWithUser>("/auth/oauth/exchange", { method: "POST", body: JSON.stringify({ code }) }),
  oauth: async (provider: string) => {
    const res = await fetch(`${API_BASE}/auth/oauth/${provider}`, { method: "POST", credentials: "include" })
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
  list: (workspace_id: number | null, params?: { folder_id?: number; tag?: string; search?: string; status?: string; ids?: string; skip?: number; limit?: number }) => {
    const q = new URLSearchParams()
    if (workspace_id) q.set("workspace_id", String(workspace_id))
    if (params?.folder_id) q.set("folder_id", String(params.folder_id))
    if (params?.tag) q.set("tag", params.tag)
    if (params?.search) q.set("search", params.search)
    if (params?.status) q.set("status", params.status)
    if (params?.ids) q.set("ids", params.ids)
    if (params?.skip) q.set("skip", String(params.skip))
    // Default to the server's maximum rather than letting it apply its own.
    //
    // The API's default `limit` is 20, and `if (params?.limit)` meant an
    // omitted limit sent nothing at all — so the server's 20 applied silently.
    // Every list view in the app renders one flat table with no pagination, so
    // a page asking for "this workspace's URLs" was getting the newest 20 and
    // presenting them as the whole set: the bulk Manage tab could not select
    // older links at all, and the favorites page resolved only the first 20 of
    // its fetched favorites and dropped the rest.
    q.set("limit", String(params?.limit ?? MAX_LIST_LIMIT))
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
  devices: (short_code: string, days?: number) => {
    const q = days ? `?days=${days}` : ""
    return apiFetch<AnalyticsDevices>(`/analytics/${short_code}/devices${q}`)
  },
  utm: (short_code: string, days?: number) => {
    const q = days ? `?days=${days}` : ""
    return apiFetch<{ short_code: string; data: UTMItem[] }>(`/analytics/${short_code}/utm${q}`)
  },
  referrers: (short_code: string, days?: number) => {
    const q = days ? `?days=${days}` : ""
    return apiFetch<{ short_code: string; data: RefererItem[] }>(`/analytics/${short_code}/referrers${q}`)
  },
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
  seed: () => apiFetch<{ detail: string }>("/admin/seed", { method: "POST" }),
  stats: () => apiFetch<AdminStats>("/admin/stats"),
  listUsers: (skip = 0, limit = 50) => apiFetch<{ total: number; users: User[] }>(`/admin/users?skip=${skip}&limit=${limit}`),
  getUser: (id: number) => apiFetch<User>(`/admin/users/${id}`),
  toggleSuperadmin: (id: number) => apiFetch<{ detail: string }>(`/admin/users/${id}/toggle-superadmin`, { method: "PATCH" }),
  deleteUser: (id: number) => apiFetch<{ detail: string }>(`/admin/users/${id}`, { method: "DELETE" }),
  listWorkspaces: (skip = 0, limit = 50) => apiFetch<{ total: number; workspaces: Workspace[] }>(`/admin/workspaces?skip=${skip}&limit=${limit}`),
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
  quota: (id: number) => apiFetch<{ api_key_id: number; remaining_quota: number; daily_limit: number; resets_at: string }>(`/api-keys/${id}/quota`),
  quotaSummary: () => apiFetch<{ used: number; limit: number; remaining: number; resets_at: string }>("/api-keys/quota-summary"),
}

function generateWebhookSecret(): string {
  const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
  let result = "whsec_"
  const randomBytes = new Uint8Array(32)
  crypto.getRandomValues(randomBytes)
  for (let i = 0; i < 32; i++) result += chars.charAt(randomBytes[i] % chars.length)
  return result
}

export const webhooksApi = {
  list: (workspace_id: number) => apiFetch<Webhook[]>(`/webhooks/workspace/${workspace_id}`),
  create: (workspace_id: number, data: { url: string; event_types: string[] }) =>
    apiFetch<Webhook>(`/webhooks/workspace/${workspace_id}`, { method: "POST", body: JSON.stringify({ url: data.url, events: data.event_types, secret: generateWebhookSecret() }) }),
  delete: (webhook_id: number, workspace_id: number) =>
    apiFetch<void>(`/webhooks/${webhook_id}/workspace/${workspace_id}`, { method: "DELETE" }),
}

function csvEscape(value: string): string {
  const needsQuoting = /[",\n\r]/.test(value)
  return needsQuoting ? `"${value.replace(/"/g, '""')}"` : value
}

export const bulkApi = {
  create: (workspace_id: number, urls: {
    original_url: string; custom_alias?: string; folder_id?: string; tags?: string;
    expires_at?: string; password?: string; domain?: string; is_ab_test?: boolean;
    is_one_time?: boolean; ios_url?: string; android_url?: string
  }[]) => {
    const csvHeader = "original_url,custom_alias,folder_id,tags,expires_at,password,domain,is_ab_test,is_one_time,ios_url,android_url"
    const csvRows = urls.map((u) =>
      [
        csvEscape(u.original_url), csvEscape(u.custom_alias || ""), csvEscape(u.folder_id || ""),
        csvEscape(u.tags || ""), csvEscape(u.expires_at || ""), csvEscape(u.password || ""),
        csvEscape(u.domain || ""), u.is_ab_test ? "true" : "false", u.is_one_time ? "true" : "false",
        csvEscape(u.ios_url || ""), csvEscape(u.android_url || ""),
      ].join(",")
    ).join("\n")
    const blob = new Blob([csvHeader + "\n" + csvRows], { type: "text/csv" })
    const form = new FormData()
    form.append("file", blob, "urls.csv")
    return apiFetch<BulkCreateResult>(`/urls/bulk/create?workspace_id=${workspace_id}`, { method: "POST", body: form, headers: {} })
  },
  disable: (workspace_id: number, ids: number[]) =>
    apiFetch<{ disabled: number }>(`/urls/bulk/disable?workspace_id=${workspace_id}&url_ids=${ids.join(",")}`, { method: "POST" }),
  reactivate: (workspace_id: number, ids: number[]) =>
    apiFetch<{ reactivated: number }>(`/urls/bulk/reactivate?workspace_id=${workspace_id}&url_ids=${ids.join(",")}`, { method: "POST" }),
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
    // The receiver view labels this "N events received", which reads as a
    // total. At the server's default of 50 a receiver that had taken 500
    // deliveries reported 50 with no truncation indicated.
    q.set("limit", String(limit ?? MAX_LIST_LIMIT))
    return apiFetch<ReceivedWebhookEvent[]>(`/webhook-receiver/events/${workspace_id}${q.toString() ? `?${q}` : ""}`)
  },
}

export const auditApi = {
  list: (workspace_id: number, skip?: number, limit?: number) => {
    const q = new URLSearchParams()
    if (skip) q.set("skip", String(skip))
    // Default to the ceiling rather than the server's 20: the audit log view is
    // a flat table with no paging control, so it rendered a plausible 20 rows
    // and gave no hint that older entries existed.
    q.set("limit", String(limit ?? MAX_LIST_LIMIT))
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