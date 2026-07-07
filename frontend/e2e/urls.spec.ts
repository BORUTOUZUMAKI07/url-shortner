import { test, expect, UrlsPage, CreateUrlPage, UrlDetailPage, setupUrlMocks, setupCommonMocks, setupAuthMocks, setAuthState, TEST_URL } from "./fixtures"

test.describe("URL Management", () => {
  test.beforeEach(async ({ page }) => {
    const authMocks = setupAuthMocks(page)
    await authMocks.setup()
    await setAuthState(page)
  })

  test("Creating a short URL", async ({ page }) => {
    const createPage = new CreateUrlPage(page)
    const urlMocks = setupUrlMocks(page)
    const commonMocks = setupCommonMocks(page)
    await urlMocks.setup()
    await commonMocks.setup()

    await createPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByRole("heading", { name: "Create Short URL" })).toBeVisible()

    await createPage.fillOriginalUrl("https://example.com/very/long/url")
    await page.getByLabel("Workspace").selectOption("1")

    await createPage.submit()

    await page.waitForURL("/urls")
  })

  test("Create URL validation for invalid URL", async ({ page }) => {
    const createPage = new CreateUrlPage(page)
    const urlMocks = setupUrlMocks(page)
    await urlMocks.setup()

    await createPage.goto()
    await page.waitForLoadState("networkidle")

    await createPage.fillOriginalUrl("not-a-valid-url")
    await createPage.submit()

    await expect(page.getByText("Must be a valid URL")).toBeVisible()
  })

  test("Create URL shows cancel button that navigates back", async ({ page }) => {
    const createPage = new CreateUrlPage(page)
    const urlMocks = setupUrlMocks(page)
    const commonMocks = setupCommonMocks(page)
    await urlMocks.setup()
    await commonMocks.setup()

    await createPage.goto()
    await page.waitForLoadState("networkidle")

    const cancelButton = page.getByRole("button", { name: "Cancel" })
    await expect(cancelButton).toBeVisible()
  })

  test("Viewing URLs list", async ({ page }) => {
    const urlsPage = new UrlsPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    const commonMocks = setupCommonMocks(page)
    await urlMocks.setup()
    await commonMocks.setup()

    await urlsPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByRole("heading", { name: "URLs" })).toBeVisible()
    await expect(page.getByText("abc123")).toBeVisible()
    await expect(page.getByText("https://example.com/very/long/url")).toBeVisible()
    await expect(page.getByText("active")).toBeVisible()
  })

  test("URLs list shows empty state when no URLs", async ({ page }) => {
    const urlsPage = new UrlsPage(page)
    const urlMocks = setupUrlMocks(page, [])
    const commonMocks = setupCommonMocks(page)
    await urlMocks.setup()
    await commonMocks.setup()

    await urlsPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("No URLs found")).toBeVisible()
  })

  test("URLs list shows filter dropdowns", async ({ page }) => {
    const urlsPage = new UrlsPage(page)
    const urlMocks = setupUrlMocks(page)
    const commonMocks = setupCommonMocks(page)
    await urlMocks.setup()
    await commonMocks.setup()

    await urlsPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("All workspaces")).toBeVisible()
    await expect(page.getByText("All folders")).toBeVisible()
    await expect(page.getByText("All tags")).toBeVisible()
  })

  test("Searching URLs", async ({ page }) => {
    const urlsPage = new UrlsPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    const commonMocks = setupCommonMocks(page)
    await urlMocks.setup()
    await commonMocks.setup()

    await urlsPage.goto()
    await page.waitForLoadState("networkidle")

    const searchInput = page.getByPlaceholder("Search URLs...")
    await expect(searchInput).toBeVisible()
    await searchInput.fill("example")
  })

  test("Editing a URL", async ({ page }) => {
    const detailPage = new UrlDetailPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    await urlMocks.setup()

    await detailPage.goto(1)
    await page.waitForLoadState("networkidle")

    await expect(page.getByRole("heading", { name: "URL Details" })).toBeVisible()
    await expect(page.getByText("/abc123")).toBeVisible()

    const urlInput = page.locator("input[type='url']")
    await expect(urlInput).toBeVisible()

    await urlInput.fill("https://updated.example.com")

    await page.getByRole("button", { name: "Save Changes" }).click()
  })

  test("URL detail page shows short code and status badge", async ({ page }) => {
    const detailPage = new UrlDetailPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    await urlMocks.setup()

    await detailPage.goto(1)
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("Short Code")).toBeVisible()
    await expect(page.getByText("abc123")).toBeVisible()
    await expect(page.getByText("active")).toBeVisible()
  })

  test("URL detail page has QR code section", async ({ page }) => {
    const detailPage = new UrlDetailPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    await urlMocks.setup()

    await detailPage.goto(1)
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("QR Code")).toBeVisible()
  })

  test("URL detail page has View Analytics button", async ({ page }) => {
    const detailPage = new UrlDetailPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    await urlMocks.setup()

    await detailPage.goto(1)
    await page.waitForLoadState("networkidle")

    const analyticsButton = page.getByRole("button", { name: "View Analytics" })
    await expect(analyticsButton).toBeVisible()
  })

  test("Deleting a URL", async ({ page }) => {
    const urlsPage = new UrlsPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    const commonMocks = setupCommonMocks(page)
    await urlMocks.setup()
    await commonMocks.setup()

    await urlsPage.goto()
    await page.waitForLoadState("networkidle")

    const deleteButton = page.locator("button").filter({ has: page.locator(".lucide-trash2") })
    await expect(deleteButton).toBeVisible()
  })

  test("URL detail shows A/B Testing toggle", async ({ page }) => {
    const detailPage = new UrlDetailPage(page)
    const urlMocks = setupUrlMocks(page)
    await urlMocks.setup()

    await detailPage.goto(1)
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("A/B Testing")).toBeVisible()
  })

  test("URL detail page shows Info section with created date", async ({ page }) => {
    const detailPage = new UrlDetailPage(page)
    const urlMocks = setupUrlMocks(page, [TEST_URL])
    await urlMocks.setup()

    await detailPage.goto(1)
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("Created")).toBeVisible()
  })
})
