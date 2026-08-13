import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const protectedPaths = [
  "/dashboard", "/urls", "/favorites", "/workspaces",
  "/folders", "/tags", "/api-keys", "/webhooks",
  "/bulk", "/audit-logs", "/billing", "/profile", "/admin",
]

const authPaths = ["/login", "/forgot-password", "/reset-password"]

function decodeTokenExp(token: string): number | null {
  try {
    const part = token.split(".")[1]
    if (!part) return null
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/")
    const padded = b64.padEnd(b64.length + ((4 - (b64.length % 4)) % 4), "=")
    const payload = JSON.parse(atob(padded))
    return typeof payload.exp === "number" ? payload.exp : null
  } catch {
    return null
  }
}

function isTokenValid(token: string | undefined): boolean {
  if (!token) return false
  const exp = decodeTokenExp(token)
  if (exp === null) return false
  return exp * 1000 > Date.now()
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const cookieToken = request.cookies.get("access_token")?.value
  const token = isTokenValid(cookieToken) ? cookieToken : undefined
  const isProtected = protectedPaths.some((p) => pathname === p || pathname.startsWith(p + "/"))
  const isAuthPage = authPaths.some((p) => pathname === p || pathname.startsWith(p + "/"))

  if (isProtected && !token) {
    const loginUrl = new URL("/login", request.url)
    // Keep the query string so flows like /workspaces?invite_token=XYZ survive
    // the round trip through login.
    loginUrl.searchParams.set("redirect", pathname + request.nextUrl.search)
    return NextResponse.redirect(loginUrl)
  }

  // Do NOT bounce an auth page to /dashboard when it carries a one-time OAuth
  // handoff `code` (a stale valid cookie would otherwise swallow the handoff and
  // the user never gets signed in) or an `expired=1` flag (a session-expired
  // redirect that must be allowed to reach the login form, or it loops).
  const hasLoginPurpose =
    request.nextUrl.searchParams.has("code") || request.nextUrl.searchParams.has("expired")

  if (isAuthPage && token && !hasLoginPurpose) {
    return NextResponse.redirect(new URL("/dashboard", request.url))
  }

  const requestHeaders = new Headers(request.headers)
  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`)
  }

  const response = NextResponse.next({ request: { headers: requestHeaders } })

  if (token) {
    response.cookies.set("access_token", token, {
      path: "/",
      maxAge: 604800,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      httpOnly: true,
    })
  } else if (cookieToken) {
    response.cookies.set("access_token", "", { path: "/", maxAge: 0 })
  }

  return response
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|api/health).*)",
  ],
}
