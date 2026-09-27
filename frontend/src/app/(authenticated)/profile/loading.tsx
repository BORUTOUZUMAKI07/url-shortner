import { CardSkeleton } from "@/components/ui/skeleton"

export default function Loading() {
  return (
    <div className="p-6">
      <div className="mb-6 h-8 w-28 animate-pulse rounded bg-stone-200/50" />
      <CardSkeleton count={1} />
    </div>
  )
}
