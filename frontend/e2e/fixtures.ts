import { test as base, type Page, type Route } from "@playwright/test"

export const TEST_USER = {
  id: 1,
  email: "test@example.com",
  password: "password123",
  is_verified: true,
  role: "admin",
  plan: "free",
  is_superadmin: false,
  avatar_url: null,
  created_at: "2025-01-01T00:00:00Z",
}

export const TEST_WORKSPACE = {
  id: 1,
  name: "My Workspace",
  owner_id: 1,
  created_at: "2025-01-01T00:00:00Z",
}

export const TEST_URL = {
  id: 1,
  short_code: "abc123",
  original_url: "https://example.com/very/long/url",
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
  created_at: "2025-01-02T00:00:00Z",
  tags: [],
}

export class LoginPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto("/login")
  }

  async fillEmail(email: string) {
    await this.page.getByPlaceholder("Email").fill(email)
  }

  async fillPassword(password: string) {
    await this.page.getByPlaceholder("Password").fill(password)
  }

  async submit() {
    await this.page.getByRole("button", { name: "Sign In" }).click()
  }

  async login(email: string, password: string) {
    await this.fillEmail(email)
    await this.fillPassword(password)
    await this.submit()
  }
}

export class RegisterPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto("/register")
  }

  async fillEmail(email: string) {
    await this.page.getByPlaceholder("Email").fill(email)
  }

  async fillPassword(password: string) {
    await this.page.getByPlaceholder("Password").fill(password)
  }

  async fillConfirmPassword(password: string) {
    await this.page.getByPlaceholder("Confirm Password").fill(password)
  }

  async submit() {
    await this.page.getByRole("button", { name: "Create Account" }).click()
  }

  async register(email: string, password: string) {
    await this.fillEmail(email)
    await this.fillPassword(password)
    await this.fillConfirmPassword(password)
    await this.submit()
  }
}

export class ForgotPasswordPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto("/forgot-password")
  }

  async fillEmail(email: string) {
    await this.page.getByPlaceholder("Your email").fill(email)
  }

  async submit() {
    await this.page.getByRole("button", { name: "Send Reset Link" }).click()
  }
}

export class ResetPasswordPage {
  constructor(public page: Page) {}

  async goto(token: string) {
    await this.page.goto(`/reset-password?token=${token}`)
  }

  async fillPassword(password: string) {
    await this.page.getByPlaceholder("New password").fill(password)
  }

  async submit() {
    await this.page.getByRole("button", { name: "Reset Password" }).click()
  }
}

export class DashboardPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto("/dashboard")
  }
}

export class UrlsPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto("/urls")
  }

  async search(query: string) {
    await this.page.getByPlaceholder("Search URLs...").fill(query)
  }
}

export class CreateUrlPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto("/urls/new")
  }

  async fillOriginalUrl(url: string) {
    await this.page.getByPlaceholder("https://example.com/very/long/url").fill(url)
  }

  async selectWorkspace(name: string) {
    await this.page.getByLabel("Workspace").selectOption({ label: name })
  }

  async submit() {
    await this.page.getByRole("button", { name: "Create URL" }).click()
  }
}

export class UrlDetailPage {
  constructor(public page: Page) {}

  async goto(id: number) {
    await this.page.goto(`/urls/${id}`)
  }
}

export class WorkspacesPage {
  constructor(public page: Page) {}

  async goto() {
    await this.page.goto("/workspaces")
  }

  async fillNewName(name: string) {
    await this.page.getByPlaceholder("Workspace name").fill(name)
  }

  async clickCreate() {
    await this.page.getByRole("button", { name: "Create" }).click()
  }
}

export class AnalyticsPage {
  constructor(public page: Page) {}

  async goto(id: number) {
    await this.page.goto(`/urls/${id}/analytics`)
  }
}

export function mockApi(page: Page) {
  const handlers: { urlPattern: RegExp; handler: (route: Route) => void }[] = []

  function route(pattern: RegExp, handler: (route: Route) => void) {
    handlers.push({ urlPattern: pattern, handler })
  }

  async function setup() {
    await page.route("**/api/v1/**", (route) => {
      const url = route.request().url()
      for (const h of handlers) {
        if (h.urlPattern.test(url)) {
          return h.handler(route)
        }
      }
      route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "unmocked" }) })
    })
  }

  return { route, setup }
}

export function setupAuthMocks(page: Page, user = TEST_USER, accessToken = "test-access-token", refreshToken = "test-refresh-token") {
  const mocks = mockApi(page)

  mocks.route(/\/auth\/login$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: accessToken, refresh_token: refreshToken, token_type: "bearer" }),
    })
  })

  mocks.route(/\/auth\/register$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(user),
    })
  })

  mocks.route(/\/auth\/me$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(user),
    })
  })

  mocks.route(/\/auth\/logout$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Logged out" }),
    })
  })

  mocks.route(/\/auth\/forgot-password$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Reset link sent" }),
    })
  })

  mocks.route(/\/auth\/reset-password$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Password reset successfully" }),
    })
  })

  return mocks
}

