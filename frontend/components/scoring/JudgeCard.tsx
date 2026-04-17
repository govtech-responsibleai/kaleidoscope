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
import { IconDotsVertical, IconInfoCircle } from "@tabler/icons-react";
import { JudgeConfig, JudgeAlignment, JudgeAccuracy, QAJob } from "@/lib/types";
import { metricsApi, questionApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";
import { compactActionIconProps } from "@/lib/iconStyles";

interface JudgeCardProps {
  judge: JudgeConfig;
  displayName?: string;
  snapshotId: number;
  questionsWithoutScores: number;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  labelOverrideCount: number;
}

export default function JudgeCard({
  judge,
  displayName,
  snapshotId,
  questionsWithoutScores,
  hasQuestionsWithoutAnswers,
  onJobStart,
  onJobComplete,
  onEdit,
  onDuplicate,
  onDelete,
  labelOverrideCount,
}: JudgeCardProps) {
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [alignment, setAlignment] = useState<JudgeAlignment | null>(null);
  const [accuracy, setAccuracy] = useState<JudgeAccuracy | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [pendingCount, setPendingCount] = useState(questionsWithoutScores);
  const [runTotalCount, setRunTotalCount] = useState<number | null>(null);

  const pollingRef = useRef<number | null>(null);
  const onJobCompleteRef = useRef(onJobComplete);

  // Keep the ref updated with latest callback
  useEffect(() => {
    onJobCompleteRef.current = onJobComplete;
  }, [onJobComplete]);

  const fetchPendingCount = useCallback(async (): Promise<number> => {
    if (!snapshotId) return 0;
    try {
      const response = await questionApi.listApprovedWithoutScores(snapshotId, judge.id);
      const nextPending = response.data.length;
      setPendingCount(nextPending);
      return nextPending;
    } catch (error) {
      console.error("Failed to fetch pending score count:", error);
      return pendingCount;
    }
  }, [snapshotId, judge.id, pendingCount]);

  const fetchMetrics = useCallback(async () => {
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
  }, [snapshotId, judge.id]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const startPolling = useCallback((initialPending: number) => {
    stopPolling();
    setIsPolling(true);
    setRunTotalCount(initialPending);

    const poll = async () => {
      try {
        const remaining = await fetchPendingCount();
        if (remaining === 0) {
          stopPolling();
          await fetchMetrics();
          onJobCompleteRef.current();
        }
      } catch (error) {
        console.error("Failed to poll pending score count:", error);
      }
    };

    poll();
    pollingRef.current = window.setInterval(poll, 5000);
  }, [fetchPendingCount, fetchMetrics, stopPolling]);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  useEffect(() => {
    setRunTotalCount(null);
    setAlignment(null);
    setAccuracy(null);
    stopPolling();
  }, [snapshotId, stopPolling]);

  useEffect(() => {
    if (!isPolling) {
      setPendingCount(questionsWithoutScores);
      if (questionsWithoutScores === 0) {
        setRunTotalCount(accuracy?.total_answers ?? null);
      }
    }
  }, [questionsWithoutScores, isPolling, accuracy]);

  const isRunning = isPolling;
  const hasAllScores = pendingCount === 0;
  const totalTracked =
    runTotalCount ??
    (accuracy ? accuracy.total_answers : pendingCount > 0 ? pendingCount : 0);
  const completedCount = Math.max(totalTracked - pendingCount, 0);

  useEffect(() => {
    if (hasAllScores && snapshotId && !isRunning) {
      fetchMetrics();
    }
  }, [hasAllScores, snapshotId, isRunning, fetchMetrics, labelOverrideCount]);

  const handleRun = async () => {
    const initialPending = Math.max(pendingCount, questionsWithoutScores);
    const createdJobs = await onJobStart(judge.id);
    if (createdJobs && createdJobs.length > 0) {
      startPolling(initialPending);
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
              {displayName || judge.name}
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
          {!judge.is_baseline && judge.is_editable && (
            <IconButton size="small" onClick={handleMenuOpen}>
              <IconDotsVertical {...compactActionIconProps} />
            </IconButton>
          )}
        </Stack>

        <Stack spacing={1} sx={{ mt: 2, flexGrow: 1 }}>
          {/* Accuracy Statement - same structure for consistent height */}
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              {accuracy
                ? "This judge rates your target at"
                : (isRunning ? `Running: ${completedCount}/${totalTracked} questions` : "Run this judge to see accuracy")}
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
                  title={`Measures how well this judge's judgments match your annotations (F1 score from ${alignment.sample_count} annotations). ≥50% is considered reliable.`}
                >
                  <IconInfoCircle {...compactActionIconProps} style={{ cursor: "help" }} />
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
          disabled={isRunning || hasAllScores || loadingMetrics || hasQuestionsWithoutAnswers}
        >
          {isRunning ? (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <CircularProgress size={16} /> Running ({completedCount}/{totalTracked})
            </Box>
          ) : hasQuestionsWithoutAnswers ? (
            "Run in Annotations"
          ) : pendingCount > 0 ? (
            `Run (${pendingCount} pending)`
          ) : !accuracy ? (
            "Run Judge"
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
