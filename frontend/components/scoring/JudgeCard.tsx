"use client";

import React, { useState, useEffect } from "react";
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
import { metricsApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";

interface JudgeCardProps {
  judge: JudgeConfig;
  snapshotId: number;
  jobs: QAJob[];
  questionsWithoutScores: number;
  hasQuestionsWithoutAnswers: boolean;
  onRun: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

export default function JudgeCard({
  judge,
  snapshotId,
  jobs,
  questionsWithoutScores,
  hasQuestionsWithoutAnswers,
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
  const isCompleted = jobs.length > 0 && jobs.every((job) => job.status === JobStatus.COMPLETED) && questionsWithoutScores === 0;
  const completedCount = jobs.filter((job) => job.status === JobStatus.COMPLETED).length;
  const totalJobs = jobs.length;

  // Fetch metrics when job completes
  useEffect(() => {
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
          onClick={onRun}
          disabled={isRunning || isCompleted || loadingMetrics || hasQuestionsWithoutAnswers}
        >
          {isRunning ? (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <CircularProgress size={16} /> Running ({completedCount}/{totalJobs})
            </Box>
          ) : totalJobs === 0 ? (
            "Run"
          ) : questionsWithoutScores > 0 ? (
            `Update (${questionsWithoutScores} new question${questionsWithoutScores > 1 ? "s" : ""})`
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
