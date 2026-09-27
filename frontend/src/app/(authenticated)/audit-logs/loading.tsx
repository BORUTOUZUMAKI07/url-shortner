import { TableSkeleton } from "@/components/ui/skeleton"

export default function Loading() {
  return (
    <div className="p-6">
      <div className="mb-6 h-8 w-40 animate-pulse rounded bg-stone-200/50" />
      <TableSkeleton rows={5} />
    </div>
  )
}
