import { describe, it, expect } from "vitest"
import { render } from "@/test/test-utils"
import { AuthPrefetcher } from "@/lib/auth-prefetcher"

describe("AuthPrefetcher", () => {
  it("renders null", () => {
    const { container } = render(<AuthPrefetcher />)
    expect(container.innerHTML).toBe("")
  })
})
