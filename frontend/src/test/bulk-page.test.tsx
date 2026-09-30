import { describe, it, expect } from "vitest"
import { render, screen } from "@/test/test-utils"
import BulkPage from "@/app/(authenticated)/bulk/page"

describe("BulkPage", () => {

  it("renders the page title", () => {
    render(<BulkPage />)
    expect(screen.getByText("Bulk Operations")).toBeDefined()
  })

  it("shows create tab by default", () => {
    render(<BulkPage />)
    expect(screen.getAllByText("Bulk Create").length).toBeGreaterThan(0)
    expect(screen.getByText("Defaults")).toBeDefined()
    expect(screen.getByText("Export URLs")).toBeDefined()
  })

  it("renders tab buttons", () => {
    render(<BulkPage />)
    expect(screen.getByText("Create")).toBeDefined()
    expect(screen.getByText("Manage")).toBeDefined()
  })

  it("shows export button", () => {
    render(<BulkPage />)
    expect(screen.getByText("Export CSV")).toBeDefined()
  })

  it("renders textarea for URL input", () => {
    render(<BulkPage />)
    expect(screen.getByPlaceholderText(/https:\/\/example.com/)).toBeDefined()
  })
})
