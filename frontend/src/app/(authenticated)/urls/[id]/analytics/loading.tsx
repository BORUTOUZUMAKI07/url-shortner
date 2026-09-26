import { StatsCardSkeleton } from "@/components/ui/skeleton"

export default function Loading() {
  return (
    <div className="p-6">
      <div className="mb-6 h-8 w-48 animate-pulse rounded bg-stone-200/50" />
      <StatsCardSkeleton />
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="h-72 animate-pulse rounded-xl bg-stone-200/50" />
        <div className="h-72 animate-pulse rounded-xl bg-stone-200/50" />
      </div>
    </div>
  )
}
