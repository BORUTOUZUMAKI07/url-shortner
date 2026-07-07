import { describe, it, expect, vi, beforeEach } from "vitest"
import { setTokenCookie, setRefreshTokenCookie, clearTokenCookies } from "@/lib/token-cookie"

describe("token-cookie", () => {
  beforeEach(() => {
    document.cookie.split(";").forEach((c) => {
      document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/")
    })
  })

  it("setTokenCookie sets the access_token cookie", () => {
    setTokenCookie("test-token")
    expect(document.cookie).toContain("access_token=test-token")
  })

  it("setRefreshTokenCookie sets the refresh_token cookie", () => {
    setRefreshTokenCookie("refresh-test")
    expect(document.cookie).toContain("refresh_token=refresh-test")
  })

  it("clearTokenCookies removes both cookies", () => {
    setTokenCookie("token")
    setRefreshTokenCookie("refresh")
    clearTokenCookies()
    expect(document.cookie).not.toContain("access_token")
    expect(document.cookie).not.toContain("refresh_token")
  })

  it("clearTokenCookies is safe when called without cookies", () => {
    clearTokenCookies()
    expect(document.cookie).not.toContain("access_token")
  })
})
