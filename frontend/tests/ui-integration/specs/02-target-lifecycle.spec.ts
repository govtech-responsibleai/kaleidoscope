import { test, expect } from "../fixtures/auth";

test.describe("Target lifecycle", () => {
  test("create target via wizard adds card to list", async ({ authedPage: page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Open modal
    await page.getByRole("button", { name: "New Target" }).click();
    await expect(page.getByText("Create new target application")).toBeVisible({ timeout: 10000 });

    // Step 1 — fill required fields
    await page.getByLabel("Name").fill("Test Target");
    await page.getByLabel("Agency").fill("Test Agency");

    // Wait for connector types to load and fill URL field
    await page.getByLabel("API Endpoint URL").fill("https://example.com/api");

    await page.getByRole("button", { name: "Next", exact: true }).click();

    // Step 2 — no KB files, click create
    await page.getByRole("button", { name: "Create Without Documents" }).click();

    // Modal closes and target card appears
    await expect(page.getByText("Create new target application")).not.toBeVisible();
    await expect(page.getByText("Test Target")).toBeVisible();
  });
});
