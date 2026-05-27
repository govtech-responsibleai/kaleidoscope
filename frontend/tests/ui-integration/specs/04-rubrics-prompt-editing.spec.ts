import { test as base, type Page, expect } from "@playwright/test";
import { setupApiMocks } from "../fixtures/api-mocks";
import { TARGET_ID, completedQAJob, customRubricWithPrompt, snapshotMetricsResponse } from "../fixtures/data";

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

test.describe("Rubrics prompt editing", () => {
  test("edit text and save persists new prompt", async ({ page }) => {
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

    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();

    await page.getByText("Customize prompt").click();
    await expect(page.getByText("Tone of Voice: Judge Prompt")).toBeVisible();

    const editor = page.locator(".cm-editor");
    await expect(editor).toBeVisible();

    await editor.locator(".cm-content").fill("Modified prompt text");

    const saveBtn = page.locator("[role=dialog]").getByRole("button", { name: "Save" });
    await expect(saveBtn).toBeEnabled();
    await saveBtn.click();

    await expect(page.getByText("Tone of Voice: Judge Prompt")).not.toBeVisible();

    await page.getByText("Customize prompt").click();
    await expect(page.locator(".cm-editor")).toContainText("Modified prompt text");
  });

  test("saving prompt for a used rubric shows reset-data warning", async ({ page }) => {
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

    const editor = page.locator(".cm-editor .cm-content");
    await editor.fill("Modified prompt text");

    await page.locator("[role=dialog]").getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Save Rubric and Reset Related Data")).toBeVisible();
    await expect(page.getByText("Saving this rubric will delete all data related to it.")).toBeVisible();
  });

  test("saving prompt for a rubric with running jobs shows wait error", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("token", "fake-token-12345");
      localStorage.setItem("username", "testuser");
      localStorage.setItem("is_admin", "false");
    });
    await setupApiMocks(page, {
      [`GET /targets/${TARGET_ID}/rubrics`]: {
        body: [customRubricWithPrompt],
      },
      "GET /snapshots/{id}/qa-jobs": {
        body: [
          {
            ...completedQAJob,
            status: "running",
            rubric_specs: [{ rubric_id: customRubricWithPrompt.id, judge_id: completedQAJob.judge_id }],
          },
        ],
      },
    });

    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByText("Customize prompt").click();

    await page.locator(".cm-editor .cm-content").fill("Modified prompt text");
    await page.locator("[role=dialog]").getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Wait for related evaluations to finish before editing this rubric.")).toBeVisible();
  });

  test("copy prompt uses unsaved editor content", async ({ authedPage: page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", {
        value: {
          writeText: async (text: string) => {
            (window as unknown as { copiedPromptText: string }).copiedPromptText = text;
          },
        },
      });
    });

    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByText("Customize prompt").click();

    await page.locator(".cm-editor .cm-content").fill("Unsaved prompt text");
    await page.locator("[role=dialog]").getByRole("button", { name: "Copy prompt" }).click();

    await expect.poll(() => page.evaluate(() => (
      window as unknown as { copiedPromptText?: string }
    ).copiedPromptText)).toBe("Unsaved prompt text");
  });

  test("cancel with dirty changes shows confirm dialog", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByText("Customize prompt").click();

    const editor = page.locator(".cm-editor .cm-content");
    await editor.fill("Some edits");

    let dialogFired = false;
    page.on("dialog", (dialog) => {
      dialogFired = true;
      dialog.dismiss();
    });

    await page.locator("[role=dialog]").getByRole("button", { name: "Cancel" }).click();

    expect(dialogFired).toBe(true);
    await expect(page.getByText("Tone of Voice: Judge Prompt")).toBeVisible();
  });
});
