"use client"

import { useRef, useState, useEffect } from "react"
import Link from "next/link"
import { motion, useInView } from "motion/react"
import {
  Link2, BarChart3, Users, Upload, Key, Shield,
  Check, ChevronDown, ExternalLink, Quote,
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

const stats = [
  { label: "URLs Shortened", value: "10K+" },
  { label: "Active Users", value: "500+" },
  { label: "Clicks Tracked", value: "1M+" },
  { label: "Uptime", value: "99.9%" },
]

const testimonials = [
  { quote: "LinkForge transformed how our team manages links. The analytics are incredible.", author: "Alex K.", role: "Engineering Lead" },
  { quote: "The API-first approach made integration effortless. Best URL shortener we've used.", author: "Sarah M.", role: "Developer" },
  { quote: "Bulk operations save us hours every week. The workspace collaboration is a game changer.", author: "James R.", role: "Marketing Director" },
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

function Counter({ value, suffix = "" }: { value: string; suffix?: string }) {
  const [count, setCount] = useState(0)
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true })
  const num = parseInt(value.replace(/\D/g, ""))

  useEffect(() => {
    if (!isInView) return
    let start = 0
    const dur = 2000
    const step = Math.max(1, Math.floor(num / 60))
    const interval = setInterval(() => {
      start += step
      if (start >= num) { start = num; clearInterval(interval) }
      setCount(start)
    }, dur / 60)
    return () => clearInterval(interval)
  }, [isInView, num])

  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>
}

