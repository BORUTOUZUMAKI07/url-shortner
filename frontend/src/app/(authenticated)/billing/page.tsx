"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { auth, billingApi, getErrorMessage } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Crown, Check, ArrowLeft, Loader2 } from "lucide-react"

const PLANS = [
  { name: "Free", backend: "free", price: "$0", limits: "100 URLs, basic analytics" },
  { name: "Pro", backend: "premium", price: "$9", limits: "10,000 URLs, advanced analytics, priority support" },
  { name: "Enterprise", backend: "enterprise", price: "$49", limits: "Unlimited URLs, all features, dedicated support" },
]

export default function BillingPage() {
  const router = useRouter()
  const { user, setUser } = useAuthStore()
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const queryClient = useQueryClient()

  const { isLoading: authLoading } = useQuery({
    queryKey: ["authMe"],
    queryFn: async () => {
      try {
        const user = await auth.me()
        setUser(user)
        return user
      } catch (err) {
        router.push("/login")
        throw err
      }
    },
    retry: false
  })

  const upgradeMutation = useMutation({
    mutationFn: (plan: string) => billingApi.upgrade(plan),
    onMutate: () => { setError(""); setSuccess("") },
    onSuccess: (res) => {
      setUser({ ...user!, plan: res.plan })
      setSuccess(res.detail)
      queryClient.invalidateQueries({ queryKey: ["authMe"] })
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
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Billing & Plans</h1>
        <p className="text-sm text-muted-foreground">Your current plan: <Badge variant="success" className="capitalize">{user.plan}</Badge></p>
      </div>

      {error && <div className="mb-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-500/10 px-4 py-2 text-sm text-green-400">{success}</div>}

      <div className="grid gap-6 sm:grid-cols-2 md:grid-cols-3">
        {PLANS.map((plan) => {
          const isCurrent = user.plan === plan.backend
          const isLoading = upgradeMutation.isPending && upgradeMutation.variables === plan.backend
          return (
            <Card key={plan.name} className={`transition-all ${isCurrent ? "ring-2 ring-blue-500" : "hover:ring-1 hover:ring-muted"}`}>
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
                      <Check className="size-4 text-green-400" /> {f}
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
