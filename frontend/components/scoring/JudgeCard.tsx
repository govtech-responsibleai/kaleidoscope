"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { InfoOutlined as InfoOutlinedIcon, MoreVert as MoreVertIcon } from "@mui/icons-material";
import { JudgeConfig, JudgeAlignment, JudgeAccuracy, JobStatus, QAJob } from "@/lib/types";
import { metricsApi, qaJobApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";

interface JudgeCardProps {
  judge: JudgeConfig;
  snapshotId: number;
  questionsWithoutScores: number;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

export default function JudgeCard({
  judge,
  snapshotId,
  questionsWithoutScores,
  hasQuestionsWithoutAnswers,
  onJobStart,
  onJobComplete,
  onEdit,
  onDuplicate,
  onDelete,
}: JudgeCardProps) {
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [alignment, setAlignment] = useState<JudgeAlignment | null>(null);
  const [accuracy, setAccuracy] = useState<JudgeAccuracy | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [jobs, setJobs] = useState<QAJob[]>([]);
  const [isPolling, setIsPolling] = useState(false);

  const pollingRef = useRef<number | null>(null);
  const onJobCompleteRef = useRef(onJobComplete);

  // Keep the ref updated with latest callback
  useEffect(() => {
    onJobCompleteRef.current = onJobComplete;
  }, [onJobComplete]);

  // Fetch jobs for this specific judge
  const fetchJobs = useCallback(async (): Promise<QAJob[]> => {
    if (!snapshotId) return [];
    try {
      const response = await qaJobApi.listByJudge(snapshotId, judge.id);
      setJobs(response.data);
      return response.data;
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
      return [];
    }
  }, [snapshotId, judge.id]);

  // Start polling for job updates
  const startPolling = useCallback(() => {
    // Clear any existing polling
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    setIsPolling(true);

    const poll = async () => {
      // Fetch directly instead of using callback to avoid stale closure
      try {
        console.log(`[JudgeCard ${judge.name}] Polling jobs for snapshot ${snapshotId}, judge ${judge.id}`);
        const response = await qaJobApi.listByJudge(snapshotId, judge.id);
        const currentJobs = response.data;

        const completedCount = currentJobs.filter((j: QAJob) => j.status === JobStatus.COMPLETED).length;
        console.log(`[JudgeCard ${judge.name}] Fetched ${currentJobs.length} jobs, ${completedCount} completed`, currentJobs.map((j: QAJob) => j.status));

        setJobs(currentJobs);

        // Check if all jobs are completed
        const allCompleted = currentJobs.length > 0 &&
          currentJobs.every((job: QAJob) => job.status === JobStatus.COMPLETED);

        if (allCompleted) {
          // Stop polling
          if (pollingRef.current) {
            window.clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setIsPolling(false);

          // Fetch metrics and notify parent using ref to get latest callback
          await fetchMetrics();
          onJobCompleteRef.current();
        }
      } catch (error) {
        console.error("Failed to poll jobs:", error);
      }
    };

    // Poll immediately, then every 5 seconds
    poll();
    pollingRef.current = window.setInterval(poll, 5000);
  }, [snapshotId, judge.id]);

  // Cleanup polling on unmount or snapshot change
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, []);

  // Reset state when snapshot changes
  useEffect(() => {
    setJobs([]);
    setAlignment(null);
    setAccuracy(null);
    setIsPolling(false);
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, [snapshotId]);

  // Fetch jobs on mount and when snapshot changes
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Calculate aggregate status from jobs
  const isRunning = isPolling || jobs.some((job) => job.status === JobStatus.RUNNING);
  const isCompleted = jobs.length > 0 && jobs.every((job) => job.status === JobStatus.COMPLETED) && questionsWithoutScores === 0;
  const hasAllScores = questionsWithoutScores === 0;
  const completedCount = jobs.filter((job) => job.status === JobStatus.COMPLETED).length;
  const totalJobs = jobs.length;

  // Fetch metrics when all questions have scores (and not running)
  useEffect(() => {
    if ((isCompleted || hasAllScores) && snapshotId && !isRunning) {
      fetchMetrics();
    }
  }, [isCompleted, hasAllScores, isRunning, snapshotId, judge.id]);

  const fetchMetrics = async () => {
    setLoadingMetrics(true);
    try {
      const [alignmentRes, accuracyRes] = await Promise.all([
        metricsApi.getAlignment(snapshotId, judge.id),
        metricsApi.getAccuracy(snapshotId, judge.id),
      ]);
      setAlignment(alignmentRes.data);
      setAccuracy(accuracyRes.data);
    } catch (error) {
      console.error("Failed to fetch metrics:", error);
    } finally {
      setLoadingMetrics(false);
    }
  };

  // Handle run button click
  const handleRun = async () => {
    console.log(`[JudgeCard ${judge.name}] handleRun called`);
    const createdJobs = await onJobStart(judge.id);
    if (createdJobs && createdJobs.length > 0) {
      setJobs(createdJobs);
      startPolling();
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    setMenuAnchor(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
  };

  const handleEdit = () => {
    handleMenuClose();
    onEdit();
  };

  const handleDuplicate = () => {
    handleMenuClose();
    onDuplicate();
  };

  const handleDelete = () => {
    handleMenuClose();
    onDelete();
  };

  return (
    <Card variant="outlined" sx={{ flex: "0 0 30%" , height: "100%" }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h6" noWrap sx={{ textOverflow: "ellipsis" }}>
              {judge.name}
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
                {judge.model_name}
              </Typography>
            </Stack>
          </Box>
          {!judge.is_baseline && judge.is_editable && (
            <IconButton size="small" onClick={handleMenuOpen}>
              <MoreVertIcon fontSize="small" />
            </IconButton>
          )}
        </Stack>

        <Stack spacing={1} sx={{ mt: 2, flexGrow: 1 }}>
          {/* Accuracy Statement - same structure for consistent height */}
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              {accuracy
                ? "This evaluator rates your target at"
                : (isRunning ? `Running: ${completedCount}/${totalJobs} questions` : "Run this evaluator to see accuracy")}
            </Typography>
            <Stack direction="row" spacing={0.5} alignItems="baseline">
              <Typography variant="h4" fontWeight={700} color={accuracy ? "primary.main" : "text.disabled"}>
                {accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : "--%"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                accuracy
              </Typography>
            </Stack>

            {/* Reliability - minimalistic text */}
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
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 500,
                  }}
                >
                  {alignment.f1 >= 0.5 ? "✓" : "✗"} {(alignment.f1 * 100).toFixed(0)}% reliability
                </Typography>
                <Tooltip
                  title={`Measures how well this evaluator's judgments match your annotations (F1 score from ${alignment.sample_count} annotations). ≥50% is considered reliable.`}
                >
                  <InfoOutlinedIcon
                    sx={{
                      fontSize: 16,
                      cursor: "help",
                    }}
                  />
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
          disabled={isRunning || isCompleted || hasAllScores || loadingMetrics || hasQuestionsWithoutAnswers}
        >
          {isRunning ? (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <CircularProgress size={16} /> Running ({completedCount}/{totalJobs})
            </Box>
          ) : questionsWithoutScores > 0 ? (
            totalJobs === 0 ? "Run" : `Update (${questionsWithoutScores} new question${questionsWithoutScores > 1 ? "s" : ""})`
          ) : (
            "Completed"
          )}
        </Button>

        <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={handleMenuClose}>
          <MenuItem onClick={handleEdit}>Edit</MenuItem>
          <MenuItem onClick={handleDuplicate}>Duplicate</MenuItem>
          <MenuItem onClick={handleDelete}>Delete</MenuItem>
        </Menu>
      </CardContent>
    </Card>
  );
}
