"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { InfoOutlined as InfoOutlinedIcon } from "@mui/icons-material";
import { JudgeConfig, JobStatus, QAJob, JudgeAlignment, JudgeAccuracy } from "@/lib/types";
import { qaJobApi, metricsApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";

interface RubricJudgeCardProps {
  judge: JudgeConfig;
  displayName: string;
  snapshotId: number;
  rubricId: number;
  bestOption: string;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
}

export default function RubricJudgeCard({
  judge,
  displayName,
  snapshotId,
  rubricId,
  bestOption,
  hasQuestionsWithoutAnswers,
  onJobStart,
  onJobComplete,
}: RubricJudgeCardProps) {
  const [jobs, setJobs] = useState<QAJob[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const pollingRef = useRef<number | null>(null);
  const onJobCompleteRef = useRef(onJobComplete);

  const [alignment, setAlignment] = useState<JudgeAlignment | null>(null);
  const [accuracy, setAccuracy] = useState<JudgeAccuracy | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

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

  const fetchMetrics = useCallback(async () => {
    setLoadingMetrics(true);
    try {
      const [alignmentRes, accuracyRes] = await Promise.all([
        metricsApi.getRubricAlignment(snapshotId, judge.id, rubricId).catch(() => null),
        metricsApi.getRubricAccuracy(snapshotId, judge.id, rubricId).catch(() => null),
      ]);
      setAlignment(alignmentRes?.data ?? null);
      setAccuracy(accuracyRes?.data ?? null);
    } catch {
      // ignore
    } finally {
      setLoadingMetrics(false);
    }
  }, [snapshotId, judge.id, rubricId]);

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
          await fetchMetrics();
          onJobCompleteRef.current();
        }
      } catch {
        // ignore polling errors
      }
    };

    poll();
    pollingRef.current = window.setInterval(poll, 5000);
  }, [snapshotId, judge.id, rubricId, fetchMetrics]);

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
    setAlignment(null);
    setAccuracy(null);
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, [snapshotId]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const isRunning = isPolling || rubricJobs.some((j) => j.status === JobStatus.RUNNING);
  const isCompleted =
    rubricJobs.length > 0 && rubricJobs.every((j) => j.status === JobStatus.COMPLETED);
  const hasAllScores = rubricJobs.length > 0;
  const completedCount = rubricJobs.filter((j) => j.status === JobStatus.COMPLETED).length;
  const totalJobs = rubricJobs.length;

  // Fetch metrics when completed
  useEffect(() => {
    if ((isCompleted || hasAllScores) && snapshotId && !isRunning) {
      fetchMetrics();
    }
  }, [isCompleted, hasAllScores, isRunning, snapshotId, fetchMetrics]);

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

        <Stack spacing={1} sx={{ mt: 2, flexGrow: 1 }}>
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              {accuracy
                ? `This judge rates your target at`
                : (isRunning ? `Running: ${completedCount}/${totalJobs} questions` : "Run this judge to see score")}
            </Typography>
            <Stack direction="row" spacing={0.5} alignItems="baseline">
              <Typography variant="h4" fontWeight={700} color={accuracy ? "primary.main" : "text.disabled"}>
                {accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : "--%"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {bestOption || "score"}
              </Typography>
            </Stack>

            {/* Reliability */}
            {alignment ? (
              <Stack
                direction="row"
                spacing={0.5}
                alignItems="center"
                sx={{
                  mt: 1,
                  color: alignment.f1 >= 0.5 ? "success.main" : "error.main"
                }}
              >
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  {alignment.f1 >= 0.5 ? "✓" : "✗"} {(alignment.f1 * 100).toFixed(0)}% reliability
                </Typography>
                <Tooltip
                  title={`Measures how well this judge's choices match your rubric annotations (${alignment.sample_count} annotations). ≥50% is considered reliable.`}
                >
                  <InfoOutlinedIcon sx={{ fontSize: 16, cursor: "help" }} />
                </Tooltip>
              </Stack>
            ) : (
              <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
                --% reliability
              </Typography>
            )}
          </Box>
        </Stack>

        <Button
          variant="contained"
          fullWidth
          sx={{ mt: 2 }}
          onClick={handleRun}
          disabled={isRunning || isCompleted || hasQuestionsWithoutAnswers || loadingMetrics}
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
