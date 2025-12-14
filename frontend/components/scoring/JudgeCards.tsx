"use client";

import React from "react";
import { Box, Stack } from "@mui/material";
import { JudgeConfig, QAJob } from "@/lib/types";
import JudgeCard from "./JudgeCard";

interface JudgeCardsProps {
  judges: JudgeConfig[];
  snapshotId: number;
  judgeJobs: Record<number, QAJob[]>;
  scrollContainerRef?: React.Ref<HTMLDivElement>;
  onRunJudge: (judgeId: number) => void;
  onEditJudge: (judge: JudgeConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
}

export default function JudgeCards({
  judges,
  snapshotId,
  judgeJobs,
  scrollContainerRef,
  onRunJudge,
  onEditJudge,
  onDuplicateJudge,
  onDeleteJudge,
}: JudgeCardsProps) {

  return (
    <Box
      ref={scrollContainerRef}
      sx={{
        overflowX: "auto",
        pb: 2,
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
      <Stack direction="row" spacing={2} justifyContent="flex-start">
        {judges.map((judge) => (
          <JudgeCard
            key={judge.id}
            judge={judge}
            snapshotId={snapshotId}
            jobs={judgeJobs[judge.id] || []}
            onRun={() => onRunJudge(judge.id)}
            onEdit={() => onEditJudge(judge)}
            onDuplicate={() => onDuplicateJudge(judge)}
            onDelete={() => onDeleteJudge(judge)}
          />
        ))}
      </Stack>
    </Box>
  );
}
