"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import { motion, useInView } from "motion/react"
import {
  Link2, BarChart3, Users, Upload, Key, Shield,
  Check, ChevronDown,
  ArrowRight, Sparkles, Zap, Code,
} from "lucide-react"

const features = [
  { icon: Link2, title: "Smart Links", desc: "Custom aliases, QR codes, and one-time URLs with expiration control." },
  { icon: BarChart3, title: "Real-time Analytics", desc: "Track clicks, devices, browsers, and geography in beautiful dashboards." },
  { icon: Users, title: "Team Workspaces", desc: "Collaborate with roles, folders, tags, and shared webhooks." },
  { icon: Upload, title: "Bulk Operations", desc: "Create and export hundreds of URLs at once with CSV support." },
  { icon: Key, title: "API-first", desc: "Full REST API with auto-generated keys and rate limiting." },
  { icon: Shield, title: "Enterprise Grade", desc: "Kafka events, OpenTelemetry, Prometheus metrics, and Grafana dashboards." },
]





const plans = [
  {
    name: "Free", price: "$0", desc: "Perfect for getting started",
    features: ["100 URLs/month", "Basic analytics", "5 custom aliases", "QR codes"],
  },
  {
    name: "Pro", price: "$9", desc: "For professionals and teams",
    features: ["10,000 URLs/month", "Advanced analytics", "Unlimited aliases", "Team workspaces", "API access", "Priority support"],
    popular: true,
  },
  {
    name: "Enterprise", price: "$29", desc: "For large organizations",
    features: ["Unlimited URLs", "Real-time analytics", "SSO & SAML", "Audit logs", "Dedicated support", "Custom integrations"],
  },
]

const faqs = [
  { q: "Is there a free plan?", a: "Yes! Our Free plan includes 100 URLs per month with basic analytics and QR codes." },
  { q: "Can I use my own domain?", a: "Custom domains are available on Pro and Enterprise plans." },
  { q: "How does team collaboration work?", a: "Create workspaces, invite team members, and manage roles and permissions." },
  { q: "Is there an API?", a: "Yes, we have a full REST API with auto-generated API keys and rate limiting." },
  { q: "What kind of analytics do you provide?", a: "Track clicks, devices, browsers, geographic locations, and referrer data in real-time." },
]

function AnimatedSection({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, margin: "-100px" })
  return (
    <motion.div ref={ref} initial={{ opacity: 0, y: 60 }} animate={isInView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.6, ease: "easeOut" }} className={className}>
      {children}
    </motion.div>
  )
}

