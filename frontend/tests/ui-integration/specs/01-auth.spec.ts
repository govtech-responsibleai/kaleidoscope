import { test, expect } from "@playwright/test";
import { setupApiMocks } from "../fixtures/api-mocks";

test.describe("Authentication", () => {
  test("successful login redirects to home", async ({ page }) => {
    await setupApiMocks(page);
    await page.goto("/login");

    await page.getByLabel("Username").fill("testuser");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(page).toHaveURL("/");
  });

  test("failed login shows error alert", async ({ page }) => {
    await setupApiMocks(page, {
      "POST /auth/login": { status: 401, body: { detail: "Incorrect username or password" } },
    });
    await page.goto("/login");

    await page.getByLabel("Username").fill("baduser");
    await page.getByLabel("Password").fill("wrongpass");
    await page.getByRole("button", { name: "Sign In" }).click();

    // Filter out Next.js route announcer which also has role="alert"
    await expect(
      page.getByRole("alert").filter({ hasText: "Invalid username or password" })
    ).toBeVisible();
    await expect(page).toHaveURL("/login");
  });
});
