import { TargetRubricResponse } from "@/lib/types";

type RubricLike = {
  id: number;
  group: string;
  position: number;
  scoring_mode?: string | null;
};

const RUBRIC_GROUP_PRIORITY: Record<string, number> = {
  fixed: 0,
  preset: 1,
  custom: 2,
};

export interface MissingRubricCoverage {
  missingQuestionIdsByRubric: Record<number, number[]>;
  pendingRubricIdsByQuestion: Record<number, number[]>;
  pendingRubricNamesByQuestion: Record<number, string[]>;
  pendingPairCount: number;
  pendingQuestionCount: number;
}

export const emptyMissingRubricCoverage: MissingRubricCoverage = {
  missingQuestionIdsByRubric: {},
  pendingRubricIdsByQuestion: {},
  pendingRubricNamesByQuestion: {},
  pendingPairCount: 0,
  pendingQuestionCount: 0,
};

export const orderRubricsForDisplay = <T extends RubricLike>(rubrics: T[]): T[] => (
  [...rubrics].sort((a, b) => {
    const groupDelta =
      (RUBRIC_GROUP_PRIORITY[a.group] ?? Number.MAX_SAFE_INTEGER)
      - (RUBRIC_GROUP_PRIORITY[b.group] ?? Number.MAX_SAFE_INTEGER);
    if (groupDelta !== 0) {
      return groupDelta;
    }
    if (a.position !== b.position) {
      return a.position - b.position;
    }
    return a.id - b.id;
  })
);

export const getRubricGroupLabel = (group: string): string => {
  switch (group) {
    case "fixed":
      return "Fixed";
    case "preset":
      return "Preset";
    case "custom":
      return "Custom";
    default:
      return group;
  }
};

export const getRubricModeLabel = (scoringMode?: string | null): string => (
  scoringMode === "claim_based" ? "Claim-based" : "Response-level"
);

export function buildMissingRubricCoverage(
  entries: Array<{ rubricId: number; questionIds: number[] }>,
  rubrics: TargetRubricResponse[],
): MissingRubricCoverage {
  const missingQuestionIdsByRubric: Record<number, number[]> = {};
  const pendingRubricIdsByQuestion: Record<number, number[]> = {};
  const pendingRubricNamesByQuestion: Record<number, string[]> = {};

  entries.forEach(({ rubricId, questionIds }) => {
    const uniqueQuestionIds = Array.from(new Set(questionIds));
    if (uniqueQuestionIds.length === 0) {
      return;
    }

    missingQuestionIdsByRubric[rubricId] = uniqueQuestionIds;
    const rubricName = rubrics.find((rubric) => rubric.id === rubricId)?.name ?? `Rubric ${rubricId}`;

    uniqueQuestionIds.forEach((questionId) => {
      pendingRubricIdsByQuestion[questionId] = [
        ...(pendingRubricIdsByQuestion[questionId] ?? []),
        rubricId,
      ];
      pendingRubricNamesByQuestion[questionId] = [
        ...(pendingRubricNamesByQuestion[questionId] ?? []),
        rubricName,
      ];
    });
  });

  const pendingPairCount = Object.values(missingQuestionIdsByRubric).reduce(
    (sum, questionIds) => sum + questionIds.length,
    0,
  );

  return {
    missingQuestionIdsByRubric,
    pendingRubricIdsByQuestion,
    pendingRubricNamesByQuestion,
    pendingPairCount,
    pendingQuestionCount: Object.keys(pendingRubricIdsByQuestion).length,
  };
}

export function hasMissingRubricCoverage(coverage: MissingRubricCoverage): boolean {
  return coverage.pendingPairCount > 0;
}
