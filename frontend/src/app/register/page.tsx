"use client"

import { Suspense, useState } from "react"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { Button } from "@/components/ui/button"
import { BackgroundBeams } from "@/components/ui/background-beams"
import { auth, getErrorMessage } from "@/lib/api"
import { registerSchema, type RegisterFormData } from "@/lib/schemas"
import { motion } from "motion/react"
import { CheckCircle } from "lucide-react"

function RegisterForm() {
  const [success, setSuccess] = useState(false)

  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  async function onSubmit(data: RegisterFormData) {
    try {
      await auth.register(data.email, data.password)
      setSuccess(true)
    } catch (err: unknown) {
      setError("root", { message: getErrorMessage(err, "Registration failed") })
    }
  }

  if (success) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-950 px-4">
        <div className="bg-grid absolute inset-0 opacity-30" />
        <BackgroundBeams className="opacity-30" />
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="relative z-10 w-full max-w-sm glass rounded-xl p-8 shadow-2xl text-center">
          <CheckCircle className="mx-auto mb-4 size-12 text-green-400" />
          <h1 className="text-2xl font-bold tracking-tight text-white mb-2">Account Created</h1>
          <p className="text-zinc-400 mb-6">Check your email to verify your account, then sign in.</p>
          <Link href="/login" className="inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors">Sign In</Link>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-950 px-4">
      <div className="bg-grid absolute inset-0 opacity-30" />
      <BackgroundBeams className="opacity-30" />
      <div className="absolute right-1/4 top-1/4 h-72 w-72 rounded-full bg-purple-500/10 blur-[96px]" />

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="relative z-10 w-full max-w-sm">
        <div className="mb-6 text-center">
          <Link href="/" className="inline-block text-2xl font-bold text-white hover:opacity-80 transition-opacity">LinkForge</Link>
          <p className="mt-1 text-sm text-zinc-500">Create your free account</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="glass mb-4 space-y-4 rounded-xl p-8 shadow-2xl">
          <h1 className="text-center text-2xl font-bold tracking-tight text-white">Create Account</h1>

          {errors.root && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
              <p className="text-center text-sm text-red-400">{errors.root.message}</p>
            </div>
          )}

          <div>
            <input type="email" placeholder="Email" {...register("email")}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2.5 text-sm text-white placeholder-zinc-500 transition-colors focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
          </div>

          <div>
            <input type="password" placeholder="Password" {...register("password")}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2.5 text-sm text-white placeholder-zinc-500 transition-colors focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>}
          </div>

          <div>
            <input type="password" placeholder="Confirm Password" {...register("confirmPassword")}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2.5 text-sm text-white placeholder-zinc-500 transition-colors focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            {errors.confirmPassword && <p className="mt-1 text-xs text-red-400">{errors.confirmPassword.message}</p>}
          </div>

          <Button type="submit" className="w-full bg-blue-600 text-white hover:bg-blue-700" disabled={isSubmitting}>
            {isSubmitting ? "Creating account..." : "Create Account"}
          </Button>

          <p className="text-center text-sm text-zinc-400">
            Already have an account?{" "}
            <Link href="/login" className="text-blue-400 hover:underline">Sign In</Link>
          </p>
        </form>

        <p className="text-center text-xs text-zinc-600">
          By creating an account, you agree to our{" "}
          <span className="cursor-default hover:text-zinc-400 transition-colors">Terms of Service</span>{" "}
          and{" "}
          <span className="cursor-default hover:text-zinc-400 transition-colors">Privacy Policy</span>
        </p>
      </motion.div>
    </div>
  )
}

export default function RegisterPage() {
  return <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-zinc-950"><div className="size-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" /></div>}><RegisterForm /></Suspense>
}
