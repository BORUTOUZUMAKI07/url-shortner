"use client"

import Image from "next/image"
import { useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { auth, getErrorMessage, profileApi } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { User, Mail, Shield, Crown, CalendarDays, CheckCircle, XCircle, ExternalLink, Lock, Camera, Loader2, AlertCircle, Check } from "lucide-react"

const passwordSchema = z.object({
  pwCurrent: z.string().min(1, "Current password is required"),
  pwNew: z.string().min(8, "New password must be at least 8 characters"),
})

const emailSchema = z.object({
  newEmail: z.string().email("Invalid email address"),
  emailPw: z.string().min(1, "Password is required to confirm"),
})

type PasswordFormData = z.infer<typeof passwordSchema>
type EmailFormData = z.infer<typeof emailSchema>

export default function ProfilePage() {
  const router = useRouter()
  const { user, setUser } = useAuthStore()
  const fileRef = useRef<HTMLInputElement>(null)

  // Password form
  const [pwError, setPwError] = useState("")
  const [pwSuccess, setPwSuccess] = useState("")
  const pwForm = useForm<PasswordFormData>({ resolver: zodResolver(passwordSchema) })

  // Email form
  const [emailError, setEmailError] = useState("")
  const [emailSuccess, setEmailSuccess] = useState("")
  const emailForm = useForm<EmailFormData>({ resolver: zodResolver(emailSchema) })

  // Avatar
  const [avatarLoading, setAvatarLoading] = useState(false)
  const [avatarError, setAvatarError] = useState("")

  useQuery({
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

  async function onPasswordSubmit(data: PasswordFormData) {
    setPwError(""); setPwSuccess("")
    try {
      const res = await profileApi.changePassword(data.pwCurrent, data.pwNew)
      setPwSuccess(res.detail)
      pwForm.reset()
    } catch (e: unknown) { setPwError(getErrorMessage(e, "Failed to update password")) }
  }

  async function onEmailSubmit(data: EmailFormData) {
    setEmailError(""); setEmailSuccess("")
    try {
      const res = await profileApi.changeEmail(data.newEmail, data.emailPw)
      setEmailSuccess(res.detail)
      setUser({ ...user!, email: data.newEmail, is_verified: false })
      emailForm.reset()
    } catch (e: unknown) { setEmailError(getErrorMessage(e, "Failed to update email")) }
  }

  async function handleAvatarUpload(file: File) {
    if (!file) return; setAvatarLoading(true); setAvatarError("")
    try {
      const reader = new FileReader()
      reader.onload = async () => {
        try {
          const dataUri = reader.result as string
          const res = await profileApi.uploadAvatar(dataUri)
          setUser({ ...user!, avatar_url: res.avatar_url })
        } catch (e: unknown) { setAvatarError(getErrorMessage(e)) }
        setAvatarLoading(false)
      }
      reader.onerror = () => { setAvatarError("Failed to read file"); setAvatarLoading(false) }
      reader.readAsDataURL(file)
    } catch (e: unknown) { setAvatarError(getErrorMessage(e)); setAvatarLoading(false) }
  }

  if (!user) return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-2">
        <div className="size-6 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  )

  const details = [
    { label: "Email", value: user.email, icon: Mail },
    { label: "User ID", value: `#${user.id}`, icon: User },
    { label: "Role", value: user.role, icon: Shield, badge: true },
    { label: "Plan", value: user.plan, icon: Crown, badge: true, badgeColor: user.plan === "free" ? "secondary" as const : "success" as const },
    { label: "Joined", value: new Date(user.created_at).toLocaleDateString(), icon: CalendarDays },
    { label: "Verified", value: user.is_verified ? "Yes" : "No", icon: user.is_verified ? CheckCircle : XCircle, badge: true, badgeColor: user.is_verified ? "success" as const : "warning" as const },
  ]

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground">Your account details and settings.</p>
      </div>

      <div className="mx-auto max-w-2xl space-y-6">
        {/* Avatar */}
        <Card>
          <CardHeader><CardTitle>Avatar</CardTitle></CardHeader>
          <CardContent className="flex items-center gap-4">
            <div className="relative size-16 overflow-hidden rounded-full bg-muted">
              {user.avatar_url ? (
                <Image src={user.avatar_url} alt="Avatar" fill className="object-cover" unoptimized />
              ) : (
                <div className="flex size-full items-center justify-center text-lg font-bold text-muted-foreground">
                  {user.email[0].toUpperCase()}
                </div>
              )}
              {avatarLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                  <Loader2 className="size-5 animate-spin text-white" />
                </div>
              )}
            </div>
            <div className="flex-1">
              <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="hidden" onChange={(e) => e.target.files?.[0] && handleAvatarUpload(e.target.files[0])} />
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={avatarLoading}>
                <Camera className="mr-1 size-4" /> Upload Avatar
              </Button>
              {avatarError && <p className="mt-1 text-xs text-red-400">{avatarError}</p>}
            </div>
          </CardContent>
        </Card>

        {/* Account Details */}
        <Card>
          <CardHeader><CardTitle>Account Details</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {details.map((d) => {
              const Icon = d.icon
              return (
                <div key={d.label} className="flex items-center justify-between rounded-lg bg-muted px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Icon className="size-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">{d.label}</span>
                  </div>
                  {d.badge ? (
                    <Badge variant={d.badgeColor || "default"} className="capitalize">{d.value}</Badge>
                  ) : (
                    <span className="text-sm font-medium">{d.value}</span>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>

        {/* Change Password */}
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Lock className="size-4" /> Change Password</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={pwForm.handleSubmit(onPasswordSubmit)} className="space-y-3">
              <div className="space-y-1">
                <Input type="password" placeholder="Current password" {...pwForm.register("pwCurrent")} />
                {pwForm.formState.errors.pwCurrent && <p className="text-xs text-red-400">{pwForm.formState.errors.pwCurrent.message}</p>}
              </div>
              <div className="space-y-1">
                <Input type="password" placeholder="New password" {...pwForm.register("pwNew")} />
                {pwForm.formState.errors.pwNew && <p className="text-xs text-red-400">{pwForm.formState.errors.pwNew.message}</p>}
              </div>
              {pwError && <p className="flex items-center gap-1 text-xs text-red-400"><AlertCircle className="size-3" /> {pwError}</p>}
              {pwSuccess && <p className="flex items-center gap-1 text-xs text-green-400"><Check className="size-3" /> {pwSuccess}</p>}
              <Button type="submit" disabled={pwForm.formState.isSubmitting}>
                {pwForm.formState.isSubmitting && <Loader2 className="mr-1 size-4 animate-spin" />} Update Password
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Change Email */}
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Mail className="size-4" /> Change Email</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={emailForm.handleSubmit(onEmailSubmit)} className="space-y-3">
              <div className="space-y-1">
                <Input type="email" placeholder="New email address" {...emailForm.register("newEmail")} />
                {emailForm.formState.errors.newEmail && <p className="text-xs text-red-400">{emailForm.formState.errors.newEmail.message}</p>}
              </div>
              <div className="space-y-1">
                <Input type="password" placeholder="Current password (to confirm)" {...emailForm.register("emailPw")} />
                {emailForm.formState.errors.emailPw && <p className="text-xs text-red-400">{emailForm.formState.errors.emailPw.message}</p>}
              </div>
              {emailError && <p className="flex items-center gap-1 text-xs text-red-400"><AlertCircle className="size-3" /> {emailError}</p>}
              {emailSuccess && <p className="flex items-center gap-1 text-xs text-green-400"><Check className="size-3" /> {emailSuccess}</p>}
              <Button type="submit" disabled={emailForm.formState.isSubmitting}>
                {emailForm.formState.isSubmitting && <Loader2 className="mr-1 size-4 animate-spin" />} Update Email
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Upgrade / Verify cards */}
        <div className="grid gap-4 sm:grid-cols-2">
          {!user.is_verified && (
            <Card>
              <CardContent className="flex items-center gap-4 pt-6">
                <XCircle className="size-6 text-amber-400" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Email not verified</p>
                  <p className="text-xs text-muted-foreground">Check your inbox for the verification link.</p>
                </div>
              </CardContent>
            </Card>
          )}
          <Card className="cursor-pointer hover:bg-muted/30" onClick={() => router.push("/billing")}>
            <CardContent className="flex items-center gap-4 pt-6">
              <Crown className="size-6 text-amber-400" />
              <div className="flex-1">
                <p className="text-sm font-medium">Upgrade Plan</p>
                <p className="text-xs text-muted-foreground">You&apos;re on the {user.plan} plan</p>
              </div>
              <ExternalLink className="size-4 text-muted-foreground" />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
