import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test/test-utils"
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
  it("renders the page title", async () => {
    render(<AnalyticsPage />)
    expect(await screen.findByText("Analytics")).toBeDefined()
  })

  it("shows the short code and URL", async () => {
    render(<AnalyticsPage />)
    expect(await screen.findByText(/https:\/\/example.com/)).toBeDefined()
  })

  it("shows analytics stats", async () => {
    render(<AnalyticsPage />)
    expect(await screen.findByText("Total Clicks")).toBeDefined()
    expect(screen.getByText("Unique Visitors")).toBeDefined()
    expect(screen.getByText("Status")).toBeDefined()
  })

  it("shows analytics values", async () => {
    render(<AnalyticsPage />)
    expect(await screen.findByText("100")).toBeDefined()
    expect(await screen.findByText("50")).toBeDefined()
  })

  it("renders back button", async () => {
    render(<AnalyticsPage />)
    expect(await screen.findByText("Back to URLs")).toBeDefined()
  })

  it("renders period selector", async () => {
    render(<AnalyticsPage />)
    expect(await screen.findByText("7 days")).toBeDefined()
  })

  it("renders no data message for empty timeseries", async () => {
    render(<AnalyticsPage />)
    expect(await screen.findByText("No data yet")).toBeDefined()
  })
})
