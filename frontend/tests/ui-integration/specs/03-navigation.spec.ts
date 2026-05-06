import { test, expect } from "../fixtures/auth";
import { setupApiMocks } from "../fixtures/api-mocks";
import { TARGET_ID, SNAPSHOT_ID, scoringStatusIncomplete } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

test.describe("Target navigation", () => {
  test("overview page shows target name in breadcrumb", async ({ authedPage: page }) => {
    await page.goto(targetUrl());
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Test Target")).toBeVisible();
    // "Targets" text appears in breadcrumb — exact match to avoid "All Targets" nav item
    await expect(page.getByText("Targets", { exact: true })).toBeVisible();
  });

  test("rubrics page shows fixed accuracy rubric", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/rubrics"));
    await page.waitForLoadState("networkidle");
    // Fixed group heading
    await expect(page.getByText("Fixed")).toBeVisible();
    // Accuracy rubric row
    await expect(page.getByText("Accuracy")).toBeVisible();
  });

  test("annotations page shows snapshot and QA list", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/annotation"));
    await page.waitForLoadState("networkidle");
    // Snapshot 1 should appear in the page (either as select value or as menu item)
    await expect(page.getByText("Snapshot 1")).toBeVisible({ timeout: 10000 });
    // QA list container is present
    await expect(page.locator(`[data-testid="${TESTIDS.QA_LIST}"]`)).toBeVisible();
  });

  test("scoring page shows incomplete-annotations alert", async ({ authedPage: page }) => {
    await setupApiMocks(page, {
      [`GET /snapshots/${SNAPSHOT_ID}/scoring-status`]: {
        body: scoringStatusIncomplete,
      },
    });
    await page.goto(targetUrl(`/scoring?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");
    // Filter out Next.js route announcer which also has role="alert"
    await expect(
      page.getByRole("alert").filter({ hasText: "Complete all" })
    ).toBeVisible();
  });

  test("scoring page shows gauge, judges, and results when complete", async ({ authedPage: page }) => {
    await page.goto(targetUrl(`/scoring?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");
    await expect(page.locator(`[data-testid="${TESTIDS.SCORE_GAUGE}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="${TESTIDS.JUDGE_LIST}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="${TESTIDS.RESULTS_TABLE}"]`)).toBeVisible();
  });

  test("report page shows summary cards and chart", async ({ authedPage: page }) => {
    await page.goto(targetUrl("/report"));
    await page.waitForLoadState("networkidle");
    await expect(page.locator(`[data-testid="${TESTIDS.SUMMARY_CARD("approved-personas")}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="${TESTIDS.SUMMARY_CARD("approved-questions")}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="${TESTIDS.SUMMARY_CARD("snapshots")}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="${TESTIDS.SUMMARY_CARD("judges")}"]`)).toBeVisible();
    await expect(page.locator(`[data-testid="${TESTIDS.SNAPSHOT_SCORE_CHART}"]`)).toBeVisible();
  });
});
