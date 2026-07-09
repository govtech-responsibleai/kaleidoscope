import { test, expect } from "../fixtures/auth";
import { TARGET_ID, SNAPSHOT_ID, question, answer, completedQAJob } from "../fixtures/data";
// `answer` is used by the transient-503 retry test below.
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

  test("transient 503 on answer fetch is retried and does NOT show the error banner while evaluating", async ({ authedPage: page }) => {
    // A running (scoring) job so the hydrate effect fetches the answer.
    const scoringJob = {
      ...completedQAJob,
      status: JobStatus.RUNNING,
      stage: QAJobStageEnum.SCORING_ANSWERS,
    };

    // Keep the job list reporting "running" so the evaluation is considered active.
    await page.route(
      (url) =>
        new RegExp(`/api/v1/snapshots/${SNAPSHOT_ID}/qa-jobs$`).test(url.pathname) &&
        !url.pathname.includes("/start"),
      (route) => {
        if (route.request().method().toUpperCase() !== "GET") return void route.fallback();
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([scoringJob]),
        });
      },
    );

    // Return an empty snapshot answer list so the answer is NOT pre-cached — this
    // forces the hydrate effect to fetch GET /answers/{id} (where we inject 503s).
    await page.route(
      (url) => new RegExp(`/api/v1/snapshots/${SNAPSHOT_ID}/answers$`).test(url.pathname),
      (route) => {
        if (route.request().method().toUpperCase() !== "GET") return void route.fallback();
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ answers: [], total: 0 }),
        });
      },
    );

    // Fail the first two GET /answers/{id} calls with 503, then succeed.
    // This exercises the retry-with-backoff and the "don't alarm mid-run" banner rule.
    let answerCalls = 0;
    await page.route(
      (url) => new RegExp(`/api/v1/answers/${answer.id}$`).test(url.pathname),
      (route) => {
        if (route.request().method().toUpperCase() !== "GET") return void route.fallback();
        answerCalls += 1;
        if (answerCalls <= 2) {
          void route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Database temporarily unavailable. Please try again." }),
          });
          return;
        }
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(answer),
        });
      },
    );

    await page.goto(targetUrl(`/annotation?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");

    // Give the retry/backoff time to run through the two 503s and succeed.
    await expect
      .poll(() => answerCalls, { timeout: 10000 })
      .toBeGreaterThanOrEqual(3);

    // The misleading banner must NOT appear while the evaluation is running,
    // even though the answer GET failed transiently.
    await expect(page.getByText("Unable to load answers for this snapshot.")).toHaveCount(0);
  });

  test("an annotated answer deselected from the set stays deselected after reload", async ({ authedPage: page }) => {
    // Simulate post-save DB state: two approved questions, both answered and
    // annotated, but only the second is selected for annotation. The first was
    // deliberately deselected — it must NOT be auto-re-added on load.
    const secondQuestion = { ...question, id: question.id + 1, text: "What is the exchange policy?" };
    const deselectedAnswer = { ...answer, id: answer.id, is_selected_for_annotation: false, has_annotation: true };
    const selectedAnswer = {
      ...answer,
      id: answer.id + 1,
      question_id: secondQuestion.id,
      is_selected_for_annotation: true,
      has_annotation: true,
    };

    const secondJob = { ...completedQAJob, id: completedQAJob.id + 1, question_id: secondQuestion.id, answer_id: selectedAnswer.id };

    await page.route(
      (url) => /\/api\/v1\/targets\/\d+\/questions$/.test(url.pathname),
      (route) => {
        if (route.request().method().toUpperCase() !== "GET") return void route.fallback();
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: [question, secondQuestion], total: 2, skip: 0, limit: 250 }),
        });
      },
    );

    await page.route(
      (url) => new RegExp(`/api/v1/snapshots/${SNAPSHOT_ID}/answers$`).test(url.pathname),
      (route) => {
        if (route.request().method().toUpperCase() !== "GET") return void route.fallback();
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ answers: [deselectedAnswer, selectedAnswer], total: 2 }),
        });
      },
    );

    await page.route(
      (url) => new RegExp(`/api/v1/snapshots/${SNAPSHOT_ID}/qa-jobs$`).test(url.pathname) && !url.pathname.includes("/start"),
      (route) => {
        if (route.request().method().toUpperCase() !== "GET") return void route.fallback();
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([completedQAJob, secondJob]),
        });
      },
    );

    // The fix means the app must NOT re-select the deselected-but-annotated answer.
    let reselected = false;
    await page.route(
      (url) => new RegExp(`/api/v1/snapshots/${SNAPSHOT_ID}/answers/bulk-selection$`).test(url.pathname),
      (route) => {
        const payload = route.request().postDataJSON() as { selections?: { answer_id: number; is_selected: boolean }[] };
        if (payload?.selections?.some((s) => s.answer_id === deselectedAnswer.id && s.is_selected)) {
          reselected = true;
        }
        void route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      },
    );

    await page.goto(targetUrl(`/annotation?snapshot=${SNAPSHOT_ID}`));
    await page.waitForLoadState("networkidle");

    await expect(page.locator(`[data-testid="${TESTIDS.QA_LIST}"]`)).toBeVisible();

    // The deselected answer's checkbox must remain unchecked; the selected one checked.
    const deselectedRow = page.locator("li", { hasText: `${question.id}.` });
    const selectedRow = page.locator("li", { hasText: `${secondQuestion.id}.` });
    await expect(deselectedRow.getByRole("checkbox")).not.toBeChecked();
    await expect(selectedRow.getByRole("checkbox")).toBeChecked();

    // And no re-selecting bulk-selection call was issued for the deselected answer.
    expect(reselected).toBe(false);
  });
});
