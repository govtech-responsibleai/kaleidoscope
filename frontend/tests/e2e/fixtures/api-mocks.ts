import type { Page, Route } from "@playwright/test";
import * as data from "./data";

type MockOverride = { status?: number; body: unknown };
type Overrides = Record<string, MockOverride>;

// Routes `**/api/v1/**` to canned responses. Pass `overrides` to replace specific
// endpoints: key is "METHOD /path-suffix" (e.g. "POST /auth/login").
export async function setupApiMocks(page: Page, overrides: Overrides = {}) {
  await page.route("**/api/v1/**", (route: Route) => {
    const url = new URL(route.request().url());
    const method = route.request().method().toUpperCase();
    const path = url.pathname.replace(/.*\/api\/v1/, "");
    const key = findOverrideKey(method, path, overrides);
    if (key) {
      const override = overrides[key];
      return route.fulfill({
        status: override.status ?? 200,
        contentType: "application/json",
        body: JSON.stringify(override.body),
      });
    }

    const response = defaultResponse(method, path);
    if (response) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(response),
      });
    }

    // Unmatched — return empty 200 so the app doesn't throw
    return route.fulfill({ status: 200, contentType: "application/json", body: "null" });
  });
}

function findOverrideKey(method: string, path: string, overrides: Overrides): string | null {
  for (const key of Object.keys(overrides)) {
    const [m, ...rest] = key.split(" ");
    const pattern = rest.join(" ");
    if (m === method && pathMatches(path, pattern)) return key;
  }
  return null;
}

function pathMatches(path: string, pattern: string): boolean {
  // Support simple glob: /targets/{id} -> /targets/1
  const regex = new RegExp("^" + pattern.replace(/\{[^}]+\}/g, "[^/]+") + "(/.*)?$");
  return regex.test(path);
}

function defaultResponse(method: string, path: string): unknown {
  // Auth
  if (method === "POST" && path === "/auth/login") {
    return { access_token: "fake-token-12345", token_type: "bearer" };
  }

  // Targets
  if (method === "GET" && path === "/targets") return [data.target];
  if (method === "GET" && path === "/targets/connector-types") return ["openai", "http"];
  if (method === "GET" && pathMatches(path, "/targets/{id}") && !path.includes("/rubrics") && !path.includes("/snapshots") && !path.includes("/stats") && !path.includes("/questions") && !path.includes("/personas") && !path.includes("/premade") && !path.includes("/rubric-specs") && !path.includes("/web") && !path.includes("/knowledge") && !path.includes("/snapshot-metrics") && !path.includes("/confusion-matrix")) return data.target;
  if (method === "POST" && path === "/targets") return data.target;
  if (method === "GET" && pathMatches(path, "/targets/{id}/stats")) return data.targetStats;
  if (method === "GET" && pathMatches(path, "/targets/{id}/rubric-specs")) return {};

  // Providers
  if (method === "GET" && path === "/providers/setup") return data.providerSetupResponse;

  // Web docs (fire and forget on target create)
  if (method === "POST" && pathMatches(path, "/targets/{id}/web-search")) return { status: "started" };
  if (method === "GET" && pathMatches(path, "/targets/{id}/web-documents")) return { documents: [] };

  // Rubrics
  if (method === "GET" && pathMatches(path, "/targets/{id}/rubrics")) return [data.accuracyRubric];
  if (method === "POST" && pathMatches(path, "/targets/{id}/rubrics")) return { ...data.accuracyRubric, id: 999, name: "Completeness", group: "preset" };
  if (method === "GET" && pathMatches(path, "/targets/{id}/premade-rubrics")) return [data.premadeTemplate];

  // Snapshots
  if (method === "GET" && pathMatches(path, "/targets/{id}/snapshots")) return [data.snapshot];
  if (method === "POST" && path === "/snapshots") return data.snapshot;
  if (method === "GET" && pathMatches(path, "/snapshots/{id}") && !path.includes("/stats") && !path.includes("/answers") && !path.includes("/questions") && !path.includes("/qa-jobs") && !path.includes("/results") && !path.includes("/scoring")) return data.snapshot;
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/stats")) return data.snapshotStats;

  // Personas
  if (method === "GET" && pathMatches(path, "/targets/{id}/personas")) return [data.persona];
  if (method === "POST" && path === "/personas") return data.persona;
  if (method === "POST" && path === "/personas/sample-nemotron") return { job_id: data.personaJob.id };
  if (method === "POST" && path === "/personas/bulk-approve") return { approved: 1 };

  // Questions
  if (method === "GET" && pathMatches(path, "/targets/{id}/questions")) return data.questionListResponse;
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/questions/approved/without-answers")) return [data.question];
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/questions/approved/without-scores")) return [];

  // Jobs
  if (method === "POST" && path === "/jobs/personas") return { id: data.personaJob.id };
  if (method === "POST" && path === "/jobs/questions") return { id: 98 };
  if (method === "GET" && pathMatches(path, "/jobs/{id}")) return data.personaJob;

  // Answers
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/answers")) return data.answerListResponse;
  if (method === "POST" && pathMatches(path, "/snapshots/{id}/answers/select-default")) return { selected: 1 };

  // QA jobs
  if (method === "POST" && pathMatches(path, "/snapshots/{id}/qa-jobs/start")) return { started: 1 };
  if (method === "POST" && path === "/qa-jobs/pause") return { paused: 1 };
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/qa-jobs")) return [data.completedQAJob];
  if (method === "GET" && pathMatches(path, "/qa-jobs/{id}")) return data.completedQAJob;

  // Judges
  if (method === "GET" && path === "/judges/available-models") return [data.judgeModelOption];
  if (method === "GET" && pathMatches(path, "/judges/by-rubric/{rubricId}")) return [data.judge];
  if (method === "POST" && path === "/judges") return data.judge;
  if (method === "POST" && path === "/judges/seed") return [data.judge];

  // Scoring / metrics
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/scoring-status")) return data.scoringStatusComplete;
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/scoring-rubrics")) return data.scoringRubricsResponse;
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/results")) return data.scoringResultsResponse;
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/rubrics/{rubricId}/scoring-results")) return data.scoringResultsResponse;
  if (method === "GET" && pathMatches(path, "/snapshots/{id}/rubrics/{rubricId}/scoring-pending-counts")) return { pending_counts: {} };
  if (method === "GET" && pathMatches(path, "/targets/{id}/snapshot-metrics")) return data.snapshotMetricsResponse;
  if (method === "GET" && pathMatches(path, "/targets/{id}/confusion-matrix")) return { matrix: { typical_in_kb: 0, typical_out_kb: 0, edge_in_kb: 0, edge_out_kb: 0 }, total_inaccurate: 0 };

  return null;
}
