import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { Providers } from "@/lib/providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LinkForge - URL Shortener",
  description: "Enterprise-grade URL shortener with analytics and team collaboration",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "LinkForge - URL Shortener",
    description: "Enterprise-grade URL shortener with analytics and team collaboration",
    url: "https://url-shortner-peay.vercel.app",
    siteName: "LinkForge",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "LinkForge - URL Shortener",
    description: "Enterprise-grade URL shortener with analytics and team collaboration",
  },
  metadataBase: new URL("https://url-shortner-peay.vercel.app"),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col"><Providers>{children}<Toaster /></Providers></body>
    </html>
  );
}
