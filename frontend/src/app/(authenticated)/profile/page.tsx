"use client"

import Image from "next/image"
import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  auth,
  getErrorMessage,
  profileApi,
  type SessionItem,
  type TwoFactorSetup,
  type TwoFactorStatus,
} from "@/lib/api"
import { useMe } from "@/queries"
import {
  AlertCircle,
  CalendarDays,
  Camera,
  Check,
  CheckCircle,
  Download,
  Loader2,
  Lock,
  LogOut,
  Mail,
  MonitorSmartphone,
  RefreshCcw,
  Shield,
  Trash2,
  User,
  XCircle,
} from "lucide-react"

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

function formatDate(value: string | null | undefined) {
  if (!value) return "Unknown"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return "Unknown"
  return d.toLocaleString()
}

function InlineError({ message }: { message: string }) {
  if (!message) return null
  return (
    <p className="flex items-center gap-1 text-xs text-red-600">
      <AlertCircle className="size-3" /> {message}
    </p>
  )
}

function InlineSuccess({ message }: { message: string }) {
  if (!message) return null
  return (
    <p className="flex items-center gap-1 text-xs text-green-600">
      <Check className="size-3" /> {message}
    </p>
  )
}

export default function ProfilePage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { data: user, isError: meError } = useMe()
  const fileRef = useRef<HTMLInputElement>(null)

  const [pwError, setPwError] = useState("")
  const [pwSuccess, setPwSuccess] = useState("")
  const pwForm = useForm<PasswordFormData>({ resolver: zodResolver(passwordSchema) })

  const [emailError, setEmailError] = useState("")
  const [emailSuccess, setEmailSuccess] = useState("")
  const emailForm = useForm<EmailFormData>({ resolver: zodResolver(emailSchema) })

  const [avatarLoading, setAvatarLoading] = useState(false)
  const [avatarError, setAvatarError] = useState("")

  const [resending, setResending] = useState(false)
  const [verifyMsg, setVerifyMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null)

  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState("")
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [revokingOthers, setRevokingOthers] = useState(false)

  const [twoFactor, setTwoFactor] = useState<TwoFactorStatus | null>(null)
  const [twoFactorLoading, setTwoFactorLoading] = useState(true)
  const [twoFactorError, setTwoFactorError] = useState("")
  const [twoFactorMsg, setTwoFactorMsg] = useState("")
  const [setupPw, setSetupPw] = useState("")
  const [setupData, setSetupData] = useState<TwoFactorSetup | null>(null)
  const [confirmCode, setConfirmCode] = useState("")
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
  const [disablePw, setDisablePw] = useState("")
  const [disableCode, setDisableCode] = useState("")
  const [regenPw, setRegenPw] = useState("")
  const [regenCode, setRegenCode] = useState("")
  const [twoFactorBusy, setTwoFactorBusy] = useState<"setup" | "confirm" | "disable" | "regen" | null>(null)

  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState("")
  const [deletePw, setDeletePw] = useState("")
  const [deleteConfirm, setDeleteConfirm] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState("")

  async function loadSessions(showLoading = true) {
    if (showLoading) setSessionsLoading(true)
    setSessionsError("")
    try {
      const res = await auth.sessions()
      setSessions(res.sessions)
    } catch (e: unknown) {
      setSessionsError(getErrorMessage(e, "Failed to load sessions"))
    } finally {
      setSessionsLoading(false)
    }
  }

  async function loadTwoFactor(showLoading = true) {
    if (showLoading) setTwoFactorLoading(true)
    try {
      setTwoFactor(await profileApi.twoFactorStatus())
    } catch (e: unknown) {
      setTwoFactorError(getErrorMessage(e, "Failed to load 2FA status"))
    } finally {
      setTwoFactorLoading(false)
    }
  }

  useEffect(() => {
    const t = window.setTimeout(() => {
      void loadSessions(false)
      void loadTwoFactor(false)
    }, 0)
    return () => window.clearTimeout(t)
  }, [])

  useEffect(() => {
    if (meError) router.push("/login?expired=1")
  }, [meError, router])

  async function handleResendVerification() {
    setResending(true)
    setVerifyMsg(null)
    try {
      await auth.resendVerification()
      setVerifyMsg({ kind: "ok", text: "New link sent — check your inbox." })
    } catch (e: unknown) {
      setVerifyMsg({ kind: "err", text: getErrorMessage(e, "Could not send the verification email") })
    } finally {
      setResending(false)
    }
  }

  async function onPasswordSubmit(data: PasswordFormData) {
    setPwError("")
    setPwSuccess("")
    try {
      const res = await profileApi.changePassword(data.pwCurrent, data.pwNew)
      setPwSuccess(res.detail)
      pwForm.reset()
    } catch (e: unknown) {
      setPwError(getErrorMessage(e, "Failed to update password"))
    }
  }

  async function onEmailSubmit(data: EmailFormData) {
    setEmailError("")
    setEmailSuccess("")
    try {
      const res = await profileApi.changeEmail(data.newEmail, data.emailPw)
      setEmailSuccess(res.detail)
      queryClient.setQueryData(["me"], { ...user!, email: data.newEmail, is_verified: false })
      emailForm.reset()
    } catch (e: unknown) {
      setEmailError(getErrorMessage(e, "Failed to update email"))
    }
  }

  async function handleAvatarUpload(file: File) {
    if (!file) return
    setAvatarLoading(true)
    setAvatarError("")
    try {
      const reader = new FileReader()
      reader.onload = async () => {
        try {
          const dataUri = reader.result as string
          const res = await profileApi.uploadAvatar(dataUri)
          queryClient.setQueryData(["me"], { ...user!, avatar_url: res.avatar_url })
        } catch (e: unknown) {
          setAvatarError(getErrorMessage(e))
        }
        setAvatarLoading(false)
      }
      reader.onerror = () => {
        setAvatarError("Failed to read file")
        setAvatarLoading(false)
      }
      reader.readAsDataURL(file)
    } catch (e: unknown) {
      setAvatarError(getErrorMessage(e))
      setAvatarLoading(false)
    }
  }

  async function handleRevokeSession(id: string) {
    setRevokingId(id)
    setSessionsError("")
    try {
      await auth.revokeSession(id)
      await loadSessions()
    } catch (e: unknown) {
      setSessionsError(getErrorMessage(e, "Failed to revoke session"))
    } finally {
      setRevokingId(null)
    }
  }

  async function handleRevokeOthers() {
    setRevokingOthers(true)
    setSessionsError("")
    try {
      await auth.revokeOtherSessions()
      await loadSessions()
    } catch (e: unknown) {
      setSessionsError(getErrorMessage(e, "Failed to revoke sessions"))
    } finally {
      setRevokingOthers(false)
    }
  }

  async function handleTwoFactorSetup(e: React.FormEvent) {
    e.preventDefault()
    setTwoFactorBusy("setup")
    setTwoFactorError("")
    setTwoFactorMsg("")
    try {
      const res = await profileApi.twoFactorSetup(setupPw)
      setSetupData(res)
      setRecoveryCodes(null)
    } catch (e: unknown) {
      setTwoFactorError(getErrorMessage(e, "Failed to start 2FA setup"))
    } finally {
      setTwoFactorBusy(null)
    }
  }

  async function handleTwoFactorConfirm(e: React.FormEvent) {
    e.preventDefault()
    setTwoFactorBusy("confirm")
    setTwoFactorError("")
    try {
      const res = await profileApi.twoFactorConfirm(confirmCode.trim())
      setRecoveryCodes(res.recovery_codes)
      setSetupData(null)
      setConfirmCode("")
      setSetupPw("")
      setTwoFactorMsg("Two-factor authentication enabled. Save your recovery codes now.")
      await loadTwoFactor()
      queryClient.setQueryData(["me"], { ...user!, two_factor_enabled: true })
    } catch (e: unknown) {
      setTwoFactorError(getErrorMessage(e, "Failed to confirm 2FA"))
    } finally {
      setTwoFactorBusy(null)
    }
  }

  async function handleTwoFactorDisable(e: React.FormEvent) {
    e.preventDefault()
    setTwoFactorBusy("disable")
    setTwoFactorError("")
    setTwoFactorMsg("")
    try {
      await profileApi.twoFactorDisable(disablePw, disableCode.trim())
      setDisablePw("")
      setDisableCode("")
      setRecoveryCodes(null)
      setTwoFactorMsg("Two-factor authentication disabled.")
      await loadTwoFactor()
      queryClient.setQueryData(["me"], { ...user!, two_factor_enabled: false })
    } catch (e: unknown) {
      setTwoFactorError(getErrorMessage(e, "Failed to disable 2FA"))
    } finally {
      setTwoFactorBusy(null)
    }
  }

  async function handleRegenerateRecoveryCodes(e: React.FormEvent) {
    e.preventDefault()
    setTwoFactorBusy("regen")
    setTwoFactorError("")
    setTwoFactorMsg("")
    try {
      const res = await profileApi.twoFactorRegenerateRecoveryCodes(regenPw, regenCode.trim())
      setRecoveryCodes(res.recovery_codes)
      setRegenPw("")
      setRegenCode("")
      setTwoFactorMsg("Recovery codes regenerated. Save the new codes now.")
      await loadTwoFactor()
    } catch (e: unknown) {
      setTwoFactorError(getErrorMessage(e, "Failed to regenerate recovery codes"))
    } finally {
      setTwoFactorBusy(null)
    }
  }

  async function handleExport() {
    setExporting(true)
    setExportError("")
    try {
      const data = await profileApi.exportAccount()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `linkforge-account-export-${user?.id ?? "me"}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      setExportError(getErrorMessage(e, "Failed to export account data"))
    } finally {
      setExporting(false)
    }
  }

  async function handleDeleteAccount(e: React.FormEvent) {
    e.preventDefault()
    setDeleting(true)
    setDeleteError("")
    try {
      await profileApi.deleteAccount(deletePw, deleteConfirm)
      queryClient.clear()
      router.push("/login")
    } catch (e: unknown) {
      setDeleteError(getErrorMessage(e, "Failed to delete account"))
    } finally {
      setDeleting(false)
    }
  }

  if (!user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <div className="size-6 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  const details = [
    { label: "Email", value: user.email, icon: Mail },
    { label: "User ID", value: `#${user.id}`, icon: User },
    { label: "Joined", value: new Date(user.created_at).toLocaleDateString(), icon: CalendarDays },
    {
      label: "Verified",
      value: user.is_verified ? "Yes" : "No",
      icon: user.is_verified ? CheckCircle : XCircle,
      badge: true,
      badgeColor: user.is_verified ? ("success" as const) : ("warning" as const),
    },
  ]

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-slate-500/10 text-slate-600">
          <User className="size-4.5" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-semibold tracking-tight">Profile</h1>
          <p className="text-sm text-muted-foreground">Your account details, security, sessions, and data controls.</p>
        </div>
      </div>

      <div className="mx-auto max-w-2xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Avatar</CardTitle>
          </CardHeader>
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
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleAvatarUpload(e.target.files[0])}
              />
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={avatarLoading}>
                <Camera className="mr-1 size-4" /> Upload Avatar
              </Button>
              {avatarError && <p className="mt-1 text-xs text-red-600">{avatarError}</p>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Account Details</CardTitle>
          </CardHeader>
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
                    <Badge variant={d.badgeColor || "default"} className="capitalize">
                      {d.value}
                    </Badge>
                  ) : (
                    <span className="text-sm font-medium">{d.value}</span>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="size-4" /> Change Password
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={pwForm.handleSubmit(onPasswordSubmit)} className="space-y-3">
              <div className="space-y-1">
                <Input type="password" placeholder="Current password" {...pwForm.register("pwCurrent")} />
                {pwForm.formState.errors.pwCurrent && (
                  <p className="text-xs text-red-600">{pwForm.formState.errors.pwCurrent.message}</p>
                )}
              </div>
              <div className="space-y-1">
                <Input type="password" placeholder="New password" {...pwForm.register("pwNew")} />
                {pwForm.formState.errors.pwNew && (
                  <p className="text-xs text-red-600">{pwForm.formState.errors.pwNew.message}</p>
                )}
              </div>
              <InlineError message={pwError} />
              <InlineSuccess message={pwSuccess} />
              <Button type="submit" disabled={pwForm.formState.isSubmitting}>
                {pwForm.formState.isSubmitting && <Loader2 className="mr-1 size-4 animate-spin" />} Update Password
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="size-4" /> Change Email
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={emailForm.handleSubmit(onEmailSubmit)} className="space-y-3">
              <div className="space-y-1">
                <Input type="email" placeholder="New email address" {...emailForm.register("newEmail")} />
                {emailForm.formState.errors.newEmail && (
                  <p className="text-xs text-red-600">{emailForm.formState.errors.newEmail.message}</p>
                )}
              </div>
              <div className="space-y-1">
                <Input type="password" placeholder="Current password (to confirm)" {...emailForm.register("emailPw")} />
                {emailForm.formState.errors.emailPw && (
                  <p className="text-xs text-red-600">{emailForm.formState.errors.emailPw.message}</p>
                )}
              </div>
              <InlineError message={emailError} />
              <InlineSuccess message={emailSuccess} />
              <Button type="submit" disabled={emailForm.formState.isSubmitting}>
                {emailForm.formState.isSubmitting && <Loader2 className="mr-1 size-4 animate-spin" />} Update Email
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="flex items-center gap-2">
                <Shield className="size-4" /> Two-Factor Authentication
              </CardTitle>
              {!twoFactorLoading && twoFactor?.enabled ? <Badge variant="success">Enabled</Badge> : <Badge variant="secondary">Optional</Badge>}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Add a TOTP authenticator app for an extra sign-in step. Recommended for admins and power users.
            </p>
            <InlineError message={twoFactorError} />
            <InlineSuccess message={twoFactorMsg} />

            {twoFactorLoading ? (
              <p className="text-sm text-muted-foreground">Loading 2FA status...</p>
            ) : !twoFactor?.enabled ? (
              <div className="space-y-4">
                {!setupData ? (
                  <form onSubmit={handleTwoFactorSetup} className="space-y-3">
                    <Input type="password" placeholder="Current password" value={setupPw} onChange={(e) => setSetupPw(e.target.value)} />
                    <Button type="submit" disabled={twoFactorBusy === "setup" || !setupPw}>
                      {twoFactorBusy === "setup" && <Loader2 className="mr-1 size-4 animate-spin" />} Begin 2FA Setup
                    </Button>
                  </form>
                ) : (
                  <div className="space-y-3 rounded-lg border p-4">
                    <p className="text-sm font-medium">Scan this QR code with your authenticator app</p>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={setupData.qr_code_data_uri} alt="2FA QR code" className="size-44 rounded-md border bg-white p-2" />
                    <p className="text-xs text-muted-foreground break-all">
                      Secret: <span className="font-mono">{setupData.secret}</span>
                    </p>
                    <form onSubmit={handleTwoFactorConfirm} className="space-y-3">
                      <Input inputMode="numeric" placeholder="6-digit code" value={confirmCode} onChange={(e) => setConfirmCode(e.target.value)} />
                      <div className="flex gap-2">
                        <Button type="submit" disabled={twoFactorBusy === "confirm" || !confirmCode.trim()}>
                          {twoFactorBusy === "confirm" && <Loader2 className="mr-1 size-4 animate-spin" />} Confirm & Enable
                        </Button>
                        <Button type="button" variant="outline" onClick={() => { setSetupData(null); setConfirmCode("") }}>
                          Cancel
                        </Button>
                      </div>
                    </form>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Enabled {twoFactor.confirmed_at ? `on ${formatDate(twoFactor.confirmed_at)}` : ""}. Recovery codes remaining:{" "}
                  {twoFactor.recovery_codes_remaining}.
                </p>
                <form onSubmit={handleRegenerateRecoveryCodes} className="space-y-3 rounded-lg border p-4">
                  <p className="text-sm font-medium flex items-center gap-2"><RefreshCcw className="size-4" /> Regenerate recovery codes</p>
                  <Input type="password" placeholder="Current password" value={regenPw} onChange={(e) => setRegenPw(e.target.value)} />
                  <Input placeholder="TOTP code" value={regenCode} onChange={(e) => setRegenCode(e.target.value)} />
                  <Button type="submit" variant="outline" disabled={twoFactorBusy === "regen" || !regenPw || !regenCode.trim()}>
                    {twoFactorBusy === "regen" && <Loader2 className="mr-1 size-4 animate-spin" />} Regenerate codes
                  </Button>
                </form>
                <form onSubmit={handleTwoFactorDisable} className="space-y-3 rounded-lg border p-4">
                  <p className="text-sm font-medium">Disable 2FA</p>
                  <Input type="password" placeholder="Current password" value={disablePw} onChange={(e) => setDisablePw(e.target.value)} />
                  <Input placeholder="TOTP code or recovery code" value={disableCode} onChange={(e) => setDisableCode(e.target.value)} />
                  <Button type="submit" variant="outline" disabled={twoFactorBusy === "disable" || !disablePw || !disableCode.trim()}>
                    {twoFactorBusy === "disable" && <Loader2 className="mr-1 size-4 animate-spin" />} Disable 2FA
                  </Button>
                </form>
              </div>
            )}

            {recoveryCodes && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
                <p className="text-sm font-medium text-amber-800">Recovery codes (save these now)</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Each code can be used once if you lose access to your authenticator app. These codes are not shown again.
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-xs">
                  {recoveryCodes.map((c) => (
                    <div key={c} className="rounded bg-background px-2 py-1">
                      {c}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="flex items-center gap-2">
                <MonitorSmartphone className="size-4" /> Active Sessions
              </CardTitle>
              <Button variant="outline" size="sm" onClick={handleRevokeOthers} disabled={revokingOthers || sessionsLoading}>
                {revokingOthers ? <Loader2 className="mr-1 size-4 animate-spin" /> : <LogOut className="mr-1 size-4" />}
                Revoke others
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Manage devices and browsers signed into your account.</p>
            <InlineError message={sessionsError} />
            {sessionsLoading ? (
              <p className="text-sm text-muted-foreground">Loading sessions...</p>
            ) : sessions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No active sessions found.</p>
            ) : (
              <div className="space-y-2">
                {sessions.map((s) => (
                  <div key={s.id} className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-medium">{s.user_agent || "Unknown device"}</p>
                        {s.is_current && <Badge variant="success">Current</Badge>}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        IP: {s.ip_address || "Unknown"} · Last seen: {formatDate(s.last_seen_at)}
                      </p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => handleRevokeSession(s.id)} disabled={revokingId === s.id}>
                      {revokingId === s.id ? <Loader2 className="size-4 animate-spin" /> : "Revoke"}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="size-4" /> Data Export
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Download a JSON export of your profile, workspaces, links, API key metadata, and favorites. Audit logs are retained per
              security/compliance policy and actor references are anonymized on account deletion.
            </p>
            <InlineError message={exportError} />
            <Button variant="outline" onClick={handleExport} disabled={exporting}>
              {exporting ? <Loader2 className="mr-1 size-4 animate-spin" /> : <Download className="mr-1 size-4" />}
              Export my data
            </Button>
          </CardContent>
        </Card>

        <Card className="border-red-500/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-700">
              <Trash2 className="size-4" /> Delete Account
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-sm text-muted-foreground">
              Permanently delete your account. Owned workspaces, links, API keys, and favorites are removed by cascade. Audit logs are
              retained for security/compliance with the actor reference anonymized.
            </p>
            <form onSubmit={handleDeleteAccount} className="space-y-3">
              <Input type="password" placeholder="Current password" value={deletePw} onChange={(e) => setDeletePw(e.target.value)} />
              <Input placeholder="Type DELETE to confirm" value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} />
              <InlineError message={deleteError} />
              <Button type="submit" variant="destructive" disabled={deleting || !deletePw || deleteConfirm !== "DELETE"}>
                {deleting ? <Loader2 className="mr-1 size-4 animate-spin" /> : <Trash2 className="mr-1 size-4" />}
                Delete account
              </Button>
            </form>
          </CardContent>
        </Card>

        {!user.is_verified && (
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <XCircle className="size-6 shrink-0 text-amber-600" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Email not verified</p>
                  <p className="text-xs text-muted-foreground">Check your inbox for the verification link.</p>
                </div>
                <Button variant="outline" size="sm" onClick={handleResendVerification} disabled={resending}>
                  {resending ? <Loader2 className="mr-1 size-4 animate-spin" /> : <Mail className="mr-1 size-4" />} Resend
                </Button>
              </div>
              {verifyMsg && (
                <p
                  role="status"
                  className={`mt-3 flex items-center gap-1.5 text-xs ${verifyMsg.kind === "ok" ? "text-green-600" : "text-red-600"}`}
                >
                  {verifyMsg.kind === "ok" ? <Check className="size-3.5" /> : <AlertCircle className="size-3.5" />}
                  {verifyMsg.text}
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
