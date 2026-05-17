import { test, expect } from "../fixtures/auth";
import { TARGET_ID } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

// Walks the "Add Questions → Generate → Use Existing Personas" flow, which
// renders the multi-language picker in the Generation Settings row.
async function openUseExistingPersonas(page: import("@playwright/test").Page) {
  await page.goto(targetUrl("/questions"));
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Add Questions" }).click();
  await page.locator(`[data-testid="${TESTIDS.GENERATE_EVALS_CARD_GENERATE}"]`).click();
  await page.getByRole("button", { name: "Use Existing Personas" }).click();
}

test.describe("Multilingual eval-set generation", () => {
  test("language picker is visible and defaults to English", async ({ authedPage: page }) => {
    await openUseExistingPersonas(page);

    await expect(page.getByLabel("Languages")).toBeVisible();
    // The default selection renders as an "English" chip.
    await expect(page.getByRole("dialog").getByText("English", { exact: true })).toBeVisible();
  });

  test("selecting an extra language sends both in the create-job request", async ({ authedPage: page }) => {
    await openUseExistingPersonas(page);

    // Select the one existing (approved) persona.
    await page.getByText("Power User").click();

    // Add a second language from the dropdown, then dismiss it via the footer's "Done" button.
    await page.getByLabel("Languages").click();
    await page.getByRole("option", { name: "French" }).click();
    await page.getByRole("button", { name: "Done" }).click();

    const requestPromise = page.waitForRequest(
      (req) => req.url().includes("/jobs/questions") && req.method() === "POST"
    );
    await page.getByRole("button", { name: /Generate \d+ Questions/ }).click();
    const request = await requestPromise;

    const body = request.postDataJSON();
    expect(body.languages).toContain("English");
    expect(body.languages).toContain("French");
  });

  test("less common languages live in the single scrollable list and Done dismisses it", async ({ authedPage: page }) => {
    await openUseExistingPersonas(page);

    await page.getByLabel("Languages").click();

    // Every supported language lives in one scrollable list — no separate "Other" step.
    // Playwright auto-scrolls the option into view before clicking.
    await page.getByRole("option", { name: "Malay", exact: true }).click();

    // The multi-select stays open between picks; the sticky footer's "Done" button dismisses it.
    await page.getByRole("button", { name: "Done" }).click();
    await expect(page.getByRole("option", { name: "Malay", exact: true })).not.toBeVisible();

    // The chosen language remains as a chip in the picker.
    await expect(page.getByRole("dialog").getByText("Malay", { exact: true })).toBeVisible();
  });
});
