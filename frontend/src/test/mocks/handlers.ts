import { http, HttpResponse } from "msw"

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

export const mockUser = {
  id: 1,
  email: "test@test.com",
  is_verified: true,
  role: "admin",
  plan: "free",
  is_superadmin: false,
  avatar_url: null,
  created_at: "2024-01-01T00:00:00Z",
}

export const mockWorkspace = { id: 1, name: "Test Workspace", owner_id: 1, created_at: "2024-01-01T00:00:00Z" }

export const mockUrl = {
  id: 1,
  short_code: "abc123",
  original_url: "https://example.com",
  workspace_id: 1,
  folder_id: null,
  custom_alias: null,
  domain: null,
  is_ab_test: false,
  is_one_time: false,
  ios_url: null,
  android_url: null,
  expires_at: null,
  status: "active",
  qr_code: null,
  created_at: "2024-01-01T00:00:00Z",
  tags: [],
}

export const handlers = [
  http.get(`${API}/auth/me`, () => HttpResponse.json(mockUser)),

  http.post(`${API}/auth/login`, () =>
    HttpResponse.json({ access_token: "mock-token", token_type: "bearer" })
  ),

  http.post(`${API}/auth/register`, () =>
    HttpResponse.json(mockUser)
  ),

  http.post(`${API}/auth/refresh`, () =>
    HttpResponse.json({ access_token: "mock-refreshed-token", token_type: "bearer" })
  ),

  http.post(`${API}/auth/logout`, () =>
    HttpResponse.json({ detail: "Logged out" })
  ),

  http.post(`${API}/auth/forgot-password`, () =>
    HttpResponse.json({ detail: "Check your email" })
  ),

  http.post(`${API}/auth/reset-password`, () =>
    HttpResponse.json({ detail: "Password reset" })
  ),

  http.post(`${API}/auth/verify-email`, () =>
    HttpResponse.json({ detail: "Email verified" })
  ),

  http.get(`${API}/auth/providers`, () =>
    HttpResponse.json({ providers: ["google", "github"] })
  ),

  http.post(`${API}/auth/oauth/:provider`, () =>
    HttpResponse.json({ authorization_url: "https://provider.com/auth" })
  ),

  http.get(`${API}/workspaces`, () =>
    HttpResponse.json([mockWorkspace])
  ),

  http.post(`${API}/workspaces`, () =>
    HttpResponse.json({ id: 2, name: "New Workspace", owner_id: 1, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.get(`${API}/workspaces/:id`, () =>
    HttpResponse.json(mockWorkspace)
  ),

  http.put(`${API}/workspaces/:id`, () =>
    HttpResponse.json({ ...mockWorkspace, name: "Updated Workspace" })
  ),

  http.delete(`${API}/workspaces/:id`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/workspaces/:id/members`, () =>
    HttpResponse.json([{ id: 1, workspace_id: 1, user_id: 1, email: "test@test.com", role: "admin", joined_at: "2024-01-01T00:00:00Z" }])
  ),

  http.post(`${API}/workspaces/:id/invites`, () =>
    HttpResponse.json({ id: 1, workspace_id: 1, email: "invited@test.com", invited_by: 1, role: "member", status: "pending", expires_at: "2024-12-31T00:00:00Z", created_at: "2024-01-01T00:00:00Z" })
  ),

  http.get(`${API}/workspaces/:id/invites`, () =>
    HttpResponse.json([])
  ),

  http.delete(`${API}/workspaces/:workspaceId/invites/:inviteId`, () => new HttpResponse(null, { status: 204 })),

  http.post(`${API}/workspaces/invites/accept`, () =>
    HttpResponse.json({ detail: "Invite accepted" })
  ),

  http.delete(`${API}/workspaces/:workspaceId/members/:memberId`, () => new HttpResponse(null, { status: 204 })),

  http.put(`${API}/workspaces/:workspaceId/members/:memberId/role`, () =>
    HttpResponse.json({ id: 1, workspace_id: 1, user_id: 1, email: "test@test.com", role: "admin", joined_at: "2024-01-01T00:00:00Z" })
  ),

  http.get(`${API}/urls`, () =>
    HttpResponse.json({ items: [mockUrl], total: 1 })
  ),

  http.post(`${API}/urls`, () =>
    HttpResponse.json(mockUrl)
  ),

  http.get(`${API}/urls/:id`, () =>
    HttpResponse.json(mockUrl)
  ),

  http.put(`${API}/urls/:id`, () =>
    HttpResponse.json({ ...mockUrl, original_url: "https://updated.com" })
  ),

  http.delete(`${API}/urls/:id`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/urls/:id/qr`, () =>
    HttpResponse.json({ qr_code: "data:image/png;base64,mock" })
  ),

  http.get(`${API}/favorites`, () =>
    HttpResponse.json([])
  ),

  http.post(`${API}/favorites`, () =>
    HttpResponse.json({ id: 1, url_id: 1, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.get(`${API}/favorites/check/:urlId`, () =>
    HttpResponse.json({ favorited: false })
  ),

  http.delete(`${API}/favorites/:urlId`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/folders`, () =>
    HttpResponse.json([])
  ),

  http.post(`${API}/folders`, () =>
    HttpResponse.json({ id: 1, name: "New Folder", workspace_id: 1, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.put(`${API}/folders/:id`, () =>
    HttpResponse.json({ id: 1, name: "Updated Folder", workspace_id: 1, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.delete(`${API}/folders/:id`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/tags`, () =>
    HttpResponse.json([])
  ),

  http.post(`${API}/tags`, () =>
    HttpResponse.json({ id: 1, name: "New Tag", workspace_id: 1, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.delete(`${API}/tags/:id`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/api-keys`, () =>
    HttpResponse.json([])
  ),

  http.post(`${API}/api-keys`, () =>
    HttpResponse.json({ id: 1, name: "New Key", prefix: "lf_", key: "lf_abc123", status: "active", expires_at: null, last_used_at: null, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.delete(`${API}/api-keys/:id`, () => new HttpResponse(null, { status: 204 })),

  http.post(`${API}/api-keys/:id/rotate`, () =>
    HttpResponse.json({ id: 1, name: "Rotated Key", prefix: "lf_", key: "lf_def456", status: "active", expires_at: null, last_used_at: null, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.get(`${API}/api-keys/:id/quota`, () =>
    HttpResponse.json({ used: 10, limit: 100 })
  ),

  http.get(`${API}/api-keys/quota-summary`, () =>
    HttpResponse.json({ used: 10, limit: 100, remaining: 90, resets_at: "2024-01-02T00:00:00Z" })
  ),

  http.get(`${API}/webhooks/workspace/:workspaceId`, () =>
    HttpResponse.json([])
  ),

  http.post(`${API}/webhooks/workspace/:workspaceId`, () =>
    HttpResponse.json({ id: 1, url: "https://hook.example.com", events: ["click"], is_active: true, created_at: "2024-01-01T00:00:00Z" })
  ),

  http.delete(`${API}/webhooks/:webhookId/workspace/:workspaceId`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/webhook-receiver/events/:workspaceId`, () =>
    HttpResponse.json([])
  ),

  http.get(`${API}/analytics/:shortCode/summary`, () =>
    HttpResponse.json({ short_code: "abc123", total_clicks: 100, unique_clicks: 50, last_clicked_at: "2024-06-01T00:00:00Z" })
  ),

  http.get(`${API}/analytics/:shortCode/timeseries`, () =>
    HttpResponse.json({ short_code: "abc123", days: 7, data: [{ date: "2024-06-01", clicks: 10 }] })
  ),

  http.get(`${API}/analytics/:shortCode/devices`, () =>
    HttpResponse.json({ short_code: "abc123", browsers: [{ name: "Chrome", count: 60 }], os: [{ name: "Windows", count: 40 }], devices: [{ name: "Desktop", count: 70 }], geo: [{ country: "US", city: "New York", count: 50 }] })
  ),

  http.get(`${API}/analytics/:shortCode/utm`, () =>
    HttpResponse.json({ short_code: "abc123", data: [] })
  ),

  http.get(`${API}/analytics/:shortCode/referrers`, () =>
    HttpResponse.json({ short_code: "abc123", data: [] })
  ),

  http.get(`${API}/admin/stats`, () =>
    HttpResponse.json({ total_users: 10, total_workspaces: 5, total_urls: 100 })
  ),

  http.get(`${API}/admin/users`, () =>
    HttpResponse.json({ total: 1, users: [mockUser] })
  ),

  http.get(`${API}/admin/users/:id`, () =>
    HttpResponse.json(mockUser)
  ),

  http.patch(`${API}/admin/users/:id/toggle-superadmin`, () =>
    HttpResponse.json({ detail: "Toggled" })
  ),

  http.delete(`${API}/admin/users/:id`, () =>
    HttpResponse.json({ detail: "Deleted" })
  ),

  http.get(`${API}/admin/workspaces`, () =>
    HttpResponse.json({ total: 1, items: [mockWorkspace] })
  ),

  http.get(`${API}/admin/urls`, () =>
    HttpResponse.json({ total: 1, urls: [mockUrl] })
  ),

  http.put(`${API}/profile/password`, () =>
    HttpResponse.json({ detail: "Password changed" })
  ),

  http.put(`${API}/profile/email`, () =>
    HttpResponse.json({ detail: "Email changed" })
  ),

  http.post(`${API}/profile/avatar`, () =>
    HttpResponse.json({ detail: "Avatar uploaded", avatar_url: "https://cdn.example.com/avatar.png" })
  ),

  http.post(`${API}/billing/upgrade`, () =>
    HttpResponse.json({ detail: "Upgraded", plan: "pro" })
  ),

  http.get(`${API}/audit-logs/workspace/:workspaceId`, () =>
    HttpResponse.json([])
  ),

  http.get(`${API}/audit-logs/resource/:resourceType/:resourceId`, () =>
    HttpResponse.json([])
  ),

  http.get(`${API}/audit-logs/actor/:actorId`, () =>
    HttpResponse.json([])
  ),

  http.post(`${API}/urls/bulk/create`, () =>
    HttpResponse.json({ created: 3 })
  ),

  http.post(`${API}/urls/bulk/update`, () =>
    HttpResponse.json({ updated: 2 })
  ),

  http.post(`${API}/urls/bulk/disable`, () =>
    HttpResponse.json({ updated: 2 })
  ),

  http.post(`${API}/urls/bulk/reactivate`, () =>
    HttpResponse.json({ updated: 2 })
  ),

  http.post(`${API}/urls/bulk/delete`, () =>
    HttpResponse.json({ deleted: 2 })
  ),

  http.get(`${API}/urls/bulk/export`, () =>
    new HttpResponse("short_code,original_url\nabc123,https://example.com", {
      headers: { "Content-Type": "text/csv" },
    })
  ),

  http.get(`${API}/urls/bulk/qr`, () =>
    new HttpResponse("mock-zip-content", {
      headers: { "Content-Type": "application/zip" },
    })
  ),
]
