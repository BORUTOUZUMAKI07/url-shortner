// A single accent everywhere reads as flat. Each nav section / content type
// gets its own hue instead, so the dashboard has visual rhythm at a glance —
// while URLs (the core object of the product) keeps the primary brand color.
//
// NOTE for Tailwind's JIT scanner: every class below must appear as a full,
// static string (not built with template interpolation) so it gets picked
// up at build time. Keep entries literal.
export const CATEGORY_COLORS = {
  dashboard: { chip: "bg-emerald-500/10 text-emerald-600", active: "bg-emerald-500/10 text-emerald-600", dot: "bg-emerald-500" },
  urls: { chip: "bg-emerald-500/10 text-emerald-600", active: "bg-emerald-500/10 text-emerald-600", dot: "bg-emerald-500" },
  favorites: { chip: "bg-rose-500/10 text-rose-600", active: "bg-rose-500/10 text-rose-600", dot: "bg-rose-500" },
  workspaces: { chip: "bg-amber-500/10 text-amber-600", active: "bg-amber-500/10 text-amber-600", dot: "bg-amber-500" },
  folders: { chip: "bg-sky-500/10 text-sky-600", active: "bg-sky-500/10 text-sky-600", dot: "bg-sky-500" },
  tags: { chip: "bg-violet-500/10 text-violet-600", active: "bg-violet-500/10 text-violet-600", dot: "bg-violet-500" },
  apiKeys: { chip: "bg-indigo-500/10 text-indigo-600", active: "bg-indigo-500/10 text-indigo-600", dot: "bg-indigo-500" },
  webhooks: { chip: "bg-cyan-500/10 text-cyan-600", active: "bg-cyan-500/10 text-cyan-600", dot: "bg-cyan-500" },
  bulk: { chip: "bg-teal-500/10 text-teal-600", active: "bg-teal-500/10 text-teal-600", dot: "bg-teal-500" },
  auditLogs: { chip: "bg-slate-500/10 text-slate-600", active: "bg-slate-500/10 text-slate-600", dot: "bg-slate-500" },
  billing: { chip: "bg-amber-500/10 text-amber-600", active: "bg-amber-500/10 text-amber-600", dot: "bg-amber-500" },
  profile: { chip: "bg-slate-500/10 text-slate-600", active: "bg-slate-500/10 text-slate-600", dot: "bg-slate-500" },
  admin: { chip: "bg-fuchsia-500/10 text-fuchsia-600", active: "bg-fuchsia-500/10 text-fuchsia-600", dot: "bg-fuchsia-500" },
  analytics: { chip: "bg-rose-500/10 text-rose-600", active: "bg-rose-500/10 text-rose-600", dot: "bg-rose-500" },
} as const

export type CategoryKey = keyof typeof CATEGORY_COLORS

export function categoryForPath(pathname: string): CategoryKey {
  if (pathname === "/dashboard") return "dashboard"
  if (pathname.startsWith("/urls/") && pathname.endsWith("/analytics")) return "analytics"
  if (pathname.startsWith("/urls")) return "urls"
  if (pathname.startsWith("/favorites")) return "favorites"
  if (pathname.startsWith("/workspaces")) return "workspaces"
  if (pathname.startsWith("/folders")) return "folders"
  if (pathname.startsWith("/tags")) return "tags"
  if (pathname.startsWith("/api-keys")) return "apiKeys"
  if (pathname.startsWith("/webhooks")) return "webhooks"
  if (pathname.startsWith("/bulk")) return "bulk"
  if (pathname.startsWith("/audit-logs")) return "auditLogs"
  if (pathname.startsWith("/billing")) return "billing"
  if (pathname.startsWith("/profile")) return "profile"
  if (pathname.startsWith("/admin")) return "admin"
  return "urls"
}
