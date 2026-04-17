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
  type SxProps,
  type Theme,
} from "@mui/material";
import { IconDotsVertical, IconInfoCircle } from "@tabler/icons-react";
import { JudgeConfig, MetricJudgeScoreSummary, QAJob } from "@/lib/types";
import { questionApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";
import { compactActionIconProps } from "@/lib/iconStyles";

interface JudgeCardProps {
  judge: JudgeConfig;
  displayName?: string;
  summary?: MetricJudgeScoreSummary;
  snapshotId: number;
  questionsWithoutScores: number;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  labelOverrideCount: number;
  cardSx?: SxProps<Theme>;
}

export default function JudgeCard({
  judge,
  displayName,
  summary,
  snapshotId,
  questionsWithoutScores,
  hasQuestionsWithoutAnswers,
  onJobStart,
  onJobComplete,
  onEdit,
  onDuplicate,
  onDelete,
  labelOverrideCount,
  cardSx,
}: JudgeCardProps) {
  const hasSummaryValues = summary?.accuracy != null && summary?.reliability != null;
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
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
          onJobCompleteRef.current();
        }
      } catch (error) {
        console.error("Failed to poll pending score count:", error);
      }
    };

    poll();
    pollingRef.current = window.setInterval(poll, 5000);
  }, [fetchPendingCount, stopPolling]);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  useEffect(() => {
    setRunTotalCount(null);
    stopPolling();
  }, [snapshotId, stopPolling]);

  useEffect(() => {
    if (!isPolling) {
      setPendingCount(questionsWithoutScores);
      if (questionsWithoutScores === 0) {
        setRunTotalCount(summary?.total_answers ?? null);
      }
    }
  }, [questionsWithoutScores, isPolling, summary]);

  const isRunning = isPolling;
  const hasAllScores = pendingCount === 0;
  const totalTracked =
    runTotalCount ??
    (summary ? summary.total_answers : pendingCount > 0 ? pendingCount : 0);
  const completedCount = Math.max(totalTracked - pendingCount, 0);

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
    <Card variant="outlined" sx={{ height: "100%", ...cardSx }}>
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
              {hasSummaryValues
                ? "This judge rates your target at"
                : (isRunning ? `Running: ${completedCount}/${totalTracked} questions` : "Run this judge to see accuracy")}
            </Typography>
            <Stack direction="row" spacing={0.5} alignItems="baseline">
              <Typography variant="h4" fontWeight={700} color={hasSummaryValues ? "primary.main" : "text.disabled"}>
                {hasSummaryValues ? `${(summary.accuracy! * 100).toFixed(1)}%` : "--%"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                accuracy
              </Typography>
            </Stack>

            {/* Reliability - minimalistic text */}
            {hasSummaryValues ? (
              <Stack
                direction="row"
                spacing={0.5}
                alignItems="center"
                sx={{
                  mt: 1,
                  color: summary.reliability! >= 0.5 ? "success.main" : "error.main"
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 500,
                  }}
                >
                  {summary.reliability! >= 0.5 ? "✓" : "✗"} {(summary.reliability! * 100).toFixed(0)}% reliability
                </Typography>
                <Tooltip
                  title={`Measures how well this judge's judgments match your annotations. ≥50% is considered reliable.`}
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
          disabled={isRunning || hasAllScores || hasQuestionsWithoutAnswers}
        >
          {isRunning ? (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <CircularProgress size={16} /> Running ({completedCount}/{totalTracked})
            </Box>
          ) : hasQuestionsWithoutAnswers ? (
            "Run in Annotations"
          ) : pendingCount > 0 ? (
            `Run (${pendingCount} pending)`
          ) : !summary ? (
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
