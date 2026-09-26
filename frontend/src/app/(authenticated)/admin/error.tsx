"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => { console.error(error) }, [error])

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6">
      <div className="text-center">
        <h2 className="mb-2 text-lg font-semibold text-red-600">Could not load admin panel</h2>
        <p className="mb-6 text-sm text-muted-foreground">{error.message}</p>
        <Button onClick={reset} variant="outline">Try Again</Button>
      </div>
    </div>
  )
}
