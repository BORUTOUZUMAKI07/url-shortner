import type { NextConfig } from "next"

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
        // Proxy API calls to FastAPI backend
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
      {
        // Forward short URL redirects to backend.
        // Matches single-segment paths like /abc123 that are NOT known frontend pages.
        source: "/:short_code((?!login|register|forgot-password|reset-password|verify-email|dashboard|urls|workspaces|folders|tags|favorites|api-keys|webhooks|bulk|audit-logs|billing|profile|admin|_next|favicon).*)",
        destination: "http://127.0.0.1:8000/:short_code",
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
