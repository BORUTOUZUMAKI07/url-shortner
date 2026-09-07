import { test, expect } from "@playwright/test"
import { registerAndLogin } from "./helpers"

test("register → sign in → authenticated dashboard with logout escape hatch", async ({ page }) => {
  const email = await registerAndLogin(page)
  await expect(page).toHaveURL(/\/dashboard$/)

  // The sidebar is hydrated from the real /auth/me: user email is visible.
  await expect(page.getByText(email)).toBeVisible({ timeout: 15_000 })
  // Logout is outside the {user && ...} gate — always present.
  await expect(page.getByRole("button", { name: "Logout" })).toBeVisible()

  await page.getByRole("button", { name: "Logout" }).click()
  await page.waitForURL("**/login")
  await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible()
})