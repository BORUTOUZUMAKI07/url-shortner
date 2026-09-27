import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Short URLs are served by the backend's root-level redirect route, not by
// this Next.js app — so the correct host is the backend's own origin
// (NEXT_PUBLIC_API_URL), not window.location.origin, except in same-origin
// reverse-proxy deployments where NEXT_PUBLIC_API_URL is unset.
export function buildShortUrl(url: { domain?: string | null; short_code: string }) {
  const base = url.domain
    ? `https://${url.domain}`
    : process.env.NEXT_PUBLIC_API_URL || (typeof window !== "undefined" ? window.location.origin : "")
  return `${base}/${url.short_code}`
}
