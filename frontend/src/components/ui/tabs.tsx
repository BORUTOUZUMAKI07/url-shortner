"use client"
import { cn } from "@/lib/utils"
import { createContext, useContext, useState } from "react"

type TabsRenderProps = {
  active: string
  setActive: (value: string) => void
}

const TabsContext = createContext<TabsRenderProps | null>(null)

function Tabs({ defaultValue, className, children, onChange, ...props }: { defaultValue: string; className?: string; children: React.ReactNode | ((props: TabsRenderProps) => React.ReactNode); onChange?: (value: string) => void } & Omit<React.HTMLAttributes<HTMLDivElement>, "children">) {
  const [active, setActive] = useState(defaultValue)
  const setTab = (value: string) => {
    setActive(value)
    onChange?.(value)
  }
  const contextValue: TabsRenderProps = { active, setActive: setTab }
  return (
    <div data-slot="tabs" className={cn("", className)} {...props}>
      {typeof children === "function" ? children(contextValue) : <TabsContext.Provider value={contextValue}>{children}</TabsContext.Provider>}
    </div>
  )
}

function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div data-slot="tabs-list" className={cn("inline-flex h-9 items-center rounded-lg bg-muted p-1 text-muted-foreground", className)} {...props} />
}

function TabsTrigger({ className, value, active, setActive, ...props }: { value: string; active?: string; setActive?: (v: string) => void } & React.HTMLAttributes<HTMLButtonElement>) {
  const ctx = useContext(TabsContext)
  const isActive = active ?? ctx?.active
  const onSelect = setActive ?? ctx?.setActive
  return (
    <button
      data-slot="tabs-trigger"
      data-state={isActive === value ? "active" : "inactive"}
      className={cn(
        "inline-flex items-center justify-center rounded-md px-3 py-1 text-sm font-medium whitespace-nowrap transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        "disabled:pointer-events-none disabled:opacity-50",
        isActive === value ? "bg-background text-foreground shadow-xs" : "hover:text-foreground",
        className,
      )}
      onClick={() => onSelect?.(value)}
      {...props}
    />
  )
}

function TabsContent({ className, value, active, ...props }: { value: string; active?: string } & React.HTMLAttributes<HTMLDivElement>) {
  const ctx = useContext(TabsContext)
  const isActive = active ?? ctx?.active
  if (isActive !== value) return null
  return <div data-slot="tabs-content" className={cn("mt-2", className)} {...props} />
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
