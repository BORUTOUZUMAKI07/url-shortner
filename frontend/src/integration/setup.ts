/**
 * Integration-test harness: makes Node's fetch persist httpOnly cookies.
 *
 * `api.ts` authenticates via backend `Set-Cookie` headers (access_token /
 * refresh_token are httpOnly, so the browser normally owns them). Node has no
 * cookie store, so each test needs one. This wrapper captures Set-Cookie on
 * responses and replays the matching cookies on subsequent requests — enough
 * to drive `auth.login` → `auth.me` → `auth.refresh` against a real backend.
 */
import { beforeAll } from "vitest"

const originalFetch = globalThis.fetch

type Cookie = { value: string; path: string; expiresAt: number | null }

// host -> cookieName -> Cookie
const store = new Map<string, Map<string, Cookie>>()

function parseSetCookie(setCookie: string): { name: string; value: string; path: string; maxAge: number | null } {
  const [first, ...rest] = setCookie.split(";")
  const eq = first.indexOf("=")
  const name = eq === -1 ? first.trim() : first.slice(0, eq).trim()
  const value = eq === -1 ? "" : first.slice(eq + 1).trim()
  let path = "/"
  let maxAge: number | null = null
  for (const part of rest) {
    const bits = part.trim().split("=")
    const key = bits[0]!.toLowerCase()
    const val = bits.slice(1).join("=")
    if (key === "path") path = val || "/"
    if (key === "max-age") maxAge = Number(val)
  }
  return { name, value, path, maxAge }
}

function applySetCookies(url: URL, setCookies: string[]) {
  const hostMap = store.get(url.host) ?? new Map()
  for (const header of setCookies) {
    const { name, value, path, maxAge } = parseSetCookie(header)
    if (maxAge !== null && maxAge <= 0) {
      hostMap.delete(name)
    } else {
      hostMap.set(name, {
        value,
        path,
        expiresAt: maxAge === null ? null : Date.now() + maxAge * 1000,
      })
    }
  }
  store.set(url.host, hostMap)
}

function cookieHeaderFor(url: URL): string {
  const hostMap = store.get(url.host)
  if (!hostMap) return ""
  const now = Date.now()
  const parts: string[] = []
  for (const [name, cookie] of hostMap) {
    if (cookie.expiresAt !== null && now >= cookie.expiresAt) continue
    if (url.pathname.startsWith(cookie.path) || cookie.path === "/") {
      parts.push(`${name}=${cookie.value}`)
    }
  }
  return parts.join("; ")
}

// The production bridge turns the httpOnly access_token cookie into an
// `Authorization: Bearer` header (frontend/src/proxy.ts). Node's fetch bypasses
// the Next proxy, so this wrapper must do the same or every authed request 401s.
function authorizationFor(url: URL): string | undefined {
  const hostMap = store.get(url.host)
  const access = hostMap?.get("access_token")
  if (!access || (access.expiresAt !== null && Date.now() >= access.expiresAt)) return undefined
  return `Bearer ${access.value}`
}

beforeAll(() => {
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url)
    const headers = new Headers(init?.headers)
    const cookie = cookieHeaderFor(url)
    if (cookie) headers.set("cookie", cookie)
    if (!headers.has("authorization")) {
      const authorization = authorizationFor(url)
      if (authorization) headers.set("Authorization", authorization)
    }

    const res = await originalFetch(url, { ...init, headers, credentials: "include" })
    const setCookies =
      typeof res.headers.getSetCookie === "function" ? res.headers.getSetCookie() : []
    if (setCookies.length > 0) applySetCookies(url, setCookies)
    return res
  }) as typeof fetch
})