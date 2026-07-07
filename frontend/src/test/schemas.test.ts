import { describe, it, expect } from "vitest"
import { loginSchema, registerSchema, createUrlSchema } from "@/lib/schemas"

describe("loginSchema", () => {
  it("accepts valid input", () => {
    const result = loginSchema.safeParse({ email: "test@test.com", password: "123456" })
    expect(result.success).toBe(true)
  })

  it("rejects invalid email", () => {
    const result = loginSchema.safeParse({ email: "not-email", password: "123456" })
    expect(result.success).toBe(false)
    if (!result.success) expect(result.error.issues[0].path).toContain("email")
  })

  it("rejects short password", () => {
    const result = loginSchema.safeParse({ email: "test@test.com", password: "123" })
    expect(result.success).toBe(false)
  })

  it("rejects empty fields", () => {
    const result = loginSchema.safeParse({ email: "", password: "" })
    expect(result.success).toBe(false)
  })
})

describe("registerSchema", () => {
  it("accepts valid input with matching passwords", () => {
    const result = registerSchema.safeParse({ email: "test@test.com", password: "12345678", confirmPassword: "12345678" })
    expect(result.success).toBe(true)
  })

  it("rejects mismatched passwords", () => {
    const result = registerSchema.safeParse({ email: "test@test.com", password: "12345678", confirmPassword: "different" })
    expect(result.success).toBe(false)
    if (!result.success) expect(result.error.issues[0].path).toContain("confirmPassword")
  })

  it("rejects password shorter than 8 characters", () => {
    const result = registerSchema.safeParse({ email: "test@test.com", password: "1234567", confirmPassword: "1234567" })
    expect(result.success).toBe(false)
  })

  it("rejects invalid email", () => {
    const result = registerSchema.safeParse({ email: "bad", password: "12345678", confirmPassword: "12345678" })
    expect(result.success).toBe(false)
  })

  it("rejects empty confirm password", () => {
    const result = registerSchema.safeParse({ email: "test@test.com", password: "12345678", confirmPassword: "" })
    expect(result.success).toBe(false)
  })
})

describe("createUrlSchema", () => {
  it("accepts minimal valid input", () => {
    const result = createUrlSchema.safeParse({ original_url: "https://example.com", workspace_id: 1 })
    expect(result.success).toBe(true)
  })

  it("rejects invalid URL", () => {
    const result = createUrlSchema.safeParse({ original_url: "not-a-url", workspace_id: 1 })
    expect(result.success).toBe(false)
  })

  it("accepts full valid input", () => {
    const result = createUrlSchema.safeParse({
      original_url: "https://example.com",
      workspace_id: 1,
      custom_alias: "my-link",
      folder_id: 2,
      password: "secret",
      expires_at: "2025-01-01T00:00:00Z",
      is_one_time: true,
      is_ab_test: false,
      tags: ["tag1", "tag2"],
    })
    expect(result.success).toBe(true)
  })

  it("rejects custom alias with invalid characters", () => {
    const result = createUrlSchema.safeParse({ original_url: "https://example.com", workspace_id: 1, custom_alias: "has spaces" })
    expect(result.success).toBe(false)
  })

  it("accepts empty optional strings", () => {
    const result = createUrlSchema.safeParse({ original_url: "https://example.com", workspace_id: 1, custom_alias: "", password: "", expires_at: "" })
    expect(result.success).toBe(true)
  })
})
