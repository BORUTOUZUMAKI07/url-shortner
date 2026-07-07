import { test, expect, WorkspacesPage, setupAuthMocks, setupWorkspaceMocks, setAuthState, TEST_WORKSPACE } from "./fixtures"

test.describe("Workspace Management", () => {
  test.beforeEach(async ({ page }) => {
    const authMocks = setupAuthMocks(page)
    await authMocks.setup()
    await setAuthState(page)
  })

  test("Creating a workspace", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByRole("heading", { name: "Workspaces" })).toBeVisible()
    await expect(page.getByText("Create Workspace")).toBeVisible()

    await workspacesPage.fillNewName("New Workspace")
    await workspacesPage.clickCreate()
  })

  test("Displays created workspaces", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [TEST_WORKSPACE])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("My Workspace")).toBeVisible()
  })

  test("Shows empty state when no workspaces", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText("No workspaces yet")).toBeVisible()
  })

  test("Shows member count on workspace card", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [TEST_WORKSPACE])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText(/Members/)).toBeVisible()
  })

  test("Shows Accept Invite button", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [TEST_WORKSPACE])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    const acceptInviteButton = page.getByRole("button", { name: "Accept Invite" })
    await expect(acceptInviteButton).toBeVisible()
  })

  test("Accept Invite dialog opens and has input field", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [TEST_WORKSPACE])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await page.getByRole("button", { name: "Accept Invite" }).click()
    await expect(page.getByPlaceholder("Paste invite token")).toBeVisible()
  })

  test("Inviting members shows invite UI when workspace is expanded", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [TEST_WORKSPACE])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    const membersButton = page.getByRole("button", { name: /Members/ })
    await membersButton.click()

    await expect(page.getByPlaceholder("Email to invite")).toBeVisible()
  })

  test("Accept Invite modal has Accept button", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [TEST_WORKSPACE])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await page.getByRole("button", { name: "Accept Invite" }).click()
    await expect(page.getByRole("button", { name: "Accept" })).toBeVisible()
  })

  test("Workspace creation input validation - empty name", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await workspacesPage.clickCreate()
    await expect(page.getByPlaceholder("Workspace name")).toBeVisible()
  })

  test("Workspace page shows Owner ID", async ({ page }) => {
    const workspacesPage = new WorkspacesPage(page)
    const wsMocks = setupWorkspaceMocks(page, [TEST_WORKSPACE])
    await wsMocks.setup()

    await workspacesPage.goto()
    await page.waitForLoadState("networkidle")

    await expect(page.getByText(`Owner ID: ${TEST_WORKSPACE.owner_id}`)).toBeVisible()
  })
})
