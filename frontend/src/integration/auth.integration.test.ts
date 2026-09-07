import { describe, it, expect } from "vitest"
import { auth } from "@/lib/api"

const PASSWORD = "StrongPass1!"

function uniqueEmail(): string {
  return `it-${Math.random().toString(36).slice(2, 12)}@example.com`
}

describe("auth API against a real backend", () => {
  it("registers, logs in with httpOnly cookies, then answers /me", async () => {
    const email = uniqueEmail()
    const registered = await auth.register(email, PASSWORD)
    expect(registered.email).toBe(email)

    const token = await auth.login(email, PASSWORD)
    expect(token.access_token).toBeTruthy()
    expect(token.refresh_token).toBeTruthy()

    const me = await auth.me()
    expect(me.email).toBe(email)
  })

  it("rotates tokens on refresh", async () => {
    const email = uniqueEmail()
    await auth.register(email, PASSWORD)
    const token = await auth.login(email, PASSWORD)

    const refreshed = await auth.refresh(token.refresh_token)
    expect(refreshed.access_token).toBeTruthy()
    expect(refreshed.refresh_token).not.toBe(token.refresh_token)

    const me = await auth.me()
    expect(me.email).toBe(email)
  })

  it("invalidate_cookie session on logout", async () => {
    const email = uniqueEmail()
    await auth.register(email, PASSWORD)
    await auth.login(email, PASSWORD)

    await auth.logout()
    // The access/refresh cookies were deleted server-side; /me must now 401.
    await expect(auth.me()).rejects.toThrow()
  })

  it("rejects a wrong password", async () => {
    const email = uniqueEmail()
    await auth.register(email, PASSWORD)
    await expect(auth.login(email, "wrongpass")).rejects.toThrow()
  })
})