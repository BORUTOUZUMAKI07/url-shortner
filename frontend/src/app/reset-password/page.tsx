"use client"

import { Suspense, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { BackgroundBeams } from "@/components/ui/background-beams"
import { auth, getErrorMessage } from "@/lib/api"

const formSchema = z.object({
  password: z.string().min(8, "Password must be at least 8 characters."),
})

type FormData = z.infer<typeof formSchema>

function ResetForm() {
  const searchParams = useSearchParams()
  const [done, setDone] = useState(false)
  const [error, setError] = useState("")

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(formSchema),
  })

  async function onSubmit(data: FormData) {
    setError("")
    const token = searchParams.get("token")
    if (!token) { setError("Missing reset token"); return }
    try {
      await auth.resetPassword(token, data.password)
      setDone(true)
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to reset password"))
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-stone-50 px-4">
      <BackgroundBeams className="opacity-40" />
      <div className="relative z-10 w-full max-w-sm space-y-4 rounded-xl border border-stone-200 bg-white/80 p-8 shadow-lg backdrop-blur-sm">
        <h1 className="text-center text-2xl font-heading font-semibold tracking-tight text-stone-900">Reset Password</h1>
        {done ? (
          <div className="space-y-4 text-center">
            <p className="text-sm text-green-600">Password reset successfully!</p>
            <Link href="/login"><Button className="bg-emerald-600 text-white hover:bg-emerald-700">Sign In</Button></Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {error && <p className="text-center text-sm text-red-600">{error}</p>}
            <div className="space-y-1">
              <Input
                type="password"
                placeholder="New password"
                {...register("password")}
                className="border-stone-300 bg-stone-200 text-stone-900 placeholder-stone-500"
              />
              {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
            </div>
            <Button type="submit" disabled={isSubmitting} className="w-full bg-emerald-600 text-white hover:bg-emerald-700">
              {isSubmitting ? "Resetting..." : "Reset Password"}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-stone-50 text-stone-900">Loading...</div>}><ResetForm /></Suspense>
}
