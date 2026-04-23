"use client";

import React, { useMemo } from "react";
import { Box, Stack, Tooltip, Typography } from "@mui/material";
import { IconAlertTriangle } from "@tabler/icons-react";
import { AnswerClaim, AnswerClaimScore, JudgeConfig } from "@/lib/types";

type ClaimStatus = "accurate" | "inaccurate" | "disagree" | "no-data";

// Centralized color configuration for claim highlighting
const CLAIM_COLORS: Record<ClaimStatus, { baseBg: string; hoverBg: string; textColor: string }> = {
  accurate: {
    baseBg: "rgba(99, 199, 125, 0.2)",
    hoverBg: "rgba(99, 199, 125, 0.7)",
    textColor: "inherit",
  },
  inaccurate: {
    baseBg: "rgba(255, 99, 99, 0.2)",
    hoverBg: "rgba(255, 99, 99, 0.7)",
    textColor: "inherit",
  },
  disagree: {
    baseBg: "rgba(255, 165, 0, 0.2)",
    hoverBg: "rgba(255, 165, 0, 0.7)",
    textColor: "inherit",
  },
  "no-data": {
    baseBg: "rgba(0, 0, 0, 0.06)",
    hoverBg: "rgba(0, 0, 0, 0.12)",
    textColor: "text.secondary",
  },
};

interface ClaimAgreement {
  status: ClaimStatus;
  scores: { judge: JudgeConfig; score: AnswerClaimScore }[];
}

interface ClaimHighlighterProps {
  answerContent: string;
  claims: AnswerClaim[];
  // Single judge mode (existing)
  claimScores?: AnswerClaimScore[];
  // Multi-judge mode (new)
  multiJudgeScores?: Map<number, AnswerClaimScore[]>; // judgeId -> scores
  judges?: JudgeConfig[];
  selectedJudgeIds?: number[]; // which judges to consider
  isProcessingClaimScores?: boolean;
  missingScoreMessage?: string;
  instrumentationContext?: Record<string, unknown>;
}

// Helper function to determine agreement status for a claim across multiple judges
function determineClaimAgreement(
  claimId: number,
  multiJudgeScores: Map<number, AnswerClaimScore[]>,
  judges: JudgeConfig[],
  selectedJudgeIds: number[]
): ClaimAgreement {
  const scores: { judge: JudgeConfig; score: AnswerClaimScore }[] = [];

  for (const judgeId of selectedJudgeIds) {
    const judge = judges.find((j) => j.id === judgeId);
    if (!judge) continue;

    const judgeScores = multiJudgeScores.get(judgeId) || [];
    const score = judgeScores.find((s) => s.claim_id === claimId);
    if (score) {
      scores.push({ judge, score });
    }
  }

  if (scores.length === 0) {
    return { status: "no-data", scores: [] };
  }

  const allAccurate = scores.every((s) => s.score.label === true);
  const allInaccurate = scores.every((s) => s.score.label === false);

  if (allAccurate) {
    return { status: "accurate", scores };
  } else if (allInaccurate) {
    return { status: "inaccurate", scores };
  } else {
    return { status: "disagree", scores };
  }
}

// Helper to get claim status from a single score
function getClaimStatus(label: boolean | null): ClaimStatus {
  if (label === true) return "accurate";
  if (label === false) return "inaccurate";
  return "no-data";
}

// Enhanced tooltip content for multi-judge mode
function MultiJudgeTooltipContent({
  agreement,
  isProcessingClaimScores,
  missingScoreMessage,
}: {
  agreement: ClaimAgreement;
  isProcessingClaimScores: boolean;
  missingScoreMessage: string;
}) {
  if (agreement.scores.length === 0) {
    return (
      <Typography variant="body2">
        {isProcessingClaimScores ? "Judge scores still processing" : missingScoreMessage}
      </Typography>
    );
  }

  // Sort: baseline (recommended) first, then secondary
  const sorted = [...agreement.scores].sort((a, b) => Number(b.judge.is_baseline) - Number(a.judge.is_baseline));
  return (
    <Stack spacing={1}>
      {agreement.status === "disagree" && (
        <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 0.5 }}>
          <IconAlertTriangle size={16} stroke={2} color="rgb(255, 194, 133)" />
          <Typography variant="body2" fontWeight={600} sx={{ color: "rgb(255, 194, 133)" }}>
            Disagreement found
          </Typography>
        </Stack>
      )}
      {sorted.map(({ judge, score }) => {
        const displayName = judge.name;
        return (
          <Box
            key={judge.id}
            sx={{
              p: 1,
              borderRadius: 1,
              bgcolor: score.label
                ? "rgba(99, 199, 125, 0.15)"
                : "rgba(255, 99, 99, 0.15)",
              borderLeft: 3,
              borderColor: score.label ? "success.main" : "error.main",
            }}
          >
            <Typography
              variant="caption"
              fontWeight={600}
              sx={{ color: score.label ? "rgba(144, 238, 144, 1)" : "rgba(255, 182, 182, 1)" }}
            >
              {displayName}: {score.label ? "Accurate" : "Inaccurate"}
            </Typography>
            {score.explanation && (
              <Typography variant="body2" sx={{ mt: 0.5, fontSize: "0.75rem" }}>
                {score.explanation}
              </Typography>
            )}
          </Box>
        );
      })}
    </Stack>
  );
}

