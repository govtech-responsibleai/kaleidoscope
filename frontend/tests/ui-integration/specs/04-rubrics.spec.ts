import { test, expect } from "../fixtures/auth";
import { TARGET_ID } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

test.describe("Rubrics page", () => {
  test("clicking custom add creates an editable accordion row", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    await page.locator(`[data-testid="${TESTIDS.RUBRIC_CUSTOM_ADD}"]`).click();

    await expect(page.getByPlaceholder("Untitled rubric")).toBeVisible();
  });

  test("clicking preset card in sidebar adds a preset row to the main list", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    // Sidebar preset list is always visible — click card directly
    await page.locator(`[data-testid="${TESTIDS.PRESET_RUBRIC_CARD("completeness")}"]`).click();

    await expect(page.getByText("Completeness").first()).toBeVisible();
  });
});
