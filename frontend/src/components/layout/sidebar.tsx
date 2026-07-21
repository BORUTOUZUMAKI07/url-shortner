"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard, Link2, Plus, FolderOpen, Tags,
  Key, Webhook, Upload, Settings, Users, LogOut,
  Heart, History, Crown, Shield, Menu, X,
} from "lucide-react"
import { useAuthStore } from "@/store/auth"
import { auth } from "@/lib/api"

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
  const pathname = usePathname()
  const { user, logout: storeLogout } = useAuthStore()

  const allSections = user?.is_superadmin
    ? [...sections.slice(0, -1), { label: sections[2].label, items: [...sections[2].items, { href: "/admin", label: "Admin", icon: Shield }] }]
    : sections

  const content = (
    <>
      <div className="flex h-14 items-center justify-between border-b border-zinc-800/50 px-4">
        <Link href="/dashboard">
          <span className="text-lg font-bold text-white">
            LinkForge
          </span>
        </Link>
        <button onClick={() => setOpen(false)} className="block md:hidden p-1 text-zinc-400 hover:text-white">
          <X className="size-5" />
        </button>
      </div>
      <nav className="flex-1 space-y-4 overflow-y-auto p-3 scrollbar-thin">
        {allSections.map((section) => (
          <div key={section.label}>
            <div className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              {section.label}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon
                const isActive = pathname === item.href || pathname.startsWith(item.href + "/")
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
                      isActive
                        ? "bg-blue-500/10 text-blue-400"
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50",
                    )}
                  >
                    <div className={cn("flex size-5 items-center justify-center", isActive ? "text-blue-400" : "text-zinc-500 group-hover:text-zinc-300")}>
                      <Icon className="size-4" />
                    </div>
                    {item.label}
                    {isActive && <div className="ml-auto size-1.5 rounded-full bg-blue-500" />}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
      {user && (
        <div className="border-t border-zinc-800/50 p-3">
          <div className="mb-2 flex items-center gap-3 rounded-lg px-3 py-2">
            <div className="flex size-8 items-center justify-center rounded-full bg-zinc-800 text-xs font-medium text-zinc-400">
              {user.email.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user.email.split("@")[0]}</p>
              <p className="truncate text-xs text-zinc-500">{user.email}</p>
            </div>
          </div>
          <button
            onClick={() => { auth.logout().catch(() => {}); storeLogout(); window.location.href = "/login" }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-zinc-400 transition-colors hover:text-red-400 hover:bg-red-500/10"
          >
            <LogOut className="size-4" />
            Logout
          </button>
        </div>
      )}
    </>
  )

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed left-3 top-3 z-40 block md:hidden rounded-lg bg-zinc-900 p-2 shadow-lg border border-zinc-800"
        aria-label="Open menu"
      >
        <Menu className="size-5 text-zinc-400" />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      <aside
        className={cn(
          "flex h-screen w-60 flex-col border-r border-zinc-800/50 bg-zinc-950 fixed md:sticky top-0 left-0 z-40 transition-transform duration-200 md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {content}
      </aside>
    </>
  )
}
