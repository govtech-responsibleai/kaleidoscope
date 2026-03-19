"use client";

import React from "react";
import { Box, Stack } from "@mui/material";
import { JudgeConfig, QAJob } from "@/lib/types";
import JudgeCard from "./JudgeCard";

interface JudgeCardsProps {
  judges: JudgeConfig[];
  snapshotId: number;
  questionsWithoutScores: Record<number, number>;
  hasQuestionsWithoutAnswers: boolean;
  scrollContainerRef?: React.Ref<HTMLDivElement>;
  getDisplayName?: (judge: JudgeConfig) => string;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEditJudge: (judge: JudgeConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
  labelOverrideCount: number;
}

export default function JudgeCards({
  judges,
  snapshotId,
  questionsWithoutScores,
  hasQuestionsWithoutAnswers,
  scrollContainerRef,
  getDisplayName,
  onJobStart,
  onJobComplete,
  onEditJudge,
  onDuplicateJudge,
  onDeleteJudge,
  labelOverrideCount,
}: JudgeCardsProps) {

  return (
    <Box
      ref={scrollContainerRef}
      sx={{
        overflowX: "auto",
        "&::-webkit-scrollbar": {
          height: 8,
        },
        "&::-webkit-scrollbar-track": {
          backgroundColor: "grey.100",
          borderRadius: 4,
        },
        "&::-webkit-scrollbar-thumb": {
          backgroundColor: "grey.400",
          borderRadius: 4,
          "&:hover": {
            backgroundColor: "grey.500",
          },
        },
      }}
    >
      <Stack direction="row" spacing={2} justifyContent="flex-start" sx={{ mb: 2}}>
        {judges.map((judge) => (
          <JudgeCard
            key={judge.id}
            judge={judge}
            displayName={getDisplayName?.(judge)}
            snapshotId={snapshotId}
            questionsWithoutScores={questionsWithoutScores[judge.id] || 0}
            hasQuestionsWithoutAnswers={hasQuestionsWithoutAnswers}
            onJobStart={onJobStart}
            onJobComplete={onJobComplete}
            onEdit={() => onEditJudge(judge)}
            onDuplicate={() => onDuplicateJudge(judge)}
            onDelete={() => onDeleteJudge(judge)}
            labelOverrideCount={labelOverrideCount}
          />
        ))}
      </Stack>
    </Box>
  );
}
