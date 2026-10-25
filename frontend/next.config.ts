import type { NextConfig } from "next"

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000"

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  allowedDevOrigins: ["127.0.0.1", "localhost"],

  logging: {
    fetches: { fullUrl: true },
  },

  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },

  serverExternalPackages: ["@opentelemetry/sdk-node"],

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: "/:short_code((?!login|register|forgot-password|reset-password|verify-email|dashboard|urls|workspaces|folders|tags|favorites|api-keys|webhooks|bulk|audit-logs|profile|admin|_next|favicon).*)",
        destination: `${BACKEND_URL}/:short_code`,
      },
    ]
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains",
          },
          {
            // Deliberately narrow: framing/base/object only. A full script CSP
            // needs per-request nonces in Next.js; shipping a permissive one
            // would be security theatre.
            key: "Content-Security-Policy",
            value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
          },
        ],
      },
    ]
  },
}

export default nextConfig
