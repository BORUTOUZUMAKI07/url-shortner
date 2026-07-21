"use client"

import { useState } from "react"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { BackgroundBeams } from "@/components/ui/background-beams"
import { auth, getErrorMessage } from "@/lib/api"

const formSchema = z.object({
  email: z.string().email("Please enter a valid email address."),
})

type FormData = z.infer<typeof formSchema>

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false)
  const [error, setError] = useState("")

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(formSchema),
  })

  async function onSubmit(data: FormData) {
    setError("")
    try {
      await auth.forgotPassword(data.email)
      setSent(true)
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to send reset link"))
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-950 px-4">
      <BackgroundBeams className="opacity-40" />
      <div className="relative z-10 w-full max-w-sm space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/80 p-8 shadow-2xl backdrop-blur-sm">
        <h1 className="text-center text-2xl font-bold tracking-tight text-white">Forgot Password</h1>
        {sent ? (
          <p className="text-center text-sm text-green-400">If that email exists, a reset link has been sent.</p>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {error && <p className="text-center text-sm text-red-400">{error}</p>}
            <div className="space-y-1">
              <Input
                type="email"
                placeholder="Your email"
                {...register("email")}
                className="border-zinc-700 bg-zinc-800 text-white placeholder-zinc-400"
              />
              {errors.email && <p className="text-xs text-red-400">{errors.email.message}</p>}
            </div>
            <Button type="submit" disabled={isSubmitting} className="w-full bg-blue-600 text-white hover:bg-blue-700">
              {isSubmitting ? "Sending..." : "Send Reset Link"}
            </Button>
          </form>
        )}
        <p className="text-center text-sm text-zinc-400">
          <Link href="/login" className="text-blue-400 hover:underline">Back to Sign In</Link>
        </p>
      </div>
    </div>
  )
}
