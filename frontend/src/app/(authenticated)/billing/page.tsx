"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { billingApi, getErrorMessage } from "@/lib/api"
import { useMe } from "@/queries"
import { Crown, Check, ArrowLeft, Loader2 } from "lucide-react"

const PLANS = [
  { name: "Free", backend: "free", price: "$0", limits: "100 URLs, basic analytics" },
  { name: "Pro", backend: "premium", price: "$9", limits: "10,000 URLs, advanced analytics, priority support" },
  { name: "Enterprise", backend: "enterprise", price: "$49", limits: "Unlimited URLs, all features, dedicated support" },
]

export default function BillingPage() {
  const router = useRouter()
  // Shared ["me"] cache — the single source of truth. The old private
  // ["authMe"] query fetched me() on top of the layout's fetch; it's gone.
  const { data: user, isPending: authLoading, isError: meError } = useMe()
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const queryClient = useQueryClient()

  // The old auth-gating query redirected on any me() failure; a dead session
  // self-redirects via the api layer's global 401 handling, so this only needs
  // to cover the non-401 case.
  useEffect(() => {
    if (meError) router.push("/login?expired=1")
  }, [meError, router])

  const upgradeMutation = useMutation({
    mutationFn: (plan: string) => billingApi.upgrade(plan),
    onMutate: () => { setError(""); setSuccess("") },
    onSuccess: (res) => {
      // Optimistic write to the shared ["me"] cache so the new plan renders
      // immediately, then invalidate so the refetch confirms the server truth.
      // (Every reader of useMe sees this — there is no second copy to update.)
      queryClient.setQueryData(["me"], { ...user!, plan: res.plan })
      setSuccess(res.detail)
      queryClient.invalidateQueries({ queryKey: ["me"] })
    },
    onError: (e: unknown) => {
      setError(getErrorMessage(e, "Failed to upgrade"))
    }
  })

  async function handleUpgrade(plan: string) {
    upgradeMutation.mutate(plan)
  }

  if (authLoading || !user) return null

  return (
    <div className="p-6">
      <button onClick={() => router.back()} className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back
      </button>
      <div className="mb-6 flex items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600">
          <Crown className="size-4.5" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-semibold tracking-tight">Billing & Plans</h1>
          <p className="text-sm text-muted-foreground">Your current plan: <Badge variant="success" className="capitalize">{user.plan}</Badge></p>
        </div>
      </div>

      {error && <div className="mb-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-600">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-500/10 px-4 py-2 text-sm text-green-600">{success}</div>}

      <div className="grid gap-6 sm:grid-cols-2 md:grid-cols-3">
        {PLANS.map((plan) => {
          const isCurrent = user.plan === plan.backend
          const isLoading = upgradeMutation.isPending && upgradeMutation.variables === plan.backend
          return (
            <Card key={plan.name} className={`transition-all ${isCurrent ? "ring-2 ring-emerald-500 shadow-lg" : "hover:ring-1 hover:ring-muted"}`}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{plan.name}</CardTitle>
                  {isCurrent && <Badge variant="success">Current</Badge>}
                </div>
                <p className="text-3xl font-bold">{plan.price}<span className="text-sm font-normal text-muted-foreground">/mo</span></p>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">{plan.limits}</p>
                <ul className="space-y-2">
                  {["URL shortening", "Click analytics", "Custom aliases", "API access"].map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm">
                      <Check className="size-4 text-green-600" /> {f}
                    </li>
                  ))}
                </ul>
                {!isCurrent && (
                  <Button className="w-full" variant={plan.name === "Enterprise" ? "outline" : "default"} onClick={() => handleUpgrade(plan.backend)} disabled={isLoading}>
                    {isLoading ? <Loader2 className="mr-1 size-4 animate-spin" /> : <Crown className="mr-1 size-4" />}
                    Upgrade
                  </Button>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
