import { test as base, type Page, expect } from "@playwright/test";
import { setupApiMocks } from "../fixtures/api-mocks";
import { TARGET_ID, customRubricWithPrompt, snapshotMetricsResponse } from "../fixtures/data";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, use) => {
    await page.addInitScript(() => {
      localStorage.setItem("token", "fake-token-12345");
      localStorage.setItem("username", "testuser");
      localStorage.setItem("is_admin", "false");
    });
    await setupApiMocks(page, {
      [`GET /targets/${TARGET_ID}/rubrics`]: {
        body: [customRubricWithPrompt],
      },
    });
    await use(page);
  },
});

test.describe("Rubrics prompt editing (buffered field)", () => {
  test("edit prompt → Done → dirty dot visible → row Save persists", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("token", "fake-token-12345");
      localStorage.setItem("username", "testuser");
      localStorage.setItem("is_admin", "false");
    });
    await setupApiMocks(page, {
      [`GET /targets/${TARGET_ID}/rubrics`]: {
        body: [customRubricWithPrompt],
      },
      [`PUT /targets/${TARGET_ID}/rubrics/${customRubricWithPrompt.id}`]: {
        body: { ...customRubricWithPrompt, judge_prompt: "Modified prompt text" },
      },
    });

    const metricsLoaded = page.waitForResponse((response) => (
      response.url().includes(`/targets/${TARGET_ID}/snapshot-metrics`) && response.status() === 200
    ));
    await page.goto(targetUrl("/rubrics"));
    await metricsLoaded;
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByText("Customize prompt").click();

    // Edit prompt in the editor
    const editor = page.locator(".cm-editor .cm-content");
    await editor.fill("Modified prompt text");

    // Click Done — should buffer and close dialog
    await page.getByRole("button", { name: "Done" }).click();
    await expect(page.locator("[role=dialog]")).not.toBeVisible();

    // Row Save should be enabled (prompt change made it dirty)
    const rowSave = page.getByRole("button", { name: "Save" });
    await expect(rowSave).toBeEnabled();
    const updateRequest = page.waitForRequest((request) => (
      request.method() === "PUT"
      && request.url().includes(`/targets/${TARGET_ID}/rubrics/${customRubricWithPrompt.id}`)
      && request.postDataJSON().judge_prompt === "Modified prompt text"
    ));
    await rowSave.click();
    await updateRequest;

    // After save, row should collapse (editing ends)
    await expect(rowSave).not.toBeVisible();
  });

  test("edit prompt → Done → row Cancel reverts prompt", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByText("Customize prompt").click();

    const editor = page.locator(".cm-editor .cm-content");
    await editor.fill("Some edits");

    await page.getByRole("button", { name: "Done" }).click();
    await expect(page.getByText("Modified")).toBeVisible();

    // Cancel the rubric row edit
    await page.getByRole("button", { name: "Cancel" }).first().click();

    // Re-expand — prompt should be reverted (no Modified badge)
    await page.getByRole("button", { name: "Edit" }).first().click();
    await expect(page.getByText("Modified")).not.toBeVisible();
  });

  test("used rubric → edit prompt → row Save shows reset-data warning", async ({ page }) => {
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
        body: {
          ...snapshotMetricsResponse,
          rubrics: [
            {
              rubric_id: customRubricWithPrompt.id,
              rubric_name: customRubricWithPrompt.name,
              group: customRubricWithPrompt.group,
              snapshots: [
                {
                  snapshot_id: 1,
                  snapshot_name: "Snapshot 1",
                  created_at: customRubricWithPrompt.created_at,
                  rubric_id: customRubricWithPrompt.id,
                  rubric_name: customRubricWithPrompt.name,
                  aggregated_score: 0.8,
                  total_answers: 5,
                  accurate_count: 4,
                  inaccurate_count: 1,
                  pending_count: 0,
                  edited_count: 0,
                  judge_alignment_range: null,
                  aligned_judges: [],
                },
              ],
            },
          ],
        },
      },
    });

    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByText("Customize prompt").click();

    await page.locator(".cm-editor .cm-content").fill("Modified prompt text");
    await page.getByRole("button", { name: "Done" }).click();

    // Row Save should trigger the warning
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Save Rubric and Reset Related Data")).toBeVisible();
  });
});
