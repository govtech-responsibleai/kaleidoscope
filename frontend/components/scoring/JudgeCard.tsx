"use client";

import React, { useState, useEffect } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { InfoOutlined as InfoOutlinedIcon, MoreVert as MoreVertIcon } from "@mui/icons-material";
import { JudgeConfig, JudgeAlignment, JudgeAccuracy, JobStatus, QAJob } from "@/lib/types";
import { metricsApi } from "@/lib/api";

interface JudgeCardProps {
  judge: JudgeConfig;
  snapshotId: number;
  jobs: QAJob[];
  onRun: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

export default function JudgeCard({
  judge,
  snapshotId,
  jobs,
  onRun,
  onEdit,
  onDuplicate,
  onDelete,
}: JudgeCardProps) {
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [alignment, setAlignment] = useState<JudgeAlignment | null>(null);
  const [accuracy, setAccuracy] = useState<JudgeAccuracy | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  // Calculate aggregate status from jobs
  const isRunning = jobs.some((job) => job.status === JobStatus.RUNNING);
  const isCompleted = jobs.length > 0 && jobs.every((job) => job.status === JobStatus.COMPLETED);
  const completedCount = jobs.filter((job) => job.status === JobStatus.COMPLETED).length;
  const totalJobs = jobs.length;

  // Fetch metrics when job completes
  useEffect(() => {
    "HIT THE USE EFFECT"
    if (isCompleted && snapshotId) {
      fetchMetrics();
    }
  }, [isCompleted, snapshotId, judge.id]);

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
    <Card variant="outlined" sx={{ flex: "0 0 31%" , height: "100%" }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h6" noWrap sx={{ textOverflow: "ellipsis" }}>
              {judge.name}
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap sx={{ textOverflow: "ellipsis" }}>
              {judge.model_name}
            </Typography>
          </Box>
          {!judge.is_baseline && judge.is_editable && (
            <IconButton size="small" onClick={handleMenuOpen}>
              <MoreVertIcon fontSize="small" />
            </IconButton>
          )}
        </Stack>

        <Stack spacing={1} sx={{ mt: 2, flexGrow: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Chatbot Accuracy
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h4">{accuracy ? `${(accuracy.accuracy*100).toFixed(1)}%` : "--"}</Typography>
              <Tooltip
                title={
                  accuracy
                    ? `Judge evaluated ${accuracy.accurate_count} / ${accuracy.total_answers} responses as "Accurate".`
                    : "Waiting for judge evaluations"
                }
              >
                <InfoOutlinedIcon fontSize="small" color="action" />
              </Tooltip>
            </Stack>
          </Box>

          <Divider />

          {/* Judge Alignment */}
          <Box>
            <Typography variant="caption" color="text.secondary">
              Evaluator Reliability
            </Typography>

            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h4">{alignment ? `${(alignment.f1*100).toFixed(1)}%` : "--"}</Typography>
              <Tooltip
                title={
                  alignment
                    ? `Calculated from ${alignment.sample_count} annotations`
                    : "Waiting for judge evaluations"
                }
              >
                <InfoOutlinedIcon fontSize="small" color="action" />
              </Tooltip>
            </Stack>
          </Box>
        </Stack>

        <Alert severity="info" sx={{ mt: 2 }}>
          {isCompleted
            ? "This judge has completed."
            : isRunning
            ? `Running: ${completedCount}/${totalJobs} questions completed`
            : !alignment && !accuracy
            ? "Run this judge to view metrics."
            : "Metrics are being calculated."}
        </Alert>

        <Button
          variant="contained"
          fullWidth
          sx={{ mt: 2 }}
          onClick={onRun}
          disabled={isRunning || isCompleted || loadingMetrics}
        >
          {isRunning ? (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <CircularProgress size={16} /> Running ({completedCount}/{totalJobs})
            </Box>
          ) : (
            "Run Judge"
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
