import { test, expect } from "../fixtures/auth";
import { TARGET_ID, persona, personaJob } from "../fixtures/data";
import { TESTIDS } from "../fixtures/testids";
import { mockJobLifecycle, mockJobPersonas } from "../fixtures/job-mocks";
import { JobStatus } from "@/lib/types";

const targetUrl = (path = "") => `/targets/${TARGET_ID}${path}`;

test.describe("Persona generation", () => {
  test("trigger generation via AI, mock job lifecycle, personas render", async ({ authedPage: page }) => {
    await mockJobLifecycle(page, personaJob.id, [
      { ...personaJob, status: JobStatus.COMPLETED },
    ]);
    await mockJobPersonas(page, personaJob.id, [persona]);

    await page.goto(targetUrl("/questions"));
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Add Questions" }).click();
    await page.locator(`[data-testid="${TESTIDS.GENERATE_EVALS_CARD_GENERATE}"]`).click();
    await page.getByRole("button", { name: "Generate New Personas" }).click();
    await page.getByText("Generate with AI").click();

    await expect(page.getByText(persona.title)).toBeVisible({ timeout: 15000 });
  });
});
