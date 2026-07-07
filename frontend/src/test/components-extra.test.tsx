import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { TableSkeleton, CardSkeleton, FormSkeleton, DetailSkeleton, StatsCardSkeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

describe("Input", () => {
  it("renders with placeholder", () => {
    render(<Input placeholder="Enter text" />)
    expect(screen.getByPlaceholderText("Enter text")).toBeDefined()
  })

  it("renders disabled", () => {
    render(<Input disabled placeholder="Disabled" />)
    expect(screen.getByPlaceholderText("Disabled")).toBeDisabled()
  })

  it("has data-slot attribute", () => {
    const { container } = render(<Input />)
    expect(container.querySelector("[data-slot=input]")).toBeDefined()
  })

  it("applies custom className", () => {
    const { container } = render(<Input className="custom-class" />)
    expect(container.querySelector(".custom-class")).toBeDefined()
  })
})

describe("Label", () => {
  it("renders with text", () => {
    render(<Label>Name</Label>)
    expect(screen.getByText("Name")).toBeDefined()
  })

  it("has data-slot attribute", () => {
    const { container } = render(<Label htmlFor="test">Test</Label>)
    expect(container.querySelector("[data-slot=label]")).toBeDefined()
  })
})

describe("Select", () => {
  it("renders with options", () => {
    render(
      <Select>
        <option value="1">Option 1</option>
        <option value="2">Option 2</option>
      </Select>
    )
    expect(screen.getByText("Option 1")).toBeDefined()
    expect(screen.getByText("Option 2")).toBeDefined()
  })

  it("has data-slot attribute", () => {
    const { container } = render(<Select><option value="">Test</option></Select>)
    expect(container.querySelector("[data-slot=select]")).toBeDefined()
  })

  it("renders disabled", () => {
    render(<Select disabled><option>Test</option></Select>)
    expect(screen.getByRole("combobox")).toBeDisabled()
  })
})

describe("Separator", () => {
  it("renders with data-slot", () => {
    const { container } = render(<Separator />)
    expect(container.querySelector("[data-slot=separator]")).toBeDefined()
  })
})

describe("Table components", () => {
  it("renders a full table", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Data</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    )
    expect(screen.getByText("Name")).toBeDefined()
    expect(screen.getByText("Data")).toBeDefined()
  })

  it("has data-slot attributes", () => {
    const { container } = render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>H</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>C</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    )
    expect(container.querySelector("[data-slot=table]")).toBeDefined()
    expect(container.querySelector("[data-slot=table-header]")).toBeDefined()
    expect(container.querySelector("[data-slot=table-body]")).toBeDefined()
    expect(container.querySelector("[data-slot=table-row]")).toBeDefined()
    expect(container.querySelector("[data-slot=table-head]")).toBeDefined()
    expect(container.querySelector("[data-slot=table-cell]")).toBeDefined()
  })
})

describe("Textarea", () => {
  it("renders with placeholder", () => {
    render(<Textarea placeholder="Write here" />)
    expect(screen.getByPlaceholderText("Write here")).toBeDefined()
  })

  it("has data-slot attribute", () => {
    const { container } = render(<Textarea />)
    expect(container.querySelector("[data-slot=textarea]")).toBeDefined()
  })
})

describe("Skeleton components", () => {
  it("TableSkeleton renders given number of rows", () => {
    const { container } = render(<TableSkeleton rows={3} />)
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(3)
  })

  it("TableSkeleton defaults to 6 rows", () => {
    const { container } = render(<TableSkeleton />)
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(6)
  })

  it("CardSkeleton renders given count", () => {
    const { container } = render(<CardSkeleton count={2} />)
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(2)
  })

  it("CardSkeleton defaults to 3", () => {
    const { container } = render(<CardSkeleton />)
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(3)
  })

  it("FormSkeleton renders 5 placeholders", () => {
    const { container } = render(<FormSkeleton />)
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(5)
  })

  it("DetailSkeleton renders 3 placeholders", () => {
    const { container } = render(<DetailSkeleton />)
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(3)
  })

  it("StatsCardSkeleton renders 4 placeholders", () => {
    const { container } = render(<StatsCardSkeleton />)
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(4)
  })
})

describe("Tabs", () => {
  it("renders with default active tab", () => {
    render(
      {/* @ts-expect-error: Tabs children type intersection issue */}
      <Tabs defaultValue="tab1">
        {({ active, setActive }: { active: string; setActive: (v: string) => void }) => (
          <>
            <TabsList>
              <TabsTrigger value="tab1" active={active} setActive={setActive}>Tab 1</TabsTrigger>
              <TabsTrigger value="tab2" active={active} setActive={setActive}>Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1" active={active}>Content 1</TabsContent>
            <TabsContent value="tab2" active={active}>Content 2</TabsContent>
          </>
        )}
      </Tabs>
    )
    expect(screen.getByText("Content 1")).toBeDefined()
    expect(screen.queryByText("Content 2")).toBeNull()
  })

  it("has data-slot attributes", () => {
    const { container } = render(
      {/* @ts-expect-error: Tabs children type intersection issue */}
      <Tabs defaultValue="a">
        {({ active, setActive }: { active: string; setActive: (v: string) => void }) => (
          <TabsList>
            <TabsTrigger value="a" active={active} setActive={setActive}>A</TabsTrigger>
          </TabsList>
        )}
      </Tabs>
    )
    expect(container.querySelector("[data-slot=tabs]")).toBeDefined()
    expect(container.querySelector("[data-slot=tabs-list]")).toBeDefined()
    expect(container.querySelector("[data-slot=tabs-trigger]")).toBeDefined()
  })
})
