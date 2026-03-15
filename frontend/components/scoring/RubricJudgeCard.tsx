"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import { JudgeConfig, JobStatus, QAJob } from "@/lib/types";
import { qaJobApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";

interface RubricJudgeCardProps {
  judge: JudgeConfig;
  rubricCategory: string;
  snapshotId: number;
  rubricId: number;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
}

export default function RubricJudgeCard({
  judge,
  rubricCategory,
  snapshotId,
  rubricId,
  hasQuestionsWithoutAnswers,
  onJobStart,
  onJobComplete,
}: RubricJudgeCardProps) {
  const [jobs, setJobs] = useState<QAJob[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const pollingRef = useRef<number | null>(null);
  const onJobCompleteRef = useRef(onJobComplete);

  useEffect(() => {
    onJobCompleteRef.current = onJobComplete;
  }, [onJobComplete]);

  // Filter jobs for this specific rubric+judge combo
  const rubricJobs = jobs.filter((j) => j.rubric_id === rubricId);

  const fetchJobs = useCallback(async (): Promise<QAJob[]> => {
    if (!snapshotId) return [];
    try {
      const response = await qaJobApi.listByJudge(snapshotId, judge.id);
      setJobs(response.data);
      return response.data;
    } catch {
      return [];
    }
  }, [snapshotId, judge.id]);

  const startPolling = useCallback(() => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsPolling(true);

    const poll = async () => {
      try {
        const response = await qaJobApi.listByJudge(snapshotId, judge.id);
        const allJobs = response.data;
        setJobs(allJobs);

        const currentRubricJobs = allJobs.filter((j) => j.rubric_id === rubricId);
        const allCompleted =
          currentRubricJobs.length > 0 &&
          currentRubricJobs.every((j) => j.status === JobStatus.COMPLETED);

        if (allCompleted) {
          if (pollingRef.current) {
            window.clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setIsPolling(false);
          onJobCompleteRef.current();
        }
      } catch {
        // ignore polling errors
      }
    };

    poll();
    pollingRef.current = window.setInterval(poll, 5000);
  }, [snapshotId, judge.id, rubricId]);

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    setJobs([]);
    setIsPolling(false);
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, [snapshotId]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const isSpecialist = judge.category === rubricCategory;
  const displayName = isSpecialist ? "Recommended Judge" : judge.name;

  const isRunning = isPolling || rubricJobs.some((j) => j.status === JobStatus.RUNNING);
  const isCompleted =
    rubricJobs.length > 0 && rubricJobs.every((j) => j.status === JobStatus.COMPLETED);
  const completedCount = rubricJobs.filter((j) => j.status === JobStatus.COMPLETED).length;
  const totalJobs = rubricJobs.length;

  const handleRun = async () => {
    const createdJobs = await onJobStart(judge.id);
    if (createdJobs && createdJobs.length > 0) {
      setJobs((prev) => {
        const existingIds = new Set(prev.map((j) => j.id));
        const merged = [...prev, ...createdJobs.filter((j) => !existingIds.has(j.id))];
        return merged;
      });
      startPolling();
    }
  };

  return (
    <Card variant="outlined" sx={{ flex: "0 0 30%", height: "100%" }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h6" noWrap sx={{ textOverflow: "ellipsis" }}>
              {displayName}
            </Typography>
            <Stack direction="row" spacing={0.5} alignItems="center">
              {getModelIcon(judge.model_name) && (
                <Box
                  component="img"
                  src={getModelIcon(judge.model_name)!}
                  alt=""
                  sx={{ width: 14, height: 14 }}
                />
              )}
              <Typography variant="caption" color="text.secondary" noWrap sx={{ textOverflow: "ellipsis" }}>
                {judge.model_label || judge.model_name}
              </Typography>
            </Stack>
          </Box>
        </Stack>

        <Box sx={{ mt: 2, mb: 2, minHeight: 56 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
            {isRunning
              ? `Running: ${completedCount}/${totalJobs} questions`
              : isCompleted
              ? "Evaluation complete"
              : "Run this evaluator to score responses"}
          </Typography>
        </Box>

        <Button
          variant="contained"
          fullWidth
          onClick={handleRun}
          disabled={isRunning || isCompleted || hasQuestionsWithoutAnswers}
        >
          {isRunning ? (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <CircularProgress size={16} /> Running ({completedCount}/{totalJobs})
            </Box>
          ) : isCompleted ? (
            "Completed"
          ) : totalJobs === 0 ? (
            "Run"
          ) : (
            "Run"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
