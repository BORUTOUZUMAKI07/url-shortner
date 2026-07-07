import { test, expect, LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage, setupAuthMocks, setupCommonMocks, setAuthState } from "./fixtures"

test.describe("Authentication", () => {
  test("User registration flow", async ({ page }) => {
    const registerPage = new RegisterPage(page)
    const mocks = setupAuthMocks(page)
    await mocks.setup()

    await registerPage.goto()
    await expect(page.getByRole("heading", { name: "Create Account" })).toBeVisible()

    await registerPage.register("newuser@example.com", "securepass123")
    await expect(page.getByText("Account Created")).toBeVisible()
    await expect(page.getByText("Check your email to verify your account")).toBeVisible()
  })

  test("Registration validation shows errors for short password", async ({ page }) => {
    const registerPage = new RegisterPage(page)

    await registerPage.goto()
    await registerPage.fillEmail("test@example.com")
    await registerPage.fillPassword("short")
    await registerPage.fillConfirmPassword("short")
    await registerPage.submit()

    await expect(page.getByText("Password must be at least 8 characters")).toBeVisible()
  })

  test("Registration validation shows error for mismatched passwords", async ({ page }) => {
    const registerPage = new RegisterPage(page)

    await registerPage.goto()
    await registerPage.fillEmail("test@example.com")
    await registerPage.fillPassword("password123")
    await registerPage.fillConfirmPassword("different123")
    await registerPage.submit()

    await expect(page.getByText("Passwords do not match")).toBeVisible()
  })

  test("Login flow", async ({ page }) => {
    const loginPage = new LoginPage(page)
    const mocks = setupAuthMocks(page)
    await mocks.setup()

    await loginPage.goto()
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible()

    await loginPage.login("test@example.com", "password123")

    await page.waitForURL("/dashboard")
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
  })

  test("Login with invalid credentials shows error", async ({ page }) => {
    const loginPage = new LoginPage(page)
    const mocks = setupAuthMocks(page)
    mocks.route(/\/auth\/login$/, (route) => {
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or password" }),
      })
    })
    await mocks.setup()

    await loginPage.goto()
    await loginPage.login("wrong@example.com", "wrongpass")

    await expect(page.getByText("Invalid email or password")).toBeVisible()
  })

  test("Logout flow", async ({ page }) => {
    const mocks = setupAuthMocks(page)
    await mocks.setup()
    await setAuthState(page)

    await page.goto("/dashboard")
    await page.waitForLoadState("networkidle")

    const logoutButton = page.getByText("Logout")
    await expect(logoutButton).toBeVisible()

    await logoutButton.click()
    await page.waitForURL("/login")
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible()
  })

  test("Accessing protected pages while unauthenticated redirects to login", async ({ page }) => {
    const mocks = setupAuthMocks(page)
    mocks.route(/\/auth\/me$/, (route) => {
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      })
    })
    await mocks.setup()

    await page.goto("/dashboard")
    await page.waitForURL(/\/login/)
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible()
  })

  test("Forgot password flow", async ({ page }) => {
    const forgotPage = new ForgotPasswordPage(page)
    const mocks = setupAuthMocks(page)
    await mocks.setup()

    await forgotPage.goto()
    await expect(page.getByRole("heading", { name: "Forgot Password" })).toBeVisible()

    await forgotPage.fillEmail("test@example.com")
    await forgotPage.submit()

    await expect(page.getByText("If that email exists, a reset link has been sent.")).toBeVisible()
  })

  test("Forgot password validation for invalid email", async ({ page }) => {
    const forgotPage = new ForgotPasswordPage(page)

    await forgotPage.goto()
    await forgotPage.fillEmail("not-an-email")
    await forgotPage.submit()

    await expect(page.getByText("Please enter a valid email address.")).toBeVisible()
  })

  test("Password reset flow", async ({ page }) => {
    const resetPage = new ResetPasswordPage(page)
    const mocks = setupAuthMocks(page)
    await mocks.setup()

    await resetPage.goto("valid-reset-token-abc123")
    await expect(page.getByRole("heading", { name: "Reset Password" })).toBeVisible()

    await resetPage.fillPassword("newSecurePass456")
    await resetPage.submit()

    await expect(page.getByText("Password reset successfully!")).toBeVisible()
    await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible()
  })

  test("Password reset with missing token shows error", async ({ page }) => {
    const resetPage = new ResetPasswordPage(page)
    const mocks = setupAuthMocks(page)
    await mocks.setup()

    await resetPage.goto("")
    await expect(page.getByText("Missing reset token")).toBeVisible()
  })

  test("Password reset with short password shows validation error", async ({ page }) => {
    const resetPage = new ResetPasswordPage(page)

    await resetPage.goto("some-token")
    await resetPage.fillPassword("short")
    await resetPage.submit()

    await expect(page.getByText("Password must be at least 8 characters")).toBeVisible()
  })

  test("Register page has link to sign in", async ({ page }) => {
    await page.goto("/register")
    const signInLink = page.getByRole("link", { name: "Sign In" })
    await expect(signInLink).toBeVisible()
    await expect(signInLink).toHaveAttribute("href", "/login")
  })

  test("Login page has link to register", async ({ page }) => {
    await page.goto("/login")
    const registerLink = page.getByRole("link", { name: "Register" })
    await expect(registerLink).toBeVisible()
    await expect(registerLink).toHaveAttribute("href", "/register")
  })

  test("Login page has link to forgot password", async ({ page }) => {
    await page.goto("/login")
    const forgotLink = page.getByRole("link", { name: "Forgot password?" })
    await expect(forgotLink).toBeVisible()
    await expect(forgotLink).toHaveAttribute("href", "/forgot-password")
  })
})
