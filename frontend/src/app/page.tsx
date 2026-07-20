"use client"

import Link from "next/link"
import { BackgroundBeams } from "@/components/ui/background-beams"

const features = [
  { title: "Smart Links", desc: "Custom aliases, QR codes, and one-time URLs with expiration control." },
  { title: "Real-time Analytics", desc: "Track clicks, devices, browsers, and geography in beautiful dashboards." },
  { title: "Team Workspaces", desc: "Collaborate with roles, folders, tags, and shared webhooks." },
  { title: "Bulk Operations", desc: "Create and export hundreds of URLs at once with CSV support." },
  { title: "API-first", desc: "Full REST API with auto-generated keys and rate limiting." },
  { title: "Enterprise Grade", desc: "Kafka events, OpenTelemetry, Prometheus metrics, and Grafana dashboards." },
]

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-zinc-950">
      <BackgroundBeams className="opacity-30" />

      <div className="relative z-20">
        <nav className="flex items-center justify-between px-4 py-4 sm:px-6">
          <span className="text-lg sm:text-xl font-bold text-white">LinkForge</span>
          <div className="flex items-center gap-3 sm:gap-4">
            <Link href="/login" className="text-xs sm:text-sm text-zinc-400 hover:text-white transition-colors">Sign In</Link>
            <Link
              href="/login"
              className="rounded-lg bg-blue-600 px-3 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Get Started
            </Link>
          </div>
        </nav>

        <section className="flex flex-col items-center justify-center px-4 pt-24 pb-16 text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-400">
            <span className="size-2 rounded-full bg-blue-400 animate-pulse" />
            Enterprise-grade URL shortener
          </div>
          <h1 className="max-w-4xl text-4xl font-bold leading-tight text-white sm:text-6xl md:text-7xl">
            Shorten. Track.
            <br />
            <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Optimize.
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-base text-zinc-400 sm:text-lg">
            Enterprise-grade URL shortener with real-time analytics, team collaboration, and full observability.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center gap-4">
            <Link
              href="/login"
              className="flex h-12 w-40 items-center justify-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Start Free
            </Link>
            <Link
              href="#features"
              className="flex h-12 w-40 items-center justify-center rounded-xl border border-zinc-700 bg-zinc-900 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition-colors"
              scroll={false}
              onClick={(e) => { e.preventDefault(); document.getElementById("features")?.scrollIntoView({ behavior: "smooth" }) }}
            >
              Learn More
            </Link>
          </div>
        </section>

        <section id="features" className="px-6 pb-24">
          <div className="mx-auto max-w-6xl">
            <h2 className="mb-12 text-center text-3xl font-bold text-white">Everything you need</h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {features.map((f) => (
                <div
                  key={f.title}
                  className="group rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 backdrop-blur-sm transition-colors hover:border-zinc-700"
                >
                  <h3 className="mb-2 text-lg font-semibold text-white">{f.title}</h3>
                  <p className="text-sm leading-relaxed text-zinc-400">{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <footer className="border-t border-zinc-800 px-6 py-6">
          <p className="text-center text-sm text-zinc-500">LinkForge — Built with Next.js, FastAPI, and love.</p>
        </footer>
      </div>
    </div>
  )
}