export default function Home() {
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <div className="min-h-screen bg-stone-50">
      <nav className="fixed top-0 z-50 w-full border-b border-stone-200/50 bg-stone-50/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <span className="text-xl font-heading font-semibold text-stone-900">LinkForge</span>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-sm text-stone-500 hover:text-stone-900 transition-colors">Sign In</Link>
            <Link href="/register" className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors">Get Started</Link>
          </div>
        </div>
      </nav>

      <section className="relative overflow-hidden pt-32 pb-20">
        <div className="bg-grid absolute inset-0 opacity-40" />
        <div className="absolute left-1/2 top-1/3 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-500/20 blur-[128px]" />
        <div className="absolute right-1/4 top-1/4 h-64 w-64 rounded-full bg-amber-500/15 blur-[96px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-6 text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-sm text-emerald-600">
              <Sparkles className="size-3.5" />
              Enterprise-grade URL shortener
            </div>
            <h1 className="mx-auto max-w-5xl text-5xl font-heading font-semibold leading-tight text-stone-900 sm:text-6xl md:text-7xl lg:text-8xl">
              Shorten. Track.
              <br />
              <span className="bg-gradient-to-r from-emerald-600 via-amber-600 to-emerald-700 bg-clip-text text-transparent">
                Optimize.
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-stone-500 sm:text-xl">
              Enterprise-grade URL shortener with real-time analytics, team collaboration, and full observability.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link href="/register" className="group flex h-12 w-44 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 text-sm font-medium text-white hover:bg-emerald-700 transition-colors">
                Start Free <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link href="#features" onClick={(e) => { e.preventDefault(); document.getElementById("features")?.scrollIntoView({ behavior: "smooth" }) }} className="flex h-12 w-44 items-center justify-center rounded-xl border border-stone-300 bg-white text-sm font-medium text-stone-600 hover:bg-stone-200 transition-colors">
                Learn More
              </Link>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.3 }} className="relative mt-16">
            <div className="pointer-events-none absolute inset-0 -z-10">
              <div className="absolute left-1/2 top-1/2 h-[420px] w-[720px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-emerald-200/40 via-sky-100/30 to-amber-100/40 blur-3xl" />
            </div>
            <svg viewBox="0 0 800 440" className="mx-auto w-full max-w-3xl" role="img" aria-label="Illustration of a shortened link fanning out to click, analytics, team, and location destinations">
              <defs>
                <linearGradient id="hero-pill" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#059669" />
                  <stop offset="100%" stopColor="#047857" />
                </linearGradient>
              </defs>

              {/* connecting paths from the short-link pill to each destination node */}
              <path d="M400 210 C 320 170, 250 130, 165 100" fill="none" stroke="#0284c7" strokeWidth="2" strokeDasharray="1 8" strokeLinecap="round" opacity="0.5" />
              <path d="M400 210 C 320 250, 250 290, 165 335" fill="none" stroke="#e11d48" strokeWidth="2" strokeDasharray="1 8" strokeLinecap="round" opacity="0.5" />
              <path d="M400 210 C 480 170, 560 130, 645 95" fill="none" stroke="#d97706" strokeWidth="2" strokeDasharray="1 8" strokeLinecap="round" opacity="0.5" />
              <path d="M400 210 C 480 255, 560 295, 645 340" fill="none" stroke="#7c3aed" strokeWidth="2" strokeDasharray="1 8" strokeLinecap="round" opacity="0.5" />

              {/* destination node: click */}
              <g transform="translate(120,75)">
                <rect x="0" y="0" width="90" height="52" rx="14" fill="white" stroke="#e7e5e4" />
                <circle cx="26" cy="26" r="11" fill="#0284c7" fillOpacity="0.12" />
                <path d="M22 20 L32 26 L22 32 Z" fill="#0284c7" />
                <rect x="44" y="18" width="34" height="5" rx="2.5" fill="#e7e5e4" />
                <rect x="44" y="28" width="24" height="5" rx="2.5" fill="#e7e5e4" />
              </g>

              {/* destination node: analytics */}
              <g transform="translate(120,310)">
                <rect x="0" y="0" width="90" height="52" rx="14" fill="white" stroke="#e7e5e4" />
                <rect x="16" y="30" width="8" height="12" rx="2" fill="#e11d48" fillOpacity="0.7" />
                <rect x="28" y="22" width="8" height="20" rx="2" fill="#e11d48" />
                <rect x="40" y="14" width="8" height="28" rx="2" fill="#e11d48" fillOpacity="0.7" />
                <rect x="58" y="18" width="24" height="5" rx="2.5" fill="#e7e5e4" />
                <rect x="58" y="28" width="18" height="5" rx="2.5" fill="#e7e5e4" />
              </g>

              {/* destination node: team */}
              <g transform="translate(590,70)">
                <rect x="0" y="0" width="90" height="52" rx="14" fill="white" stroke="#e7e5e4" />
                <circle cx="24" cy="22" r="9" fill="#d97706" fillOpacity="0.85" />
                <circle cx="36" cy="22" r="9" fill="#d97706" fillOpacity="0.35" />
                <rect x="16" y="36" width="52" height="5" rx="2.5" fill="#e7e5e4" />
              </g>

              {/* destination node: global reach */}
              <g transform="translate(590,315)">
                <rect x="0" y="0" width="90" height="52" rx="14" fill="white" stroke="#e7e5e4" />
                <circle cx="26" cy="26" r="12" fill="none" stroke="#7c3aed" strokeWidth="2" />
                <ellipse cx="26" cy="26" rx="5" ry="12" fill="none" stroke="#7c3aed" strokeWidth="1.5" />
                <line x1="14" y1="26" x2="38" y2="26" stroke="#7c3aed" strokeWidth="1.5" />
                <rect x="46" y="20" width="30" height="5" rx="2.5" fill="#e7e5e4" />
                <rect x="46" y="30" width="20" height="5" rx="2.5" fill="#e7e5e4" />
              </g>

              {/* central short-link pill */}
              <g transform="translate(310,182)">
                <rect x="0" y="0" width="180" height="56" rx="28" fill="url(#hero-pill)" />
                <circle cx="28" cy="28" r="12" fill="white" fillOpacity="0.15" />
                <path d="M22 28 h12 M25 24 a4 4 0 0 1 0 8 M31 24 a4 4 0 0 1 0 8" stroke="white" strokeWidth="2.5" strokeLinecap="round" fill="none" />
                <text x="52" y="33" fontSize="17" fontFamily="ui-monospace, monospace" fill="white" fontWeight="600">lnkfg.co/x7K9p</text>
              </g>
            </svg>
          </motion.div>
        </div>
      </section>

      <section id="features" className="relative border-t border-stone-200/50 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <AnimatedSection>
            <p className="text-center text-xs font-semibold uppercase tracking-[0.2em] text-emerald-600">Features</p>
            <h2 className="mt-3 text-center text-3xl font-heading font-semibold text-stone-900 sm:text-4xl">
              Everything you need
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-center text-stone-500">
              Powerful features designed for teams who need reliable link management.
            </p>
          </AnimatedSection>
          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="group relative overflow-hidden rounded-xl border border-stone-200 bg-white p-6 transition-all hover:-translate-y-1 hover:border-stone-300 hover:shadow-md"
              >
                <span className="pointer-events-none absolute -right-2 -top-2 font-heading text-6xl font-semibold text-stone-100 transition-colors group-hover:text-stone-200">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className={`relative mb-4 flex size-12 items-center justify-center rounded-lg ${i % 2 === 0 ? "bg-emerald-500/10 text-emerald-600 group-hover:bg-emerald-500/15" : "bg-amber-500/10 text-amber-600 group-hover:bg-amber-500/15"} transition-colors`}>
                  <f.icon className="size-6" />
                </div>
                <h3 className="relative mb-2 text-lg font-semibold text-stone-900">{f.title}</h3>
                <p className="relative text-sm leading-relaxed text-stone-500">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>



      <section id="pricing" className="border-t border-stone-200/50 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <AnimatedSection>
            <p className="text-center text-xs font-semibold uppercase tracking-[0.2em] text-emerald-600">Pricing</p>
            <h2 className="mt-3 text-center text-3xl font-heading font-semibold text-stone-900 sm:text-4xl">
              Simple, transparent pricing
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-center text-stone-500">
              Start free, upgrade as you grow.
            </p>
          </AnimatedSection>
          <div className="mt-16 grid gap-8 lg:grid-cols-3">
            {plans.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.15 }}
                className={`relative rounded-xl border p-8 transition-all hover:-translate-y-1 ${plan.popular ? "border-emerald-500/50 bg-white shadow-lg shadow-emerald-900/5" : "border-stone-200 bg-white hover:shadow-sm"}`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-emerald-600 px-4 py-1 text-xs font-medium text-white shadow-sm">
                    <Zap className="size-3" /> Most Popular
                  </div>
                )}
                <h3 className="text-lg font-semibold text-stone-900">{plan.name}</h3>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="font-heading text-4xl font-semibold text-stone-900">{plan.price}</span>
                  <span className="text-sm text-stone-500">/month</span>
                </div>
                <p className="mt-2 text-sm text-stone-500">{plan.desc}</p>
                <ul className="mt-6 space-y-3">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm text-stone-600">
                      <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600">
                        <Check className="size-2.5" strokeWidth={3} />
                      </span>
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/register"
                  className={`mt-8 flex h-11 w-full items-center justify-center rounded-lg text-sm font-medium transition-colors ${plan.popular ? "bg-emerald-600 text-white hover:bg-emerald-700" : "border border-stone-300 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
                >
                  Get Started
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-stone-200/50 px-6 py-24">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <p className="text-center text-xs font-semibold uppercase tracking-[0.2em] text-emerald-600">FAQ</p>
            <h2 className="mt-3 text-center text-3xl font-heading font-semibold text-stone-900 sm:text-4xl">
              Frequently asked questions
            </h2>
          </AnimatedSection>
          <div className="mt-12 space-y-3">
            {faqs.map((faq, i) => (
              <div key={i} className="rounded-xl border border-stone-200 bg-white overflow-hidden transition-colors hover:border-stone-300">
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)} className="flex w-full items-center justify-between px-6 py-4 text-left text-sm font-medium text-stone-900 transition-colors hover:bg-stone-50">
                  {faq.q}
                  <ChevronDown className={`size-4 shrink-0 text-stone-500 transition-transform ${openFaq === i ? "rotate-180 text-emerald-600" : ""}`} />
                </button>
                <motion.div initial={false} animate={{ height: openFaq === i ? "auto" : 0 }} className="overflow-hidden">
                  <p className="border-t border-stone-200 px-6 py-4 text-sm text-stone-500">{faq.a}</p>
                </motion.div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden border-t border-stone-200/50 px-6 py-24">
        <div className="absolute inset-0 bg-gradient-to-r from-emerald-600/10 via-amber-500/10 to-emerald-600/10" />
        <div className="relative z-10 mx-auto max-w-3xl text-center">
          <AnimatedSection>
            <h2 className="text-3xl font-heading font-semibold text-stone-900 sm:text-4xl">
              Ready to simplify your links?
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-stone-500">
              Join hundreds of teams already using LinkForge. Start free, no credit card required.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link href="/register" className="flex h-12 w-44 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 text-sm font-medium text-white hover:bg-emerald-700 transition-colors">
                Get Started Free <ArrowRight className="size-4" />
              </Link>
              <Link href="https://github.com/BORUTOUZUMAKI07/url-shortner" target="_blank" className="flex h-12 w-44 items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white text-sm font-medium text-stone-600 hover:bg-stone-200 transition-colors">
                <Code className="size-4" /> View on GitHub
              </Link>
            </div>
          </AnimatedSection>
        </div>
      </section>

      <footer className="border-t border-stone-200/50 px-6 py-12">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <span className="text-lg font-heading font-semibold text-stone-900">LinkForge</span>
              <p className="mt-2 text-sm text-stone-500">Enterprise-grade URL shortener with analytics and team collaboration.</p>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold text-stone-900">Product</h4>
              <ul className="space-y-2 text-sm text-stone-500">
                <li><Link href="#features" className="hover:text-stone-900 transition-colors">Features</Link></li>
                <li><Link href="/login" className="hover:text-stone-900 transition-colors">Sign In</Link></li>
                <li><Link href="/register" className="hover:text-stone-900 transition-colors">Get Started</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold text-stone-900">Developers</h4>
              <ul className="space-y-2 text-sm text-stone-500">
                <li><Link href="/login" className="hover:text-stone-900 transition-colors">API Keys</Link></li>
                <li><Link href="/login" className="hover:text-stone-900 transition-colors">Dashboard</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold text-stone-900">Resources</h4>
              <ul className="space-y-2 text-sm text-stone-500">
                <li><a href="https://github.com/BORUTOUZUMAKI07/url-shortner" target="_blank" className="hover:text-stone-900 transition-colors">GitHub</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-12 border-t border-stone-200 pt-6 text-center text-sm text-stone-400">
            LinkForge — Built with Next.js, FastAPI, and love.
          </div>
        </div>
      </footer>
    </div>
  )
}
