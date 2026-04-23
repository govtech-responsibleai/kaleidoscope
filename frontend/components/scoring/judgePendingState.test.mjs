import test from "node:test";
import assert from "node:assert/strict";

import { deriveJudgePendingState } from "./judgePendingState.mjs";

test("unknown pending counts are not treated as completed", () => {
  const state = deriveJudgePendingState({
    isRunning: false,
    pollingState: null,
    pendingCountProp: null,
    summaryTotalAnswers: null,
  });

  assert.equal(state.pendingCount, null);
  assert.equal(state.pendingCountKnown, false);
  assert.equal(state.hasAllScores, false);
  assert.equal(state.completedCount, 0);
});

test("zero pending counts remain completed", () => {
  const state = deriveJudgePendingState({
    isRunning: false,
    pollingState: null,
    pendingCountProp: 0,
    summaryTotalAnswers: 12,
  });

  assert.equal(state.pendingCount, 0);
  assert.equal(state.pendingCountKnown, true);
  assert.equal(state.hasAllScores, true);
  assert.equal(state.totalTracked, 12);
  assert.equal(state.completedCount, 12);
});

test("running state uses polling counts", () => {
  const state = deriveJudgePendingState({
    isRunning: true,
    pollingState: { pendingCount: 3, runTotalCount: 10 },
    pendingCountProp: null,
    summaryTotalAnswers: null,
  });

  assert.equal(state.pendingCount, 3);
  assert.equal(state.pendingCountKnown, true);
  assert.equal(state.hasAllScores, false);
  assert.equal(state.totalTracked, 10);
  assert.equal(state.completedCount, 7);
});
