import type { NextConfig } from "next"

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000"

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,

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
        source: "/:short_code((?!login|register|forgot-password|reset-password|verify-email|dashboard|urls|workspaces|folders|tags|favorites|api-keys|webhooks|bulk|audit-logs|billing|profile|admin|_next|favicon).*)",
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
        ],
      },
    ]
  },
}

export default nextConfig
