import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import CreateURLPage from "@/app/(authenticated)/urls/new/page"

vi.mock("@/queries", () => ({
  useWorkspaces: () => ({ data: [{ id: 1, name: "My Workspace" }] }),
  useFolders: () => ({ data: [{ id: 1, name: "General" }] }),
  useTags: () => ({ data: [{ id: 1, name: "important" }] }),
  useCreateUrlMutation: () => ({ mutateAsync: vi.fn(), isError: false, error: null }),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

describe("CreateURLPage", () => {
  it("renders the page title", () => {
    render(<CreateURLPage />)
    expect(screen.getByText("Create Short URL")).toBeDefined()
  })

  it("renders form fields", () => {
    render(<CreateURLPage />)
    expect(screen.getByText("Original URL")).toBeDefined()
    expect(screen.getByText("Workspace")).toBeDefined()
    expect(screen.getByText("Folder")).toBeDefined()
    expect(screen.getByText("Custom Alias")).toBeDefined()
    expect(screen.getByText("A/B Testing")).toBeDefined()
  })

  it("renders submit button", () => {
    render(<CreateURLPage />)
    expect(screen.getByText("Create URL")).toBeDefined()
  })

  it("renders back button", () => {
    render(<CreateURLPage />)
    expect(screen.getByText("Back")).toBeDefined()
  })

  it("renders cancel button", () => {
    render(<CreateURLPage />)
    expect(screen.getByText("Cancel")).toBeDefined()
  })

  it("renders workspace selector with options", () => {
    render(<CreateURLPage />)
    expect(screen.getByText("My Workspace")).toBeDefined()
  })

  it("renders tags when available", () => {
    render(<CreateURLPage />)
    expect(screen.getByText("important")).toBeDefined()
  })
})
