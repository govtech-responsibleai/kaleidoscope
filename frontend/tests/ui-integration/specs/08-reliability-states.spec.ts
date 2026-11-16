import { test as base, type Page, expect } from "@playwright/test";
import { setupApiMocks } from "../fixtures/api-mocks";
import {
  SNAPSHOT_ID,
  TARGET_ID,
  scoringContractInsufficientCalibration,
  scoringContractJudgesUnscored,
} from "../fixtures/data";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

const test = base.extend<{ calibratingPage: Page; unscoredJudgePage: Page }>({
  calibratingPage: async ({ page }, use) => {
    await page.addInitScript(() => {
      localStorage.setItem("token", "fake-token-12345");
      localStorage.setItem("username", "testuser");
      localStorage.setItem("is_admin", "false");
    });
    await setupApiMocks(page, {
      "GET /snapshots/{id}/results": { body: scoringContractInsufficientCalibration },
      "GET /snapshots/{id}/rubrics/{rubricId}/scoring-results": { body: scoringContractInsufficientCalibration },
    });
    await use(page);
  },
  unscoredJudgePage: async ({ page }, use) => {
    await page.addInitScript(() => {
      localStorage.setItem("token", "fake-token-12345");
      localStorage.setItem("username", "testuser");
      localStorage.setItem("is_admin", "false");
    });
    await setupApiMocks(page, {
      "GET /snapshots/{id}/results": { body: scoringContractJudgesUnscored },
      "GET /snapshots/{id}/rubrics/{rubricId}/scoring-results": { body: scoringContractJudgesUnscored },
    });
    await use(page);
  },
});

test.describe("Reliability states", () => {
  test("a judge still calibrating shows its progress and its reliability so far", async ({ calibratingPage: page }) => {
    await page.goto(targetUrl(`/scoring?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/Not calibrated — 12 of 20 labels/).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/62% so far/).first()).toBeVisible();
  });

  test("labels exist but the judge has not scored them yet: the tile and the judge card agree", async ({ unscoredJudgePage: page }) => {
    await page.goto(targetUrl(`/scoring?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/has not scored the 25 labelled responses yet/).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/have not yet scored enough of the 25 labelled responses/).first()).toBeVisible();
  });
});
