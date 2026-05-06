import type { Page } from "@playwright/test";

// Deterministic state machine for GET /jobs/{jobId}.
// Each successive call advances to the next state, staying on the last once exhausted.
export async function mockJobLifecycle(page: Page, jobId: number, states: unknown[]) {
  let callCount = 0;
  await page.route(
    (url) => /\/api\/v1\/jobs\/(\d+)$/.test(url.pathname) && url.pathname.endsWith(`/${jobId}`),
    (route) => {
      const idx = Math.min(callCount++, states.length - 1);
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(states[idx]),
      });
    },
  );
}

// Mock GET /jobs/{jobId}/personas to return a fixed list.
export async function mockJobPersonas(page: Page, jobId: number, personas: unknown[]) {
  await page.route(
    (url) => url.pathname.endsWith(`/api/v1/jobs/${jobId}/personas`),
    (route) =>
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(personas),
      }),
  );
}

// Deterministic state machine for GET /snapshots/{snapshotId}/qa-jobs.
// Each successive GET advances to the next state; non-GET requests fall through.
export async function mockQAJobsLifecycle(
  page: Page,
  snapshotId: number,
  states: unknown[][],
) {
  let callCount = 0;
  await page.route(
    (url) => new RegExp(`/api/v1/snapshots/${snapshotId}/qa-jobs$`).test(url.pathname),
    (route) => {
      if (route.request().method().toUpperCase() !== "GET") {
        void route.continue();
        return;
      }
      const idx = Math.min(callCount++, states.length - 1);
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(states[idx]),
      });
    },
  );
}
