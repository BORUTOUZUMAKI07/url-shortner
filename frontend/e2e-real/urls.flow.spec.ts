import { test, expect } from "@playwright/test"
import { registerAndLogin } from "./helpers"

test("create a short URL, see it listed, and follow the real redirect", async ({ page }) => {
  await registerAndLogin(page)

  await page.goto("/urls/new")
  await page.getByPlaceholder("https://example.com/very/long/url").fill("https://example.com/e2e-redirect-target")
  // The workspace selector loads asynchronously; "Create URL" stays disabled
  // until the form is valid (workspace_id >= 1), so wait for it to enable.
  await expect(page.getByRole("button", { name: "Create URL" })).toBeEnabled()
  await page.getByRole("button", { name: "Create URL" }).click()
  // The success path pushes /urls client-side (router.push) — no document load.
  await expect(page).toHaveURL(/\/urls$/)

  // The list row links to /{short_code} (all URL rows use target="_blank").
  const shortLink = page.locator('a[target="_blank"]').first()
  await expect(shortLink).toBeVisible()
  const href = await shortLink.getAttribute("href")
  expect(href).toMatch(/^\/[a-zA-Z0-9_-]+$/)
  const shortCode = href!.slice(1)

  // Follow the redirect through the real chain: Next proxy → backend → original.
  await page.goto(`http://127.0.0.1:3000/${shortCode}`)
  await page.waitForURL(/^https:\/\/example\.com\//)
  await expect(page).toHaveURL(/^https:\/\/example\.com\/e2e-redirect-target$/)
})