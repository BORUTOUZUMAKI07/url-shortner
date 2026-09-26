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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-stone-50 px-4">
      <BackgroundBeams className="opacity-40" />
      <div className="relative z-10 w-full max-w-sm space-y-4 rounded-xl border border-stone-200 bg-white/80 p-8 shadow-lg backdrop-blur-sm">
        <h1 className="text-center text-2xl font-heading font-semibold tracking-tight text-stone-900">Forgot Password</h1>
        {sent ? (
          <p className="text-center text-sm text-green-600">If that email exists, a reset link has been sent.</p>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {error && <p className="text-center text-sm text-red-600">{error}</p>}
            <div className="space-y-1">
              <Input
                type="email"
                placeholder="Your email"
                {...register("email")}
                className="border-stone-300 bg-stone-200 text-stone-900 placeholder-stone-500"
              />
              {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
            </div>
            <Button type="submit" disabled={isSubmitting} className="w-full bg-emerald-600 text-white hover:bg-emerald-700">
              {isSubmitting ? "Sending..." : "Send Reset Link"}
            </Button>
          </form>
        )}
        <p className="text-center text-sm text-stone-500">
          <Link href="/login" className="text-emerald-600 hover:underline">Back to Sign In</Link>
        </p>
      </div>
    </div>
  )
}
