import { test, expect } from "../fixtures/auth";
import { TARGET_ID, SNAPSHOT_ID } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

test.describe("Judges", () => {
  test("clicking judge add button opens CreateJudgeDialog with required fields", async ({ authedPage: page }) => {
    await page.goto(targetUrl(`/scoring?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");

    await page.locator(`[data-testid="${TESTIDS.JUDGE_ADD_BUTTON}"]`).first().click();

    await expect(page.getByLabel("Judge Name")).toBeVisible();
    await expect(page.getByLabel("Model Name")).toBeVisible();
    await expect(page.getByLabel("Temperature")).toBeVisible();
  });
});
