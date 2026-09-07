import { expect, type Page } from "@playwright/test"

export const TEST_PASSWORD = "StrongPass1!"

export function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
}

export async function registerAndLogin(page: Page): Promise<string> {
  const email = uniqueEmail()

  await page.goto("/register")
  await page.getByPlaceholder("Email", { exact: true }).fill(email)
  await page.getByPlaceholder("Password", { exact: true }).fill(TEST_PASSWORD)
  await page.getByPlaceholder("Confirm Password", { exact: true }).fill(TEST_PASSWORD)
  await page.getByRole("button", { name: "Create Account" }).click()
  // First registration on a cold backend runs the argon2 hash synchronously —
  // give the success panel the full action timeout, not the 5s assertion default.
  await expect(page.getByText("Account Created")).toBeVisible({ timeout: 60_000 })

  await page.getByRole("link", { name: "Sign In" }).click()
  await page.getByPlaceholder("Email", { exact: true }).fill(email)
  await page.getByPlaceholder("Password", { exact: true }).fill(TEST_PASSWORD)
  await page.getByRole("button", { name: "Sign In" }).click()
  await page.waitForURL("**/dashboard")

  return email
}