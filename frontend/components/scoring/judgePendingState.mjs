/**
 * @typedef {{
 *   pendingCount: number | null;
 *   runTotalCount: number | null;
 *   hasAllScores: boolean;
 *   totalTracked: number;
 *   completedCount: number;
 *   pendingCountKnown: boolean;
 * }} JudgePendingState
 */

/**
 * Derive a judge card's pending-state view without conflating unknown and completed states.
 *
 * @param {{
 *   isRunning: boolean;
 *   pollingState: { pendingCount: number; runTotalCount: number } | null;
 *   pendingCountProp: number | null;
 *   summaryTotalAnswers: number | null | undefined;
 * }} params
 * @returns {JudgePendingState}
 */
export function deriveJudgePendingState({
  isRunning,
  pollingState,
  pendingCountProp,
  summaryTotalAnswers,
}) {
  const pendingCount = isRunning ? (pollingState?.pendingCount ?? 0) : pendingCountProp;
  const pendingCountKnown = typeof pendingCount === "number";
  const hasAllScores = pendingCountKnown && pendingCount === 0;
  const runTotalCount = isRunning
    ? (pollingState?.runTotalCount ?? 0)
    : (hasAllScores ? (summaryTotalAnswers ?? null) : null);
  const totalTracked =
    runTotalCount ??
    (summaryTotalAnswers ?? (pendingCountKnown && pendingCount > 0 ? pendingCount : 0));
  const completedCount = pendingCountKnown ? Math.max(totalTracked - pendingCount, 0) : 0;

  return {
    pendingCount,
    runTotalCount,
    hasAllScores,
    totalTracked,
    completedCount,
    pendingCountKnown,
  };
}
