import { test, expect, DashboardPage, setupCommonMocks, setupAuthMocks, setAuthState, TEST_URL } from "./fixtures"
import { mockApi } from "./fixtures"

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    const authMocks = setupAuthMocks(page)
    await authMocks.setup()
    await setAuthState(page)
  })

  test("Viewing dashboard shows stats cards", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [TEST_URL], total: 1 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
    await expect(page.getByText("Total URLs")).toBeVisible()
    await expect(page.getByText("Active")).toBeVisible()
    await expect(page.getByText("Plan")).toBeVisible()
  })

  test("Dashboard shows workspace selector", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("All workspaces")).toBeVisible()
  })

  test("Dashboard shows Create URL button", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    const createUrlButton = page.getByRole("link", { name: /Create URL/ })
    await expect(createUrlButton).toBeVisible()
  })

  test("Dashboard shows recent URLs section", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [TEST_URL], total: 1 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("Recent URLs")).toBeVisible()
    await expect(page.getByText("abc123")).toBeVisible()
  })

  test("Dashboard shows View all link", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [TEST_URL], total: 1 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    const viewAllLink = page.getByRole("link", { name: "View all" })
    await expect(viewAllLink).toBeVisible()
    await expect(viewAllLink).toHaveAttribute("href", "/urls")
  })

  test("Dashboard shows empty state when no URLs", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("No URLs yet")).toBeVisible()
  })

  test("Dashboard shows stat values", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    const urlsWithStatus = { ...TEST_URL, status: "active" }
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [urlsWithStatus, urlsWithStatus], total: 2 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("2").first()).toBeVisible()
  })

  test("Dashboard sets document title", async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const commonMocks = setupCommonMocks(page)
    await commonMocks.setup()

    const mocks = mockApi(page)
    mocks.route(/\/urls\?/, (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      })
    })
    await mocks.setup()

    await dashboardPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page).toHaveTitle("Dashboard - LinkForge")
  })
})
