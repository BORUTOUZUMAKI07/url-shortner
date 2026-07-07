import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import ProfilePage from "@/app/(authenticated)/profile/page"

const { mockUser, mockStore, mockStoreHook, authMeResolvedObj } = vi.hoisted(() => {
  const mockUser = { id: 1, email: "test@test.com", is_verified: true, role: "admin", plan: "free", is_superadmin: false, avatar_url: null, created_at: "2024-01-01" }
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

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn(() => authMeResolvedObj.value ? Promise.resolve(mockUser) : Promise.reject(new Error("Unauthorized"))) },
  profileApi: { changePassword: vi.fn(), changeEmail: vi.fn(), uploadAvatar: vi.fn() },
  getErrorMessage: vi.fn((e) => e instanceof Error ? e.message : "Error"),
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "authMe") return { data: mockUser, isLoading: false }
    return {}
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}))

describe("ProfilePage", () => {
  beforeEach(() => {
    authMeResolvedObj.value = true
    mockStore.user = mockUser
  })

  it("renders the page title", () => {
    render(<ProfilePage />)
    expect(screen.getByText("Profile")).toBeDefined()
  })

  it("renders account details sections", () => {
    render(<ProfilePage />)
    expect(screen.getByText("Account Details")).toBeDefined()
    expect(screen.getByText("Avatar")).toBeDefined()
    expect(screen.getByText("Change Password")).toBeDefined()
    expect(screen.getByText("Change Email")).toBeDefined()
  })

  it("renders user email", () => {
    render(<ProfilePage />)
    expect(screen.getByText("test@test.com")).toBeDefined()
  })

  it("renders user details", () => {
    render(<ProfilePage />)
    expect(screen.getByText("admin")).toBeDefined()
    expect(screen.getByText("free")).toBeDefined()
    expect(screen.getByText("Yes")).toBeDefined()
  })

  it("renders upgrade plan card", () => {
    render(<ProfilePage />)
    expect(screen.getByText("Upgrade Plan")).toBeDefined()
  })

  it("renders upload avatar button", () => {
    render(<ProfilePage />)
    expect(screen.getByText("Upload Avatar")).toBeDefined()
  })
})
