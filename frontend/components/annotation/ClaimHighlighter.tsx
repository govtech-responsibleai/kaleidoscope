"use client";

import React, { useEffect, useMemo } from "react";
import { Box, Tooltip, Typography } from "@mui/material";
import { AnswerClaim, AnswerClaimScore } from "@/lib/types";

interface ClaimHighlighterProps {
  answerContent: string;
  claims: AnswerClaim[];
  claimScores?: AnswerClaimScore[];
}

export default function ClaimHighlighter({
  answerContent,
  claims,
  claimScores = [],
}: ClaimHighlighterProps) {
  // Create a map of claim_id to score for fast lookup
  const claimScoreMap = useMemo(() => {
    const map = new Map<number, AnswerClaimScore>();
    claimScores.forEach((score) => {
      // console.log("SCORE", score)
      map.set(score.claim_id, score);
    });
    return map;
  }, [claimScores]);

  // Sort claims by sequence order and filter for checkworthy only
  const sortedClaims = useMemo(() => {
    return [...claims]
      .filter((claim) => claim.checkworthy)
      .sort((a, b) => a.sequence_order - b.sequence_order);
  }, [claims]);

  // Build segments highlighting claims in the answer
  const segments = useMemo(() => {
    const result: React.ReactNode[] = [];
    let cursor = 0;

    sortedClaims.forEach((claim) => {
      const claimScore = claimScoreMap.get(claim.id);
      const accurate = claimScore ? claimScore.label : null;

      // Determine background color based on score
        const baseBg =
          accurate === true
            ? "rgba(99, 199, 125, 0.2)" // Green for accurate
            : accurate === false
            ? "rgba(255, 99, 99, 0.2)" // Red for inaccurate
            : "rgba(0, 0, 0, 0.06)"; // Gray for pending
        
        const hoverBg =
          accurate === true
            ? "rgba(99, 199, 125, 0.4)" // Green for accurate
            : accurate === false
            ? "rgba(255, 99, 99, 0.4)" // Red for inaccurate
            : "rgba(0, 0, 0, 0.2)"; // Gray for pending

      const textColor = accurate !== null ? "inherit" : "text.secondary";

      const tooltip =
        claimScore?.explanation ||
        (claimScore
          ? accurate
            ? "Marked accurate by judge"
            : "Marked inaccurate by judge"
          : "No judge score yet");

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
          title={tooltip}
          placement="top"
          arrow
          slotProps={{
            tooltip: {
              sx: {
                fontSize: "0.8rem",
                px: 1.5,
                maxWidth: 420,
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
  }, [answerContent, sortedClaims, claimScoreMap]);

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
