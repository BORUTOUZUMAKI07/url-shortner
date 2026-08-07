import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const protectedPaths = [
  "/dashboard", "/urls", "/favorites", "/workspaces",
  "/folders", "/tags", "/api-keys", "/webhooks",
  "/bulk", "/audit-logs", "/billing", "/profile", "/admin",
]

const authPaths = ["/login", "/forgot-password", "/reset-password"]

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const token = request.cookies.get("access_token")?.value
  const isProtected = protectedPaths.some((p) => pathname === p || pathname.startsWith(p + "/"))
  const isAuthPage = authPaths.some((p) => pathname === p || pathname.startsWith(p + "/"))

  if (isProtected && !token) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("redirect", pathname)
    return NextResponse.redirect(loginUrl)
  }

  if (isAuthPage && token) {
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
  }

  return response
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|api/health).*)",
  ],
}
