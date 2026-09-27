import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Short URLs at the app's own origin are handled by next.config.ts's
// rewrite (source: "/:short_code..." -> BACKEND_URL), so a relative path
// is correct and portable across every deployment. Custom domains bypass
// that rewrite entirely and go straight to their own host.
export function buildShortUrl(url: { domain?: string | null; short_code: string }) {
  if (url.domain) return `https://${url.domain}/${url.short_code}`
  return `/${url.short_code}`
}

// For copy-to-clipboard / anywhere the URL leaves the app (Slack, email, a
// README) a relative path is useless — this always returns a full,
// paste-anywhere URL. Client-only (reads window.location), which is fine
// since every caller is a click handler, never SSR render.
export function buildShareableShortUrl(url: { domain?: string | null; short_code: string }) {
  if (url.domain) return `https://${url.domain}/${url.short_code}`
  const origin = typeof window !== "undefined" ? window.location.origin : ""
  return `${origin}/${url.short_code}`
}