export default function Home() {
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <div className="min-h-screen bg-zinc-950">
      <nav className="fixed top-0 z-50 w-full border-b border-zinc-800/50 bg-zinc-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <span className="text-xl font-bold text-white">LinkForge</span>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-sm text-zinc-400 hover:text-white transition-colors">Sign In</Link>
            <Link href="/register" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors">Get Started</Link>
          </div>
        </div>
      </nav>

      <section className="relative overflow-hidden pt-32 pb-20">
        <div className="bg-grid absolute inset-0 opacity-40" />
        <div className="absolute left-1/2 top-1/3 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-500/20 blur-[128px]" />
        <div className="absolute right-1/4 top-1/4 h-64 w-64 rounded-full bg-purple-500/15 blur-[96px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-6 text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-400">
              <Sparkles className="size-3.5" />
              Enterprise-grade URL shortener
            </div>
            <h1 className="mx-auto max-w-5xl text-5xl font-bold leading-tight text-white sm:text-6xl md:text-7xl lg:text-8xl">
              Shorten. Track.
              <br />
              <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                Optimize.
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-400 sm:text-xl">
              Enterprise-grade URL shortener with real-time analytics, team collaboration, and full observability.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link href="/register" className="group flex h-12 w-44 items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 text-sm font-medium text-white hover:bg-blue-700 transition-colors">
                Start Free <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link href="#features" onClick={(e) => { e.preventDefault(); document.getElementById("features")?.scrollIntoView({ behavior: "smooth" }) }} className="flex h-12 w-44 items-center justify-center rounded-xl border border-zinc-700 bg-zinc-900 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition-colors">
                Learn More
              </Link>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.3 }} className="mt-16">
            <div className="mx-auto max-w-4xl rounded-2xl border border-zinc-800 bg-zinc-900/50 p-2 backdrop-blur-sm">
              <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
                <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
                  <div className="size-3 rounded-full bg-red-500" />
                  <div className="size-3 rounded-full bg-yellow-500" />
                  <div className="size-3 rounded-full bg-green-500" />
                  <span className="ml-2 text-xs text-zinc-500">Preview</span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-4">
                  <div className="rounded-lg bg-zinc-800/50 p-4">
                    <div className="text-xs text-zinc-500">Smart Links</div>
                    <div className="mt-1 text-lg font-bold text-white">Custom aliases &amp; QR codes</div>
                  </div>
                  <div className="rounded-lg bg-zinc-800/50 p-4">
                    <div className="text-xs text-zinc-500">Analytics</div>
                    <div className="mt-1 text-lg font-bold text-white">Real-time dashboards</div>
                  </div>
                  <div className="rounded-lg bg-zinc-800/50 p-4">
                    <div className="text-xs text-zinc-500">Collaboration</div>
                    <div className="mt-1 text-lg font-bold text-white">Team workspaces</div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section id="features" className="relative border-t border-zinc-800/50 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <AnimatedSection>
            <h2 className="text-center text-3xl font-bold text-white sm:text-4xl">
              Everything you need
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-center text-zinc-400">
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
                className="group rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 backdrop-blur-sm transition-all hover:border-zinc-700 hover:bg-zinc-800/50 hover:-translate-y-1"
              >
                <div className="mb-4 flex size-12 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400 transition-colors group-hover:bg-blue-500/20">
                  <f.icon className="size-6" />
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">{f.title}</h3>
                <p className="text-sm leading-relaxed text-zinc-400">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-800/50 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <AnimatedSection>
            <h2 className="text-center text-3xl font-bold text-white sm:text-4xl">
              Trusted by teams worldwide
            </h2>
          </AnimatedSection>
          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="text-center"
              >
                <div className="text-4xl font-bold gradient-text sm:text-5xl">
                  <Counter value={s.value} />
                </div>
                <div className="mt-2 text-sm text-zinc-400">{s.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-800/50 bg-zinc-900/30 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <AnimatedSection>
            <h2 className="text-center text-3xl font-bold text-white sm:text-4xl">
              What our users say
            </h2>
          </AnimatedSection>
          <div className="mt-16 grid gap-6 md:grid-cols-3">
            {testimonials.map((t, i) => (
              <motion.div
                key={t.author}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.15 }}
                className="glass rounded-xl p-6"
              >
                <Quote className="mb-4 size-6 text-blue-400" />
                <p className="text-sm leading-relaxed text-zinc-300">&ldquo;{t.quote}&rdquo;</p>
                <div className="mt-4 border-t border-zinc-800 pt-4">
                  <div className="text-sm font-medium text-white">{t.author}</div>
                  <div className="text-xs text-zinc-500">{t.role}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="border-t border-zinc-800/50 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <AnimatedSection>
            <h2 className="text-center text-3xl font-bold text-white sm:text-4xl">
              Simple, transparent pricing
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-center text-zinc-400">
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
                className={`relative rounded-xl border p-8 transition-all hover:-translate-y-1 ${plan.popular ? "border-blue-500/50 bg-blue-500/5" : "border-zinc-800 bg-zinc-900/50"}`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-4 py-1 text-xs font-medium text-white">
                    <Zap className="mr-1 inline size-3" /> Most Popular
                  </div>
                )}
                <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-white">{plan.price}</span>
                  <span className="text-sm text-zinc-400">/month</span>
                </div>
                <p className="mt-2 text-sm text-zinc-400">{plan.desc}</p>
                <ul className="mt-6 space-y-3">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-zinc-300">
                      <Check className="mt-0.5 size-4 shrink-0 text-green-400" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/register"
                  className={`mt-8 flex h-11 w-full items-center justify-center rounded-lg text-sm font-medium transition-colors ${plan.popular ? "bg-blue-600 text-white hover:bg-blue-700" : "border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700"}`}
                >
                  Get Started
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-800/50 px-6 py-24">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <h2 className="text-center text-3xl font-bold text-white sm:text-4xl">
              Frequently asked questions
            </h2>
          </AnimatedSection>
          <div className="mt-12 space-y-3">
            {faqs.map((faq, i) => (
              <div key={i} className="glass rounded-xl overflow-hidden">
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)} className="flex w-full items-center justify-between px-6 py-4 text-left text-sm font-medium text-white transition-colors hover:bg-zinc-800/50">
                  {faq.q}
                  <ChevronDown className={`size-4 text-zinc-400 transition-transform ${openFaq === i ? "rotate-180" : ""}`} />
                </button>
                <motion.div initial={false} animate={{ height: openFaq === i ? "auto" : 0 }} className="overflow-hidden">
                  <p className="border-t border-zinc-800 px-6 py-4 text-sm text-zinc-400">{faq.a}</p>
                </motion.div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden border-t border-zinc-800/50 px-6 py-24">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-600/10 via-purple-600/10 to-pink-600/10" />
        <div className="relative z-10 mx-auto max-w-3xl text-center">
          <AnimatedSection>
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Ready to simplify your links?
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-zinc-400">
              Join hundreds of teams already using LinkForge. Start free, no credit card required.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link href="/register" className="flex h-12 w-44 items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 text-sm font-medium text-white hover:bg-blue-700 transition-colors">
                Get Started Free <ArrowRight className="size-4" />
              </Link>
              <Link href="https://github.com/BORUTOUZUMAKI07/url-shortner" target="_blank" className="flex h-12 w-44 items-center justify-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition-colors">
                <Code className="size-4" /> View on GitHub
              </Link>
            </div>
          </AnimatedSection>
        </div>
      </section>

      <footer className="border-t border-zinc-800/50 px-6 py-12">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <span className="text-lg font-bold text-white">LinkForge</span>
              <p className="mt-2 text-sm text-zinc-500">Enterprise-grade URL shortener with analytics and team collaboration.</p>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold text-white">Product</h4>
              <ul className="space-y-2 text-sm text-zinc-500">
                <li><Link href="#features" className="hover:text-white transition-colors">Features</Link></li>
                <li><Link href="/login" className="hover:text-white transition-colors">Sign In</Link></li>
                <li><Link href="/register" className="hover:text-white transition-colors">Get Started</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold text-white">Developers</h4>
              <ul className="space-y-2 text-sm text-zinc-500">
                <li><Link href="/login" className="hover:text-white transition-colors">API Keys</Link></li>
                <li><Link href="/login" className="hover:text-white transition-colors">Dashboard</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="mb-3 text-sm font-semibold text-white">Resources</h4>
              <ul className="space-y-2 text-sm text-zinc-500">
                <li><a href="https://github.com/BORUTOUZUMAKI07/url-shortner" target="_blank" className="hover:text-white transition-colors">GitHub</a></li>
                <li><span className="cursor-default">Documentation</span></li>
              </ul>
            </div>
          </div>
          <div className="mt-12 border-t border-zinc-800 pt-6 text-center text-sm text-zinc-600">
            LinkForge — Built with Next.js, FastAPI, and love.
          </div>
        </div>
      </footer>
    </div>
  )
}
