"use client"

import { Suspense, useEffect, useRef } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { Button } from "@/components/ui/button"
import { auth, getErrorMessage } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { setTokenCookie, setRefreshTokenCookie } from "@/lib/token-cookie"
import { loginSchema, type LoginFormData } from "@/lib/schemas"
import { motion } from "motion/react"

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((s) => s.setUser)

  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  function redirectAfterLogin() {
    const inviteToken = sessionStorage.getItem("invite_token")
    if (inviteToken) {
      sessionStorage.removeItem("invite_token")
      router.push(`/workspaces?invite_token=${inviteToken}`)
    } else {
      router.push("/dashboard")
    }
  }

  const processedRef = useRef(false)

  useEffect(() => {
    if (processedRef.current) return
    const accessToken = searchParams.get("access_token")
    const refreshToken = searchParams.get("refresh_token")
    if (accessToken) {
      processedRef.current = true
      localStorage.setItem("access_token", accessToken)
      setTokenCookie(accessToken)
      if (refreshToken) {
        localStorage.setItem("refresh_token", refreshToken)
        setRefreshTokenCookie(refreshToken)
      }
      auth.me().then(setUser).then(redirectAfterLogin)
      return
    }
    const inviteToken = searchParams.get("invite_token")
    if (inviteToken) {
      sessionStorage.setItem("invite_token", inviteToken)
    }
  }, [searchParams])

  async function onSubmit(data: LoginFormData) {
    try {
      const tokens = await auth.login(data.email, data.password)
      localStorage.setItem("access_token", tokens.access_token)
      setTokenCookie(tokens.access_token)
      if (tokens.refresh_token) {
        localStorage.setItem("refresh_token", tokens.refresh_token)
        setRefreshTokenCookie(tokens.refresh_token)
      }
      const user = await auth.me()
      setUser(user)
      redirectAfterLogin()
    } catch (err: unknown) {
      setError("root", { message: getErrorMessage(err, "Login failed") })
    }
  }

  async function handleOAuth(provider: string) {
    try {
      const { authorization_url } = await auth.oauth(provider)
      window.location.href = authorization_url
    } catch (err: unknown) {
      setError("root", { message: getErrorMessage(err) })
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-4">

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="relative z-10 w-full max-w-sm">
        <div className="mb-6 text-center">
          <Link href="/" className="inline-block text-2xl font-bold text-white hover:opacity-80 transition-opacity">LinkForge</Link>
          <p className="mt-1 text-sm text-zinc-400">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="glass mb-4 space-y-4 rounded-xl p-8 shadow-2xl">
          <h1 className="text-center text-2xl font-bold tracking-tight text-white">Sign In</h1>

          {errors.root && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
              <p className="text-center text-sm text-red-400">{errors.root.message}</p>
            </div>
          )}

          <div>
            <input type="email" placeholder="Email" {...register("email")}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2.5 text-sm text-white placeholder-zinc-400 transition-colors focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
          </div>

          <div>
            <input type="password" placeholder="Password" {...register("password")}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2.5 text-sm text-white placeholder-zinc-400 transition-colors focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>}
          </div>

          <Button type="submit" className="w-full bg-blue-600 text-white hover:bg-blue-700" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Sign In"}
          </Button>

          <div className="flex items-center justify-between text-sm">
            <Link href="/forgot-password" className="text-blue-400 hover:underline">Forgot password?</Link>
            <Link href="/register" className="text-zinc-400 hover:text-white transition-colors">No account?</Link>
          </div>
        </form>

        <div className="glass rounded-xl p-8 shadow-2xl">
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-zinc-800" /></div>
            <div className="relative flex justify-center text-xs"><span className="bg-zinc-900 px-2 text-zinc-400">Or continue with</span></div>
          </div>
          <div className="grid gap-3">
            <button onClick={() => handleOAuth("google")} className="group flex items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-white px-4 py-2.5 text-sm font-medium text-zinc-900 transition-all hover:bg-zinc-100 hover:shadow-lg">
              <svg className="size-5" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              Google
            </button>
            <button onClick={() => handleOAuth("github")} className="group flex items-center justify-center gap-2 rounded-lg border border-zinc-600 bg-zinc-800 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-zinc-700 hover:shadow-lg">
              <svg className="size-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
              GitHub
            </button>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-zinc-500">
          By continuing, you agree to our{" "}
          <span className="cursor-default hover:text-zinc-300 transition-colors">Terms of Service</span>{" "}
          and{" "}
          <span className="cursor-default hover:text-zinc-300 transition-colors">Privacy Policy</span>
        </p>
      </motion.div>
    </div>
  )
}

export default function LoginPage() {
  return <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-zinc-950"><div className="size-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" /></div>}><LoginForm /></Suspense>
}
