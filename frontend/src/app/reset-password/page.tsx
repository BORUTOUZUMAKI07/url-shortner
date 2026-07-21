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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-950 px-4">
      <BackgroundBeams className="opacity-40" />
      <div className="relative z-10 w-full max-w-sm space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/80 p-8 shadow-2xl backdrop-blur-sm">
        <h1 className="text-center text-2xl font-bold tracking-tight text-white">Reset Password</h1>
        {done ? (
          <div className="space-y-4 text-center">
            <p className="text-sm text-green-400">Password reset successfully!</p>
            <Link href="/login"><Button className="bg-blue-600 text-white hover:bg-blue-700">Sign In</Button></Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {error && <p className="text-center text-sm text-red-400">{error}</p>}
            <div className="space-y-1">
              <Input
                type="password"
                placeholder="New password"
                {...register("password")}
                className="border-zinc-700 bg-zinc-800 text-white placeholder-zinc-400"
              />
              {errors.password && <p className="text-xs text-red-400">{errors.password.message}</p>}
            </div>
            <Button type="submit" disabled={isSubmitting} className="w-full bg-blue-600 text-white hover:bg-blue-700">
              {isSubmitting ? "Resetting..." : "Reset Password"}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-zinc-950 text-white">Loading...</div>}><ResetForm /></Suspense>
}
