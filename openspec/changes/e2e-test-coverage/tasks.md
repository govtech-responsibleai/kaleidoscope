## 1. PR1 — Shared Infrastructure

- [x] 1.1 Create `frontend/tests/ui-integration/fixtures/testids.ts` with all ~10 testid constants (full list, even ones used in PR2/PR3)
- [x] 1.2 Add `data-testid` attributes to components: `SnapshotHeader`, `QAJobControl`, `QAList`, scoring page (`judge-list`, `judge-add-button`, `score-gauge`), `ResultsTable` (`results-table`, `results-table-row-toggle`), report page (`summary-card-*`, `snapshot-score-chart`), `GenerateEvalsModal` (`generate-evals-card-*`, `generation-model-selector`), rubrics page (`rubric-custom-add`, `rubric-preset-add`, `preset-rubric-dialog`, `preset-rubric-card-*`)
- [x] 1.3 Create `frontend/tests/ui-integration/fixtures/data.ts` with canned target/snapshot/rubric/judge/persona/answer/result objects, types imported from `frontend/lib/types.ts`
- [x] 1.4 Create `frontend/tests/ui-integration/fixtures/api-mocks.ts` exporting `setupApiMocks(page, overrides?)` that routes `**/api/v1/**` to a single dispatcher
- [x] 1.5 Create `frontend/tests/ui-integration/fixtures/auth.ts` exporting `test` extended with an `authedPage` fixture that injects token via `addInitScript`
- [x] 1.6 Move existing `frontend/tests/ui-integration/smoke.spec.ts` → `frontend/tests/ui-integration/specs/00-smoke.spec.ts`
- [x] 1.7 Update `frontend/playwright.config.ts` `testDir` to `./tests/ui-integration/specs`
- [x] 1.8 Add `"test:ui:ui": "playwright test --ui"` script to `frontend/package.json`

## 2. PR1 — Auth + CRUD + Navigation Specs

- [x] 2.1 Create `specs/01-auth.spec.ts`: success login redirects, failure shows alert
- [x] 2.2 Create `specs/02-target-lifecycle.spec.ts`: open New Target modal, fill 2-step form, verify card appears
- [x] 2.3 Create `specs/03-navigation.spec.ts` with 6 tests in one `describe` (Overview, Rubrics, Annotations, Scoring-incomplete, Scoring-complete, Report) sharing a `beforeAll` that mocks target id `t-1`
- [x] 2.4 Run `npm run test:ui` — all PR1 specs pass
- [x] 2.5 Run `npm run lint` — clean

## 3. PR2 — UI Modals & Forms

- [x] 3.1 Create `specs/04-rubrics.spec.ts`: custom inline accordion expands; preset modal opens and selecting a card adds a Preset row
- [x] 3.2 Create `specs/05-eval-set.spec.ts` (route: `/targets/1/questions`) with 4 tests:
  - **modal opens**: click "Generate Questions" → modal visible at `choose_mode` with 2 cards (`GENERATE_EVALS_CARD_GENERATE`, `GENERATE_EVALS_CARD_UPLOAD`)
  - **generate flow**: click Generate card → click "Generate New Personas" → `generate_personas` step shows 3 PersonaSelect cards ("Generate with AI", "Random Personas", "Add Manually")
  - **upload flow**: reopen modal at `choose_mode`, click Upload card → click "Type Questions" → `upload_manual` step shows multiline textarea
  - **manage personas / add personas**: click "Manage Personas" tab → click "Add Personas" → `AddPersonasModal` opens showing same 3 PersonaSelect cards
- [x] 3.3 Create `specs/06-judges.spec.ts`: clicking judge add button opens `CreateJudgeDialog` with name/model/temperature fields
- [x] 3.4 Run `npm run test:ui` — all PR2 specs pass

## 4. PR3 — Heavy AI Mocking

- [x] 4.1 Create `frontend/tests/ui-integration/fixtures/job-mocks.ts` exporting `mockJobLifecycle(page, jobId, states[])` for deterministic polled-job state machines
- [x] 4.2 Create `specs/07-persona-generation.spec.ts`: trigger generation, mock job lifecycle, assert `select_personas` view renders mocked personas
- [x] 4.3 Create `specs/08-annotation-run.spec.ts`: click `qa-job-control-button`, mock job lifecycle through running→completed, assert button text transitions and QA item content populates
- [x] 4.4 Create `specs/09-results-expand.spec.ts`: setup scoring-done state with claim-based rubric, click row toggle, assert claim highlighter renders
- [x] 4.5 Run `npm run test:ui` — full suite passes
- [x] 4.6 Run `npm run test:ui` 5 times in a row to flush any flakes
