import { TableSkeleton } from "@/components/ui/skeleton"

export default function Loading() {
  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="h-8 w-32 animate-pulse rounded bg-stone-200/50" />
        <div className="h-10 w-28 animate-pulse rounded-lg bg-stone-200/50" />
      </div>
      <div className="mb-4 flex gap-2">
        <div className="h-10 flex-1 animate-pulse rounded-lg bg-stone-200/50" />
        <div className="h-10 w-36 animate-pulse rounded-lg bg-stone-200/50" />
        <div className="h-10 w-36 animate-pulse rounded-lg bg-stone-200/50" />
      </div>
      <TableSkeleton />
    </div>
  )
}
