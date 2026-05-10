import { test, expect } from "../fixtures/auth";
import { TARGET_ID, SNAPSHOT_ID } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";

const scoringUrl = `/targets/${TARGET_ID}/scoring?snapshot=${SNAPSHOT_ID}`;

test.describe("Judge Prompt Editor", () => {
  test("prompt editor renders with CodeMirror and accepts input", async ({ authedPage: page }) => {
    await page.goto(scoringUrl);
    await page.waitForLoadState("networkidle");

    await page.locator(`[data-testid="${TESTIDS.JUDGE_ADD_BUTTON}"]`).first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Customize prompt" }).click();

    const editor = dialog.locator(".cm-editor");
    await expect(editor).toBeVisible();
    await expect(editor.locator(".cm-gutters")).toBeVisible();

    const content = editor.locator(".cm-content");
    await content.click();
    await page.keyboard.type("Score the {{ response }} based on {{ rubric }}");

    const text = await content.textContent();
    expect(text).toContain("{{ response }}");
    expect(text).toContain("{{ rubric }}");
  });

  test("submitting dialog sends prompt_template in request body", async ({ authedPage: page }) => {
    const promptText = "Evaluate {{ response }} for correctness.";
    let capturedBody: Record<string, unknown> | null = null;

    await page.route("**/api/v1/judges", async (route) => {
      if (route.request().method() === "POST") {
        capturedBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: 999, name: "Test", model_name: "openai/gpt-4o", model_label: "GPT-4o", temperature: 1.0, is_baseline: false, is_editable: true, params: {}, target_id: TARGET_ID, rubric_id: 100, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(scoringUrl);
    await page.waitForLoadState("networkidle");

    await page.locator(`[data-testid="${TESTIDS.JUDGE_ADD_BUTTON}"]`).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Customize prompt" }).click();

    const content = dialog.locator(".cm-content");
    await content.click();
    await page.keyboard.press("Meta+a");
    await page.keyboard.type(promptText);

    await dialog.getByRole("button", { name: "Create" }).click();

    await expect.poll(() => capturedBody !== null).toBeTruthy();
    expect(capturedBody!.prompt_template).toBe(promptText);
  });
});
