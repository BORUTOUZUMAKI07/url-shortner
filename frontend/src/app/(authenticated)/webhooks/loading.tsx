import { CardSkeleton } from "@/components/ui/skeleton"

export default function Loading() {
  return (
    <div className="p-6">
      <div className="mb-6 h-8 w-32 animate-pulse rounded bg-stone-200/50" />
      <CardSkeleton count={2} />
    </div>
  )
}
