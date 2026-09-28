import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test/test-utils"
import ProfilePage from "@/app/(authenticated)/profile/page"

const { mockUser, mockStore, mockStoreHook, authMeResolvedObj } = vi.hoisted(() => {
  const mockUser = { id: 1, email: "test@test.com", is_verified: true, is_active: true, plan: "free", is_superadmin: false, avatar_url: null, created_at: "2024-01-01" }
  const mockStore = { user: mockUser, setUser: vi.fn() }
  const mockStoreHook = (selector?: (s: any) => any) => selector ? selector(mockStore) : mockStore
  mockStoreHook.getState = () => mockStore
  const authMeResolvedObj = { value: true }
  return { mockUser, mockStore, mockStoreHook, authMeResolvedObj }
})

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({ useAuthStore: mockStoreHook }))

describe("ProfilePage", () => {
  beforeEach(() => {
    authMeResolvedObj.value = true
    mockStore.user = mockUser
  })

  it("renders the page title", async () => {
    render(<ProfilePage />)
    expect(await screen.findByText("Profile")).toBeDefined()
  })

  it("renders account details sections", async () => {
    render(<ProfilePage />)
    expect(await screen.findByText("Account Details")).toBeDefined()
    expect(await screen.findByText("Avatar")).toBeDefined()
    expect(await screen.findByText("Change Password")).toBeDefined()
    expect(await screen.findByText("Change Email")).toBeDefined()
  })

  it("renders user email", async () => {
    render(<ProfilePage />)
    expect(await screen.findByText("test@test.com")).toBeDefined()
  })

  it("renders user details", async () => {
    render(<ProfilePage />)
    expect(await screen.findByText("free")).toBeDefined()
    expect(await screen.findByText("Yes")).toBeDefined()
    // The global-role row was removed: users.role had no readers and workspace
    // authorisation actually runs off workspace_members.role, so displaying it
    // here as "Role" was misleading.
    expect(screen.queryByText("Role")).toBeNull()
  })

  it("renders upgrade plan card", async () => {
    render(<ProfilePage />)
    expect(await screen.findByText("Upgrade Plan")).toBeDefined()
  })

  it("renders upload avatar button", async () => {
    render(<ProfilePage />)
    expect(await screen.findByText("Upload Avatar")).toBeDefined()
  })
})
