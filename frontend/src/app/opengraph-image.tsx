import { ImageResponse } from "next/og";

export const contentType = "image/png";
export const size = { width: 1200, height: 630 };

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #1d4ed8 100%)",
          color: "white",
          fontFamily: '"Inter", sans-serif',
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginBottom: 30,
          }}
        >
          <svg width="64" height="64" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="6" fill="white" />
            <path d="M10 16c0-3.3 2.7-6 6-6s6 2.7 6 6-2.7 6-6 6" stroke="#2563eb" stroke-width="2" fill="none" />
            <path d="M16 7v7m0 3v0" stroke="#2563eb" stroke-width="2" stroke-linecap="round" />
            <circle cx="16" cy="16" r="2" fill="#2563eb" />
          </svg>
          <span style={{ fontSize: 64, fontWeight: 800, letterSpacing: "-0.02em" }}>LinkForge</span>
        </div>
        <div style={{ fontSize: 28, opacity: 0.85, textAlign: "center", fontWeight: 500 }}>
          Enterprise-grade URL shortener with analytics
        </div>
        <div style={{ fontSize: 20, opacity: 0.6, marginTop: 20 }}>
          linkforge.app
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
