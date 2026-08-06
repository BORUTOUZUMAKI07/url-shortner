"use client"
import { cn } from "@/lib/utils"
import { useState } from "react"

type TabsRenderProps = {
  active: string
  setActive: (value: string) => void
}

function Tabs({ defaultValue, className, children, onChange, ...props }: { defaultValue: string; className?: string; children: React.ReactNode | ((props: TabsRenderProps) => React.ReactNode); onChange?: (value: string) => void } & Omit<React.HTMLAttributes<HTMLDivElement>, "children">) {
  const [active, setActive] = useState(defaultValue)
  const setTab = (value: string) => {
    setActive(value)
    onChange?.(value)
  }
  return (
    <div data-slot="tabs" className={cn("", className)} {...props}>
      {typeof children === "function" ? children({ active, setActive: setTab }) : children}
    </div>
  )
}

function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div data-slot="tabs-list" className={cn("inline-flex h-9 items-center rounded-lg bg-muted p-1 text-muted-foreground", className)} {...props} />
}

function TabsTrigger({ className, value, active, setActive, ...props }: { value: string; active?: string; setActive?: (v: string) => void } & React.HTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      data-slot="tabs-trigger"
      data-state={active === value ? "active" : "inactive"}
      className={cn(
        "inline-flex items-center justify-center rounded-md px-3 py-1 text-sm font-medium whitespace-nowrap transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        "disabled:pointer-events-none disabled:opacity-50",
        active === value ? "bg-background text-foreground shadow-xs" : "hover:text-foreground",
        className,
      )}
      onClick={() => setActive?.(value)}
      {...props}
    />
  )
}

function TabsContent({ className, value, active, ...props }: { value: string; active?: string } & React.HTMLAttributes<HTMLDivElement>) {
  if (active !== value) return null
  return <div data-slot="tabs-content" className={cn("mt-2", className)} {...props} />
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
