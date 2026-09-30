"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { CATEGORY_COLORS, categoryForPath } from "@/lib/category-colors"
import {
  LayoutDashboard, Link2, Plus, FolderOpen, Tags,
  Key, Webhook, Upload, Settings, Users, LogOut,
  Heart, History, Crown, Shield, Menu, X,
} from "lucide-react"
import { toast } from "sonner"
import { useQueryClient } from "@tanstack/react-query"
import { adminApi, auth, getErrorMessage } from "@/lib/api"
import { useMe } from "@/queries"

interface NavItem {
  href: string
  label: string
  icon: React.ElementType
}

const sections: { label: string; items: NavItem[] }[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/urls", label: "All URLs", icon: Link2 },
      { href: "/urls/new", label: "Create URL", icon: Plus },
      { href: "/favorites", label: "Favorites", icon: Heart },
    ],
  },
  {
    label: "Management",
    items: [
      { href: "/workspaces", label: "Workspaces", icon: Users },
      { href: "/folders", label: "Folders", icon: FolderOpen },
      { href: "/tags", label: "Tags", icon: Tags },
      { href: "/api-keys", label: "API Keys", icon: Key },
      { href: "/webhooks", label: "Webhooks", icon: Webhook },
      { href: "/bulk", label: "Bulk Ops", icon: Upload },
    ],
  },
  {
    label: "Settings",
    items: [
      { href: "/audit-logs", label: "Audit Logs", icon: History },
      { href: "/billing", label: "Billing", icon: Crown },
      { href: "/profile", label: "Profile", icon: Settings },
    ],
  },
]

export function Sidebar() {
  const [open, setOpen] = useState(false)
  const [seedingAdmin, setSeedingAdmin] = useState(false)
  const pathname = usePathname()
  const queryClient = useQueryClient()
  // The shared ["me"] cache is the single source of truth for the current
  // user; mounting this useMe() on every authenticated page also warms the
  // cache for the page below (the layout renders this before the page).
  const { data: user } = useMe()

  async function handleSeedAdmin() {
    setSeedingAdmin(true)
    try {
      await adminApi.seed()
      // The account just became a superadmin. Read it back from the server
      // into the shared ["me"] cache rather than hand-editing a copy.
      await queryClient.invalidateQueries({ queryKey: ["me"] })
      toast.success("Admin panel enabled")
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, "Could not enable admin panel"))
    } finally {
      setSeedingAdmin(false)
    }
  }

  async function handleLogout() {
    // Await the server call so the httpOnly cookies are actually cleared BEFORE
    // navigating — otherwise the proxy middleware sees a still-valid cookie on
    // /login and bounces back to /dashboard (infinite reload loop). Fire-and-
    // forget navigation previously made this a race the loop always won.
    try {
      await auth.logout()
    } catch {
      // The cookies were NOT cleared. `auth.logout` throws on any non-2xx, not
      // just an unreachable backend, and /auth/logout sits behind the global
      // per-IP rate limiter — so a 429 or a 5xx landed here with the access
      // token still valid.
      //
      // The old code swallowed that and navigated to a bare /login, which is
      // exactly the bounce described above: the URL flickered to /login and the
      // user landed back on the signed-in dashboard, with no error and no
      // explanation. `expired=1` is the flag proxy.ts looks for to suppress that
      // bounce, so the sign-in form is reachable either way.
      toast.error("Could not reach the server to end your session. Sign-in will be required again.")
      queryClient.setQueryData(["me"], null)
      window.location.href = "/login?expired=1"
      return
    }
    queryClient.setQueryData(["me"], null)
    window.location.href = "/login"
  }

  const allSections = user?.is_superadmin
    ? [...sections.slice(0, -1), { label: sections[2].label, items: [...sections[2].items, { href: "/admin", label: "Admin", icon: Shield }] }]
    : sections

  const content = (
    <>
      <div className="flex h-14 items-center justify-between border-b border-stone-200/50 px-4">
        <Link href="/dashboard">
          <span className="text-lg font-heading font-semibold text-stone-900">
            LinkForge
          </span>
        </Link>
        <button onClick={() => setOpen(false)} className="block md:hidden p-1 text-stone-500 hover:text-stone-900">
          <X className="size-5" />
        </button>
      </div>
      <nav className="flex-1 space-y-4 overflow-y-auto p-3 scrollbar-thin">
        {allSections.map((section) => (
          <div key={section.label}>
            <div className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-stone-500">
              {section.label}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon
                const isActive = pathname === item.href || pathname.startsWith(item.href + "/")
                const colors = CATEGORY_COLORS[categoryForPath(item.href)]
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
                      isActive
                        ? colors.active
                        : "text-stone-500 hover:text-stone-700 hover:bg-stone-200/50",
                    )}
                  >
                    <div className={cn("flex size-5 items-center justify-center", isActive ? colors.chip.split(" ")[1] : "text-stone-500 group-hover:text-stone-600")}>
                      <Icon className="size-4" />
                    </div>
                    {item.label}
                    {isActive && <div className={cn("ml-auto size-1.5 rounded-full", colors.dot)} />}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-stone-200/50 p-3">
        {user && (
          <>
            <div className="mb-2 flex items-center gap-3 rounded-lg px-3 py-2">
              <div className="flex size-8 items-center justify-center rounded-full bg-stone-200 text-xs font-medium text-stone-500">
                {user.email.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-stone-900">{user.email.split("@")[0]}</p>
                <p className="truncate text-xs text-stone-500">{user.email}</p>
              </div>
            </div>
            {!user.is_superadmin && (
              <button
                onClick={handleSeedAdmin}
                disabled={seedingAdmin}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-stone-500 transition-colors hover:text-amber-600 hover:bg-amber-500/10 disabled:opacity-60"
              >
                <Crown className="size-4" />
                {seedingAdmin ? "Enabling..." : "Enable Admin Panel"}
              </button>
            )}
          </>
        )}
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-stone-500 transition-colors hover:text-red-600 hover:bg-red-500/10"
        >
          <LogOut className="size-4" />
          Logout
        </button>
      </div>
    </>
  )

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed left-3 top-3 z-40 block md:hidden rounded-lg bg-white p-2 shadow-lg border border-stone-200"
        aria-label="Open menu"
      >
        <Menu className="size-5 text-stone-500" />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      <aside
        className={cn(
          "flex h-screen w-60 flex-col border-r border-stone-200/50 bg-stone-50 fixed md:sticky top-0 left-0 z-40 transition-transform duration-200 md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {content}
      </aside>
    </>
  )
}
