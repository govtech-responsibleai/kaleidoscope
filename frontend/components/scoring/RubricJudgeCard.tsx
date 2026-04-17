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
import { JudgeConfig, QAJob, JudgeAlignment, JudgeAccuracy } from "@/lib/types";
import { metricsApi, questionApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";
import { compactActionIconProps } from "@/lib/iconStyles";

interface RubricJudgeCardProps {
  judge: JudgeConfig;
  displayName: string;
  snapshotId: number;
  rubricId: number;
  pendingCount: number | null;
  bestOption: string;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEdit?: () => void;
  onDuplicate?: () => void;
  onDelete?: () => void;
  cardSx?: SxProps<Theme>;
}

export default function RubricJudgeCard({
  judge,
  displayName,
  snapshotId,
  rubricId,
  pendingCount: pendingCountProp,
  bestOption,
  hasQuestionsWithoutAnswers,
  onJobStart,
  onJobComplete,
  onEdit,
  onDuplicate,
  onDelete,
  cardSx,
}: RubricJudgeCardProps) {
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [pendingCount, setPendingCount] = useState<number | null>(pendingCountProp);
  const [runTotalCount, setRunTotalCount] = useState<number | null>(null);
  const pollingRef = useRef<number | null>(null);
  const onJobCompleteRef = useRef(onJobComplete);

  const [alignment, setAlignment] = useState<JudgeAlignment | null>(null);
  const [accuracy, setAccuracy] = useState<JudgeAccuracy | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  useEffect(() => {
    onJobCompleteRef.current = onJobComplete;
  }, [onJobComplete]);

  const fetchPendingCount = useCallback(async (): Promise<number> => {
    if (!snapshotId) return 0;
    try {
      const response = await questionApi.listApprovedWithoutRubricScores(snapshotId, judge.id, rubricId);
      const nextPending = response.data.length;
      setPendingCount(nextPending);
      return nextPending;
    } catch {
      return pendingCount ?? 0;
    }
  }, [snapshotId, judge.id, rubricId, pendingCount]);

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
      } catch {
        // ignore polling errors
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
    setPendingCount(null);
    setRunTotalCount(null);
    setAlignment(null);
    setAccuracy(null);
    stopPolling();
  }, [snapshotId, stopPolling]);

  useEffect(() => {
    setPendingCount(pendingCountProp);
  }, [pendingCountProp]);

  useEffect(() => {
    if (pendingCountProp === null) {
      fetchPendingCount();
    }
  }, [fetchPendingCount, pendingCountProp]);

  const isRunning = isPolling;
  const hasAllScores = pendingCount === 0;
  const hasSomeScores = (accuracy?.total_answers ?? 0) > 0;
  const isPartial = !isRunning && pendingCount !== null && pendingCount > 0 && hasSomeScores;
  const totalTracked =
    runTotalCount ??
    (accuracy ? accuracy.total_answers : pendingCount ?? 0);
  const completedCount = Math.max(totalTracked - (pendingCount ?? 0), 0);

  useEffect(() => {
    if (hasAllScores && snapshotId && !isRunning) {
      fetchMetrics();
    }
  }, [hasAllScores, isRunning, snapshotId, fetchMetrics]);

  const handleRun = async () => {
    const initialPending = pendingCount ?? 0;
    const createdJobs = await onJobStart(judge.id);
    if (createdJobs && createdJobs.length > 0) {
      startPolling(initialPending);
    }
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
  };

  return (
    <Card variant="outlined" sx={{ height: "100%", ...cardSx }}>
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
          {judge.is_editable && (
            <IconButton size="small" onClick={(event) => setMenuAnchor(event.currentTarget)}>
              <IconDotsVertical {...compactActionIconProps} />
            </IconButton>
          )}
        </Stack>

        <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={handleMenuClose}>
          <MenuItem onClick={() => { handleMenuClose(); onEdit?.(); }}>Edit</MenuItem>
          <MenuItem onClick={() => { handleMenuClose(); onDuplicate?.(); }}>Duplicate</MenuItem>
          <MenuItem onClick={() => { handleMenuClose(); onDelete?.(); }}>Delete</MenuItem>
        </Menu>

        <Stack spacing={1} sx={{ mt: 2, flexGrow: 1 }}>
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              {accuracy
                ? `This judge rates your target at`
                : (isRunning ? `Running: ${completedCount}/${totalTracked} questions` : "Run this judge to see score")}
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
          disabled={isRunning || hasAllScores || loadingMetrics}
        >
          {isRunning ? (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <CircularProgress size={16} /> Running ({completedCount}/{totalTracked})
            </Box>
          ) : hasAllScores ? (
            "Completed"
          ) : isPartial ? (
            `Retry Missing (${pendingCount})`
          ) : hasQuestionsWithoutAnswers ? (
            "Run in Annotations"
          ) : (
            `Run (${pendingCount ?? 0} pending)`
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
