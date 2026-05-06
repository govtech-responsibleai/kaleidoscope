import { test, expect } from "../fixtures/auth";
import { TARGET_ID, SNAPSHOT_ID, completedQAJob } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";
import { JobStatus, QAJobStageEnum } from "@/lib/types";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

const runningQaJob = {
  ...completedQAJob,
  status: JobStatus.RUNNING,
  stage: QAJobStageEnum.GENERATING_ANSWERS,
};

test.describe("Annotation run", () => {
  test("clicking qa-job-control-button triggers evaluation, button text transitions, QA list populates", async ({ authedPage: page }) => {
    let started = false;
    let pollCount = 0;

    // Override POST start to return running job and flip the trigger
    await page.route(
      (url) => new RegExp(`/api/v1/snapshots/${SNAPSHOT_ID}/qa-jobs/start$`).test(url.pathname),
      (route) => {
        started = true;
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([runningQaJob]),
        });
      },
    );

    // Override GET qa-jobs: before POST → fallback to default mock; after POST → lifecycle
    await page.route(
      (url) =>
        new RegExp(`/api/v1/snapshots/${SNAPSHOT_ID}/qa-jobs$`).test(url.pathname) &&
        !url.pathname.includes("/start"),
      (route) => {
        if (route.request().method().toUpperCase() !== "GET") {
          void route.fallback();
          return;
        }
        if (!started) {
          void route.fallback();
          return;
        }
        const response = pollCount++ === 0 ? [runningQaJob] : [completedQAJob];
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(response),
        });
      },
    );

    await page.goto(targetUrl(`/annotation?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");

    const button = page.locator(`[data-testid="${TESTIDS.QA_JOB_CONTROL_BUTTON}"]`);
    await expect(button).toBeVisible();
    // Wait for initial load: button shows non-running text (not "Evaluating")
    await expect(button).not.toHaveText(/Evaluating/, { timeout: 15000 });
    await expect(button).toBeEnabled();

    // Click and wait for POST to confirm hydration processed the click
    const postResponse = page.waitForResponse(
      (resp) => resp.url().includes("/qa-jobs/start") && resp.status() === 200,
    );
    await button.click();
    await postResponse;

    // Running state: button shows "Evaluating: X/Y"
    await expect(button).toHaveText(/Evaluating/, { timeout: 10000 });

    // After polling completes: button exits evaluating state
    await expect(button).not.toHaveText(/Evaluating/, { timeout: 15000 });

    // QA list should be visible with populated content
    await expect(page.locator(`[data-testid="${TESTIDS.QA_LIST}"]`)).toBeVisible();
  });
});
