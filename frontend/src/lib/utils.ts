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
