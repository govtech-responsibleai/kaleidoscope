import { test, expect } from "../fixtures/auth";
import { TARGET_ID, answer, customRubricWithPrompt } from "../fixtures/data";
import { setupApiMocks } from "../fixtures/api-mocks";
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

  test("editing a rubric with annotations shows reset-data warning", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("token", "fake-token-12345");
      localStorage.setItem("username", "testuser");
      localStorage.setItem("is_admin", "false");
    });
    await setupApiMocks(page, {
      [`GET /targets/${TARGET_ID}/rubrics`]: {
        body: [customRubricWithPrompt],
      },
      [`GET /targets/${TARGET_ID}/snapshot-metrics`]: {
        body: { target_id: TARGET_ID, rubrics: [] },
      },
      "GET /snapshots/{id}/qa-jobs": {
        body: [],
      },
      "GET /snapshots/{id}/annotations": {
        body: {
          answers: [
            {
              answer_id: answer.id,
              annotations: [
                {
                  id: 1,
                  answer_id: answer.id,
                  rubric_id: customRubricWithPrompt.id,
                  option_value: customRubricWithPrompt.best_option,
                  notes: null,
                  created_at: customRubricWithPrompt.created_at,
                  updated_at: customRubricWithPrompt.updated_at,
                },
              ],
            },
          ],
          total_answers: 1,
          total_annotations: 1,
        },
      },
    });

    const annotationsLoaded = page.waitForResponse((response) => (
      response.url().includes("/snapshots/")
      && response.url().includes("/annotations")
      && response.status() === 200
    ));
    await page.goto(targetUrl("/rubrics"));
    await annotationsLoaded;
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByPlaceholder("Describe your evaluation criteria").fill("Updated tone criteria");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Save Rubric and Reset Related Data")).toBeVisible();
  });
});