export function setupWorkspaceMocks(page: Page, workspaces = [TEST_WORKSPACE]) {
  const mocks = mockApi(page)

  mocks.route(/\/workspaces$/, (route) => {
    if (route.request().method() === "POST") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 2, name: "New Workspace", owner_id: 1, created_at: new Date().toISOString() }),
      })
    } else {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(workspaces),
      })
    }
  })

  mocks.route(/\/workspaces\/\d+\/members$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  })

  mocks.route(/\/workspaces\/\d+\/invites$/, (route) => {
    if (route.request().method() === "POST") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 1, workspace_id: 1, email: "invited@example.com", invited_by: 1, role: "editor", status: "pending", token: "invite-token-123", expires_at: new Date(Date.now() + 86400000).toISOString(), created_at: new Date().toISOString() }),
      })
    } else {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      })
    }
  })

  return mocks
}

export function setupUrlMocks(page: Page, urls = [TEST_URL]) {
  const mocks = mockApi(page)

  mocks.route(/\/urls\?/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: urls, total: urls.length }),
    })
  })

  mocks.route(/\/urls\/\d+$/, (route) => {
    if (route.request().method() === "PUT") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...urls[0], original_url: "https://updated.example.com" }),
      })
    } else if (route.request().method() === "DELETE") {
      route.fulfill({
        status: 204,
      })
    } else {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(urls[0]),
      })
    }
  })

  mocks.route(/\/urls$/, (route) => {
    if (route.request().method() === "POST") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(TEST_URL),
      })
    } else {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: urls, total: urls.length }),
      })
    }
  })

  mocks.route(/\/urls\/\d+\/qr$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ qr_code: "iVBORw0KGgoAAAANSUhEUg..." }),
    })
  })

  return mocks
}

export function setupAnalyticsMocks(page: Page) {
  const mocks = mockApi(page)

  mocks.route(/\/analytics\/.+\/summary/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ short_code: "abc123", total_clicks: 150, unique_clicks: 45, last_clicked_at: "2025-06-01T12:00:00Z" }),
    })
  })

  mocks.route(/\/analytics\/.+\/timeseries/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ short_code: "abc123", days: 7, data: [{ date: "2025-05-25", clicks: 10 }, { date: "2025-05-26", clicks: 20 }, { date: "2025-05-27", clicks: 15 }] }),
    })
  })

  mocks.route(/\/analytics\/.+\/devices/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        short_code: "abc123",
        browsers: [{ name: "Chrome", count: 80 }, { name: "Firefox", count: 40 }, { name: "Safari", count: 30 }],
        os: [{ name: "Windows", count: 60 }, { name: "macOS", count: 50 }, { name: "Linux", count: 40 }],
        devices: [{ name: "Desktop", count: 100 }, { name: "Mobile", count: 50 }],
        geo: [{ country: "US", city: "New York", count: 50 }, { country: "US", city: "San Francisco", count: 30 }],
      }),
    })
  })

  mocks.route(/\/analytics\/.+\/utm/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ short_code: "abc123", data: [{ source: "twitter", medium: "social", campaign: "summer", count: 40 }] }),
    })
  })

  mocks.route(/\/analytics\/.+\/referrers/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ short_code: "abc123", data: [{ referer: "https://twitter.com/post/123", count: 60 }] }),
    })
  })

  return mocks
}

export function setupCommonMocks(page: Page, user = TEST_USER) {
  const mocks = mockApi(page)

  mocks.route(/\/workspaces$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([TEST_WORKSPACE]),
    })
  })

  mocks.route(/\/folders\?/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  })

  mocks.route(/\/tags\?/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  })

  mocks.route(/\/favorites$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  })

  mocks.route(/\/api-keys$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  })

  mocks.route(/\/auth\/me$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(user),
    })
  })

  mocks.route(/\/api-key-quota/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ used: 5, limit: 100 }),
    })
  })

  return mocks
}

export async function setAuthState(page: Page, accessToken = "test-access-token", refreshToken = "test-refresh-token") {
  await page.evaluate(({ accessToken, refreshToken }) => {
    localStorage.setItem("access_token", accessToken)
    localStorage.setItem("refresh_token", refreshToken)
    document.cookie = `access_token=${accessToken}; path=/; max-age=604800`
    document.cookie = `refresh_token=${refreshToken}; path=/; max-age=2592000`
  }, { accessToken, refreshToken })
}

export async function navigateWithAuth(page: Page, url: string) {
  await page.goto(url)
}

export const test = base

export { expect } from "@playwright/test"
