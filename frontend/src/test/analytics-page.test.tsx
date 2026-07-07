import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import AnalyticsPage from "@/app/(authenticated)/urls/[id]/analytics/page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock("@/store/auth", () => ({
  useAuthStore: (selector?: (s: any) => any) => {
    const state = { user: { id: 1 }, setUser: vi.fn() }
    return selector ? selector(state) : state
  },
}))

vi.mock("@/lib/api", () => ({
  auth: { me: vi.fn().mockResolvedValue({ id: 1, email: "test@test.com" }) },
  urls: {
    get: vi.fn().mockResolvedValue({ id: 1, short_code: "abc", original_url: "https://example.com", workspace_id: 1, folder_id: null, tags: [], status: "active", is_one_time: false, is_ab_test: false, ios_url: null, android_url: null, custom_alias: null, domain: null, expires_at: null, qr_code: null, created_at: "2024-01-01T00:00:00Z" }),
    analytics: vi.fn().mockResolvedValue([{ short_code: "abc", total_clicks: 42, unique_clicks: 10, last_clicked_at: null }, { short_code: "abc", days: 7, data: [] }]),
    devices: vi.fn().mockResolvedValue({ short_code: "abc", browsers: [], os: [], devices: [], geo: [] }),
    utm: vi.fn().mockResolvedValue({ short_code: "abc", data: [] }),
    referrers: vi.fn().mockResolvedValue({ short_code: "abc", data: [] }),
  },
  getErrorMessage: vi.fn((e) => e instanceof Error ? e.message : "Error"),
}))

let queryReturnMap: Record<string, any> = {
  authMe: { data: { id: 1 }, isLoading: false },
  url: { data: { id: 1, short_code: "abc", original_url: "https://example.com", workspace_id: 1, folder_id: null, tags: [], status: "active", is_one_time: false, is_ab_test: false, ios_url: null, android_url: null, custom_alias: null, domain: null, expires_at: null, qr_code: null, created_at: "2024-01-01T00:00:00Z" }, isLoading: false },
  analytics_summary: { data: [{ short_code: "abc", total_clicks: 42, unique_clicks: 10, last_clicked_at: null }, { short_code: "abc", days: 7, data: [] }] },
  analytics_devices: { data: { short_code: "abc", browsers: [], os: [], devices: [], geo: [] } },
  analytics_utm: { data: { short_code: "abc", data: [] } },
  analytics_referrers: { data: { short_code: "abc", data: [] } },
}

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "authMe") return queryReturnMap.authMe
    if (queryKey[0] === "url") return queryReturnMap.url
    if (queryKey[0] === "analytics_summary") return queryReturnMap.analytics_summary
    if (queryKey[0] === "analytics_devices") return queryReturnMap.analytics_devices
    if (queryKey[0] === "analytics_utm") return queryReturnMap.analytics_utm
    if (queryKey[0] === "analytics_referrers") return queryReturnMap.analytics_referrers
    return { data: null, isLoading: true }
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}))

vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div />,
  Cell: () => <div />,
  Legend: () => <div />,
}))

describe("AnalyticsPage", () => {
  beforeEach(() => {
    queryReturnMap = {
      authMe: { data: { id: 1 }, isLoading: false },
      url: { data: { id: 1, short_code: "abc", original_url: "https://example.com", workspace_id: 1, folder_id: null, tags: [], status: "active", is_one_time: false, is_ab_test: false, ios_url: null, android_url: null, custom_alias: null, domain: null, expires_at: null, qr_code: null, created_at: "2024-01-01T00:00:00Z" }, isLoading: false },
      analytics_summary: { data: [{ short_code: "abc", total_clicks: 42, unique_clicks: 10, last_clicked_at: null }, { short_code: "abc", days: 7, data: [] }] },
      analytics_devices: { data: { short_code: "abc", browsers: [], os: [], devices: [], geo: [] } },
      analytics_utm: { data: { short_code: "abc", data: [] } },
      analytics_referrers: { data: { short_code: "abc", data: [] } },
    }
  })

  it("renders the page title", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText("Analytics")).toBeDefined()
  })

  it("shows the short code and URL", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText(/https:\/\/example.com/)).toBeDefined()
  })

  it("shows analytics stats", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText("Total Clicks")).toBeDefined()
    expect(screen.getByText("Unique Visitors")).toBeDefined()
    expect(screen.getByText("Status")).toBeDefined()
  })

  it("shows click count", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText("42")).toBeDefined()
  })

  it("shows unique click count", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText("10")).toBeDefined()
  })

  it("renders back button", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText("Back to URLs")).toBeDefined()
  })

  it("renders period selector", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText("7 days")).toBeDefined()
  })

  it("renders no data message for empty timeseries", () => {
    render(<AnalyticsPage />)
    expect(screen.getByText("No data yet")).toBeDefined()
  })
})
