import { JudgeConfig } from "./types";

/**
 * Sort judges: baseline first, then alphabetically by name.
 */
export function sortJudges(judges: JudgeConfig[]): JudgeConfig[] {
  return [...judges].sort((a, b) => {
    if (a.is_editable !== b.is_editable) return a.is_editable ? 1 : -1;
    if (a.is_baseline !== b.is_baseline) return a.is_baseline ? -1 : 1;
    const rank = (judge: JudgeConfig) => {
      if (judge.name === "Judge 1 (Recommended)") return 0;
      if (judge.name === "Judge 2") return 1;
      if (judge.name === "Judge 3") return 2;
      return 3;
    };
    const rankDiff = rank(a) - rank(b);
    if (rankDiff !== 0) return rankDiff;
    return a.name.localeCompare(b.name);
  });
}
