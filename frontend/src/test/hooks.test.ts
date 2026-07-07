import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useDashboard } from "@/hooks/useDashboard"

const { mockMutateAsync, mockUseMe, mockUseWorkspaces, mockUseUrls, mockUseWorkspaceMembers } = vi.hoisted(() => {
  const mockMutateAsync = vi.fn()
  return {
    mockMutateAsync,
    mockUseMe: vi.fn(() => ({ data: { id: 1, email: "test@test.com" }, isLoading: false })),
    mockUseWorkspaces: vi.fn(() => ({ data: [{ id: 1, name: "Test" }], isLoading: false })),
    mockUseUrls: vi.fn(() => ({ data: { items: [{ id: 1, short_code: "abc", status: "active", original_url: "https://example.com" }], total: 1 }, error: null, isLoading: false })),
    mockUseWorkspaceMembers: vi.fn(() => ({ data: [{ user_id: 1, role: "admin" }], isLoading: false })),
  }
})

vi.mock("@/queries", () => ({
  useMe: mockUseMe,
  useWorkspaces: mockUseWorkspaces,
  useUrls: mockUseUrls,
  useWorkspaceMembers: mockUseWorkspaceMembers,
  useApiKeys: vi.fn(() => ({ data: [], isLoading: false })),
  useApiKeyQuota: vi.fn(() => ({ data: null })),
  useDeleteUrlMutation: vi.fn(() => ({ mutateAsync: mockMutateAsync })),
}))

describe("useDashboard", () => {
  beforeEach(() => {
    mockMutateAsync.mockReset()
    mockUseMe.mockReturnValue({ data: { id: 1, email: "test@test.com" }, isLoading: false })
    mockUseWorkspaces.mockReturnValue({ data: [{ id: 1, name: "Test" }], isLoading: false })
    mockUseUrls.mockReturnValue({ data: { items: [{ id: 1, short_code: "abc", status: "active", original_url: "https://example.com" }], total: 1 }, error: null, isLoading: false })
    mockUseWorkspaceMembers.mockReturnValue({ data: [{ user_id: 1, role: "admin" }], isLoading: false })
  })

  it("returns initial state with data", () => {
    const { result } = renderHook(() => useDashboard())
    expect(result.current.urlList).toHaveLength(1)
    expect(result.current.totalUrlsCount).toBe(1)
    expect(result.current.activeUrls).toHaveLength(1)
    expect(result.current.workspaces).toHaveLength(1)
    expect(result.current.canEdit).toBe(true)
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBe("")
  })

  it("sets wsId", () => {
    const { result } = renderHook(() => useDashboard())
    act(() => result.current.setWsId(5))
    expect(result.current.wsId).toBe(5)
  })

  it("calls handleDelete", async () => {
    const { result } = renderHook(() => useDashboard())
    await act(async () => result.current.handleDelete(1))
    expect(mockMutateAsync).toHaveBeenCalledWith(1)
  })

  it("extracts error message from urlsError", () => {
    mockUseUrls.mockReturnValueOnce({
      data: null, error: new Error("Something went wrong"), isLoading: false,
    } as any)
    const { result } = renderHook(() => useDashboard())
    expect(result.current.error).toBe("Something went wrong")
  })

  it("sets canEdit to false for viewers", () => {
    mockUseWorkspaceMembers.mockReturnValueOnce({ data: [{ user_id: 1, role: "viewer" }], isLoading: false })
    const { result } = renderHook(() => useDashboard())
    expect(result.current.canEdit).toBe(false)
  })

  it("sets isLoading true when user is loading", () => {
    mockUseMe.mockReturnValueOnce({ data: null, isLoading: true } as any)
    const { result } = renderHook(() => useDashboard())
    expect(result.current.isLoading).toBe(true)
  })
})
