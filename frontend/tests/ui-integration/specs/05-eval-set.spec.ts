import { test, expect } from "../fixtures/auth";
import { TARGET_ID } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

test.describe("Evaluation set page", () => {
  test("clicking Add Questions opens modal with two mode cards", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/questions"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Add Questions" }).click();

    await expect(page.locator(`[data-testid="${TESTIDS.GENERATE_EVALS_CARD_GENERATE}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="${TESTIDS.GENERATE_EVALS_CARD_UPLOAD}"]`)).toBeVisible();
  });

  test("Generate card → Generate New Personas shows 3 PersonaSelect cards", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/questions"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Add Questions" }).click();
    await page.locator(`[data-testid="${TESTIDS.GENERATE_EVALS_CARD_GENERATE}"]`).click();
    await page.getByRole("button", { name: "Generate New Personas" }).click();

    await expect(page.getByText("Generate with AI")).toBeVisible();
    await expect(page.getByText("Random Personas")).toBeVisible();
    await expect(page.getByText("Add Manually")).toBeVisible();
  });

  test("Upload card → Type Questions shows textarea", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/questions"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Add Questions" }).click();
    await page.locator(`[data-testid="${TESTIDS.GENERATE_EVALS_CARD_UPLOAD}"]`).click();
    await page.getByRole("button", { name: "Type Questions" }).click();

    await expect(page.getByPlaceholder(/What are the leave policies/)).toBeVisible();
  });

  test("Manage Personas tab → Add Personas opens modal with 3 PersonaSelect cards", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/questions"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("tab", { name: "Manage Personas" }).click();
    await expect(page.getByRole("button", { name: "Add Personas" })).toBeVisible();
    await page.getByRole("button", { name: "Add Personas" }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Add Personas" })).toBeVisible();
    await expect(dialog.getByText("Generate with AI")).toBeVisible();
    await expect(dialog.getByText("Random Personas")).toBeVisible();
    await expect(dialog.getByText("Add Manually")).toBeVisible();
  });
});
