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
import { JudgeConfig, JudgeScoreSummary, QAJob } from "@/lib/types";
import { metricsApi } from "@/lib/api";
import { GLOBAL_POLLING_INTERVAL } from "@/lib/constants";
import { usePolling } from "@/hooks/usePolling";
import { getModelIcon } from "@/lib/modelIcons";
import { compactActionIconProps } from "@/lib/styles";
import { deriveJudgePendingState } from "@/components/scoring/judgePendingState.mjs";

interface JudgeCardProps {
  judge: JudgeConfig;
  displayName?: string;
  summary?: JudgeScoreSummary;
  snapshotId: number;
  rubricId: number;
  pendingCount: number | null;
  scoreLabel?: string;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => Promise<void> | void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  cardSx?: SxProps<Theme>;
}

export default function JudgeCard({
  judge,
  displayName,
  summary,
  snapshotId,
  rubricId,
  pendingCount: pendingCountProp,
  scoreLabel = "score",
  hasQuestionsWithoutAnswers,
  onJobStart,
  onJobComplete,
  onEdit,
  onDuplicate,
  onDelete,
  cardSx,
}: JudgeCardProps) {
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [pollingState, setPollingState] = useState<{
    snapshotId: number;
    rubricId: number;
    pendingCount: number;
    runTotalCount: number;
  } | null>(null);

  const onJobCompleteRef = useRef(onJobComplete);
  const pollingStateRef = useRef(pollingState);

  useEffect(() => {
    onJobCompleteRef.current = onJobComplete;
  }, [onJobComplete]);

  useEffect(() => {
    pollingStateRef.current = pollingState;
  }, [pollingState]);

  const fetchPendingCount = useCallback(async (): Promise<number> => {
    if (!snapshotId) return 0;
    try {
      const response = await metricsApi.getScoringPendingCounts(snapshotId, rubricId);
      const nextPending = response.data.pending_counts[String(judge.id)] ?? 0;
      setPollingState((current) => (
        current && current.snapshotId === snapshotId && current.rubricId === rubricId
          ? { ...current, pendingCount: nextPending }
          : current
      ));
      return nextPending;
    } catch (error) {
      console.error("Failed to fetch pending score count:", error);
      const ps = pollingStateRef.current;
      return ps?.snapshotId === snapshotId && ps.rubricId === rubricId
        ? ps.pendingCount
        : (pendingCountProp ?? 0);
    }
  }, [snapshotId, judge.id, rubricId, pendingCountProp]);

  const stopPolling = useCallback(() => {
    setPollingState(null);
  }, []);

  const startPolling = useCallback((initialPending: number) => {
    setPollingState({
      snapshotId,
      rubricId,
      pendingCount: initialPending,
      runTotalCount: initialPending,
    });
  }, [rubricId, snapshotId]);

  const activePollingState =
    pollingState?.snapshotId === snapshotId && pollingState.rubricId === rubricId ? pollingState : null;
  usePolling({
    enabled: activePollingState !== null,
    intervalMs: GLOBAL_POLLING_INTERVAL,
    onPoll: async () => {
      const remaining = await fetchPendingCount();
      if (remaining === 0) {
        await onJobCompleteRef.current();
        stopPolling();
      }
    },
  });
  const isRunning = activePollingState !== null;
  const {
    pendingCount,
    hasAllScores,
    totalTracked,
    completedCount,
  } = deriveJudgePendingState({
    isRunning,
    pollingState: activePollingState,
    pendingCountProp,
    summaryTotalAnswers: summary?.total_answers,
  });
  const hasSummaryValues = !isRunning && summary?.accuracy != null && summary?.reliability != null;

  const handleRun = async () => {
    const initialPending = pendingCount ?? await fetchPendingCount();
    startPolling(initialPending);
    const createdJobs = await onJobStart(judge.id);
    if (!createdJobs || createdJobs.length === 0) {
      stopPolling();
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
    <Card variant="outlined" sx={{ height: "100%", borderColor: "divider", ...cardSx }}>
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
                : (isRunning ? `Running: ${completedCount}/${totalTracked} questions` : "Run this judge to see score")}
            </Typography>
            <Stack direction="row" spacing={0.5} alignItems="baseline">
              <Typography variant="h4" fontWeight={700} color={hasSummaryValues ? "primary.main" : "text.disabled"}>
                {hasSummaryValues ? `${(summary.accuracy! * 100).toFixed(1)}%` : "--%"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {scoreLabel}
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
          ) : hasQuestionsWithoutAnswers && !hasAllScores ? (
            "Run in Annotations"
          ) : (pendingCount ?? 0) > 0 ? (
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
