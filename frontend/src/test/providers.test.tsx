import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { Providers } from "@/lib/providers"

describe("Providers", () => {
  it("renders children", () => {
    render(<Providers><div>child</div></Providers>)
    expect(screen.getByText("child")).toBeDefined()
  })

  it("wraps with QueryClientProvider", () => {
    const { container } = render(<Providers><span data-testid="inner">inner</span></Providers>)
    expect(container.querySelector("[data-testid='inner']")).toBeDefined()
  })
})