export default function ClaimHighlighter({
  answerContent,
  claims,
  claimScores = [],
  multiJudgeScores,
  judges = [],
  selectedJudgeIds,
  isProcessingClaimScores = false,
  missingScoreMessage = "Claim score missing unexpectedly after evaluation completed.",
  instrumentationContext,
}: ClaimHighlighterProps) {
  // Determine if we're in multi-judge mode
  const isMultiJudgeMode = multiJudgeScores !== undefined && judges.length > 0;

  // For multi-judge mode, default to all judges if no selection provided
  const effectiveSelectedJudgeIds = selectedJudgeIds ?? judges.map((j) => j.id);

  // Create a map of claim_id to score for fast lookup (single judge mode)
  const claimScoreMap = useMemo(() => {
    const map = new Map<number, AnswerClaimScore>();
    claimScores.forEach((score) => {
      map.set(score.claim_id, score);
    });
    return map;
  }, [claimScores]);

  // Sort claims by backend-provided claim index and filter for checkworthy only
  const sortedClaims = useMemo(() => {
    return [...claims]
      .filter((claim) => claim.checkworthy)
      .sort((a, b) => (a.claim_index ?? 0) - (b.claim_index ?? 0));
  }, [claims]);

  const missingClaimIds = useMemo(() => {
    return sortedClaims
      .filter((claim) => {
        if (isMultiJudgeMode && multiJudgeScores) {
          const agreement = determineClaimAgreement(
            claim.id,
            multiJudgeScores,
            judges,
            effectiveSelectedJudgeIds
          );
          return agreement.scores.length === 0;
        }

        return !claimScoreMap.has(claim.id);
      })
      .map((claim) => claim.id);
  }, [
    sortedClaims,
    isMultiJudgeMode,
    multiJudgeScores,
    judges,
    effectiveSelectedJudgeIds,
    claimScoreMap,
  ]);

  React.useEffect(() => {
    if (isProcessingClaimScores || missingClaimIds.length === 0) {
      return;
    }

    console.warn("Missing terminal claim scores detected", {
      missingClaimIds,
      ...instrumentationContext,
    });
  }, [isProcessingClaimScores, missingClaimIds, instrumentationContext]);

  // Build segments highlighting claims in the answer
  const segments = useMemo(() => {
    const result: React.ReactNode[] = [];
    let cursor = 0;

    sortedClaims.forEach((claim) => {
      let status: ClaimStatus;
      let tooltipContent: React.ReactNode;

      if (isMultiJudgeMode && multiJudgeScores) {
        // Multi-judge mode: determine agreement across judges
        const agreement = determineClaimAgreement(
          claim.id,
          multiJudgeScores,
          judges,
          effectiveSelectedJudgeIds
        );
        status = agreement.status;
        tooltipContent = (
          <MultiJudgeTooltipContent
            agreement={agreement}
            isProcessingClaimScores={isProcessingClaimScores}
            missingScoreMessage={missingScoreMessage}
          />
        );
      } else {
        // Single judge mode
        const claimScore = claimScoreMap.get(claim.id);
        const label = claimScore ? claimScore.label : null;
        status = getClaimStatus(label);

        tooltipContent =
          claimScore?.explanation ||
          (claimScore
            ? label
              ? "Marked accurate by judge"
              : "Marked inaccurate by judge"
            : isProcessingClaimScores
              ? "Judge score still processing"
              : missingScoreMessage);
      }

      const { baseBg, hoverBg, textColor } = CLAIM_COLORS[status];

      // Find the claim text in the answer
      const claimText = claim.claim_text;
      const foundIdx = answerContent.indexOf(claimText, cursor);

      // Skip if claim not found
      if (foundIdx === -1) {
        return;
      }

      // Add text before the claim
      if (foundIdx > cursor) {
        result.push(
          <span key={`pre-${claim.id}`}>{answerContent.slice(cursor, foundIdx)}</span>
        );
      }

      // Add highlighted claim
      result.push(
        <Tooltip
          key={`claim-${claim.id}`}
          title={tooltipContent}
          placement="top"
          arrow
          slotProps={{
            tooltip: {
              sx: {
                fontSize: "0.8rem",
                px: 1.5,
                py: 1,
                maxWidth: 480,
              },
            },
            arrow: {
              sx: {
                fontSize: 14,
              },
            },
          }}
        >
          <Box
            component="span"
            sx={{
              bgcolor: baseBg,
              color: textColor,
              p: 0.5,
              transition: "background-color 0.2s ease",
              boxDecorationBreak: "clone",
              WebkitBoxDecorationBreak: "clone",
              "&:hover": { bgcolor: hoverBg },
            }}
          >
            {claimText}
          </Box>
        </Tooltip>
      );

      cursor = foundIdx + claimText.length;
    });

    // Add remaining text after the last claim
    if (cursor < answerContent.length) {
      result.push(<span key="post-tail">{answerContent.slice(cursor)}</span>);
    }

    return result;
  }, [
    answerContent,
    sortedClaims,
    claimScoreMap,
    isMultiJudgeMode,
    multiJudgeScores,
    judges,
    effectiveSelectedJudgeIds,
    isProcessingClaimScores,
    missingScoreMessage,
  ]);

  // If no claims or no matches, show raw text
  if (segments.length === 0) {
    return (
      <Typography variant="body1" sx={{ whiteSpace: "pre-wrap", p: 2 }}>
        {answerContent}
      </Typography>
    );
  }

  return (
    <Box sx={{ p: 2, borderRadius: 1, lineHeight: 1.8, whiteSpace: "pre-wrap" }}>
      {segments}
    </Box>
  );
}
