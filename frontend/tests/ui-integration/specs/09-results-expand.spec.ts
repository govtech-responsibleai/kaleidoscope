import { test, expect } from "../fixtures/auth";
import {
  TARGET_ID,
  SNAPSHOT_ID,
  RUBRIC_ID,
  JUDGE_ID,
  accuracyRubric,
  judge,
  answer,
  scoringResultsResponse,
} from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

const claimBasedRubric = { ...accuracyRubric, scoring_mode: "claim_based" as const };

const claimBasedScoringRubricsResponse = {
  snapshot_id: SNAPSHOT_ID,
  rubrics: [{ ...claimBasedRubric, judges: [judge] }],
};

const claimsResponse = {
  answer_id: answer.id,
  claims: [
    {
      id: 1,
      answer_id: answer.id,
      claim_text: "returns within 30 days",
      claim_index: 0,
      checkworthy: true,
      created_at: "2026-04-28T12:00:00Z",
    },
  ],
};

test.describe("Results expand row", () => {
  test("scoring-done state with claim-based rubric, click row toggle, claim highlighter renders", async ({ authedPage: page }) => {
    // Override scoring-rubrics to return claim-based rubric
    await page.route(
      (url) => /\/api\/v1\/snapshots\/\d+\/scoring-rubrics/.test(url.pathname),
      (route) =>
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(claimBasedScoringRubricsResponse),
        }),
    );

    // Override claims endpoint to return test claims
    await page.route(
      (url) => /\/api\/v1\/answers\/\d+\/claims/.test(url.pathname),
      (route) =>
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(claimsResponse),
        }),
    );

    // Override rubric-scores endpoint (non-essential, prevent error)
    await page.route(
      (url) => /\/api\/v1\/answers\/\d+\/rubric-scores/.test(url.pathname),
      (route) =>
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        }),
    );

    await page.goto(targetUrl(`/scoring?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");

    // Results table should be visible
    await expect(page.locator(`[data-testid="${TESTIDS.RESULTS_TABLE}"]`)).toBeVisible({ timeout: 10000 });

    // Click row toggle to expand
    await page.locator(`[data-testid="${TESTIDS.RESULTS_TABLE_ROW_TOGGLE}"]`).first().click();

    // Claim highlighter renders: claim text visible in expanded row
    await expect(page.getByText("returns within 30 days", { exact: true })).toBeVisible({ timeout: 10000 });
  });
});
