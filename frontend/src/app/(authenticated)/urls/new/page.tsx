"use client"

import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { useWorkspaces, useFolders, useTags, useCreateUrlMutation } from "@/queries"
import { createUrlSchema, type CreateUrlFormData } from "@/lib/schemas"
import { Link2, ArrowLeft } from "lucide-react"
import { useState } from "react"

export default function CreateURLPage() {
  const router = useRouter()
  const [selectedWs, setSelectedWs] = useState(0)
  const { data: workspaces = [] } = useWorkspaces()
  const { data: folders = [] } = useFolders(selectedWs || null)
  const { data: tags = [] } = useTags(selectedWs || null)
  const createUrl = useCreateUrlMutation()

  const { register, handleSubmit, setValue, watch, formState: { errors, isSubmitting } } = useForm<CreateUrlFormData>({
    resolver: zodResolver(createUrlSchema),
    defaultValues: { workspace_id: selectedWs },
  })

  // eslint-disable-next-line react-hooks/incompatible-library
  const isAbTest = watch("is_ab_test")
  const [selectedTagList, setSelectedTagList] = useState<string[]>([])
  const [folderVal, setFolderVal] = useState("")

  function toggleTag(name: string) {
    setSelectedTagList((prev) => {
      const next = prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]
      setValue("tags", next)
      return next
    })
  }

  async function onSubmit(data: CreateUrlFormData) {
    try {
      await createUrl.mutateAsync({
        original_url: data.original_url,
        workspace_id: data.workspace_id,
        custom_alias: data.custom_alias || undefined,
        folder_id: folderVal ? Number(folderVal) : undefined,
        tags: selectedTagList.length > 0 ? selectedTagList : undefined,
        is_ab_test: data.is_ab_test || false,
        is_one_time: false,
      })
      router.push("/urls")
    } catch {
      // mutation error is shown via createUrl.isError
    }
  }

  return (
    <div className="p-6">
      <button onClick={() => router.back()} className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back
      </button>
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-blue-500/10 p-2">
                <Link2 className="size-5 text-blue-400" />
              </div>
              <div>
                <CardTitle>Create Short URL</CardTitle>
                <p className="text-sm text-muted-foreground">Paste a long URL and customize your short link.</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {createUrl.isError && <p className="text-sm text-red-400">{createUrl.error.message}</p>}

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <Label>Original URL</Label>
                  <Input type="url" {...register("original_url")} required placeholder="https://example.com/very/long/url" />
                  {errors.original_url && <p className="mt-1 text-xs text-red-400">{errors.original_url.message}</p>}
                </div>
                <div>
                  <Label>Workspace</Label>
                  <Select value={String(selectedWs)} onChange={(e) => {
                    const id = Number(e.target.value)
                    setSelectedWs(id)
                    setValue("workspace_id", id)
                  }}>
                    <option value="">Select...</option>
                    {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                  </Select>
                </div>
                <div>
                  <Label>Folder <span className="text-muted-foreground">(optional)</span></Label>
                  <Select value={folderVal} onChange={(e) => setFolderVal(e.target.value)}>
                    <option value="">No folder</option>
                    {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </Select>
                </div>
                <div>
                  <Label>Custom Alias <span className="text-muted-foreground">(optional)</span></Label>
                  <Input type="text" {...register("custom_alias")} placeholder="my-custom-link" />
                  {errors.custom_alias && <p className="mt-1 text-xs text-red-400">{errors.custom_alias.message}</p>}
                </div>
              </div>

              <Separator />
              <p className="text-sm font-medium">Features</p>

              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">A/B Testing</p>
                  <p className="text-xs text-muted-foreground">Different destinations for iOS / Android</p>
                </div>
                <Switch checked={!!isAbTest} onCheckedChange={(v) => setValue("is_ab_test", v)} />
              </div>

              {tags.length > 0 && (
                <div>
                  <Label>Tags</Label>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {tags.map((t) => (
                      <button key={t.id} type="button" onClick={() => toggleTag(t.name)}
                        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                          selectedTagList.includes(t.name)
                            ? "bg-blue-600 text-white"
                            : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                        }`}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-col gap-3 pt-2 sm:flex-row">
                <Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button>
                <Button type="submit" disabled={isSubmitting} className="bg-blue-600 text-white hover:bg-blue-700">
                  {isSubmitting ? "Creating..." : "Create URL"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
