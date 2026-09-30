import { describe, it, expect } from "vitest"
import { render, screen } from "@/test/test-utils"
import { server } from "@/test/mocks/server"
import { http, HttpResponse } from "msw"
import FoldersPage from "@/app/(authenticated)/folders/page"

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

describe("FoldersPage", () => {
  it("renders the page title", async () => {
    render(<FoldersPage />)
    expect(await screen.findByText("Folders")).toBeDefined()
  })

  it("renders create folder section", async () => {
    render(<FoldersPage />)
    expect(await screen.findByText("Create Folder")).toBeDefined()
  })

  it("shows empty state when no folders", async () => {
    render(<FoldersPage />)
    expect(await screen.findByText("No folders yet")).toBeDefined()
  })

  it("lists folders when present", async () => {
    server.use(
      http.get(`${API}/folders`, () => {
        return HttpResponse.json([
          { id: 1, name: "Important", workspace_id: 1, created_at: "2024-01-01" },
        ])
      })
    )
    render(<FoldersPage />)
    expect(await screen.findByText("Important")).toBeDefined()
  })
})
