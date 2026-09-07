import { test, expect } from "@playwright/test"
import { registerAndLogin } from "./helpers"

test("create a workspace and see it in the workspace list", async ({ page }) => {
  await registerAndLogin(page)

  await page.goto("/workspaces")
  const workspaceName = `Team-${Date.now().toString().slice(-6)}`
  await page.getByPlaceholder("Workspace name").fill(workspaceName)
  await page.getByRole("button", { name: "Create" }).click()

  await expect(page.getByText(workspaceName)).toBeVisible({ timeout: 60_000 })
})