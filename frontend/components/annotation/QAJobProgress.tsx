"use client";

import React, { useEffect } from "react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Pause as PauseIcon,
} from "@mui/icons-material";
import { QAJob, QAJobStageEnum, JobStatus } from "@/lib/types";

interface QAJobProgressProps {
  job: QAJob | null;
}

export default function QAJobProgress({ job }: QAJobProgressProps) {
  if (!job) {
    return null;
  }

  // This page only displays the progress of a single QAJob!!!

  const getStageLabel = (stage: QAJobStageEnum): string => {
    switch (stage) {
      case QAJobStageEnum.STARTING:
        return "Starting";
      case QAJobStageEnum.GENERATING_ANSWERS:
        return "Generating Answer";
      case QAJobStageEnum.PROCESSING_ANSWERS:
        return "Processing Claims";
      case QAJobStageEnum.SCORING_ANSWERS:
        return "Scoring Claims";
      case QAJobStageEnum.COMPLETED:
        return "Completed";
      default:
        return "Processing";
    }
  };

  const getStageProgress = (stage: QAJobStageEnum): number => {
    switch (stage) {
      case QAJobStageEnum.STARTING:
        return 10;
      case QAJobStageEnum.GENERATING_ANSWERS:
        return 30;
      case QAJobStageEnum.PROCESSING_ANSWERS:
        return 60;
      case QAJobStageEnum.SCORING_ANSWERS:
        return 85;
      case QAJobStageEnum.COMPLETED:
        return 100;
      default:
        return 0;
    }
  };
  
  const getStatusChip = () => {
    if (job.status === JobStatus.RUNNING) {
      return (
        <Chip
          icon={<CircularProgress size={14} />}
          label={getStageLabel(job.stage)}
          color="primary"
          size="small"
        />
      );
    }

    if (job.status === JobStatus.COMPLETED) {
      return (
        <Chip
          icon={<CheckCircleIcon />}
          label="Completed"
          color="success"
          size="small"
        />
      );
    }

    if (job.status === JobStatus.FAILED) {
      return (
        <Chip
          icon={<ErrorIcon />}
          label="Failed"
          color="error"
          size="small"
        />
      );
    }

    if (job.status === JobStatus.PAUSED) {
      return (
        <Chip
          icon={<PauseIcon />}
          label="Paused"
          color="default"
          size="small"
        />
      );
    }

    return null;
  };

  const progress = getStageProgress(job.stage);
  const isRunning = job.status === JobStatus.RUNNING;
  const isFailed = job.status === JobStatus.FAILED;

  return (
    <Paper variant="outlined" sx={{ p: 2, bgcolor: "grey.50" }}>
      <Stack spacing={2}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Processing Status
          </Typography>
          {getStatusChip()}
        </Box>

        {isRunning && (
          <>
            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{ height: 6, borderRadius: 1 }}
            />
            <Typography variant="caption" color="text.secondary">
              {getStageLabel(job.stage)}...
            </Typography>
          </>
        )}

        {isFailed && (
          <Alert severity="error" sx={{ py: 0.5 }}>
            Job failed at stage: `{getStageLabel(job.stage)}`. Try running again.
          </Alert>
        )}

        {job.status === JobStatus.COMPLETED && (
          <Alert severity="success" sx={{ py: 0.5 }}>
            Answer generation and scoring completed successfully.
          </Alert>
        )}

        {/* Cost tracking (optional) */}
        {(job.prompt_tokens > 0 || job.completion_tokens > 0) && (
          <Box sx={{ pt: 1, borderTop: 1, borderColor: "divider" }}>
            <Stack direction="row" spacing={3}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Tokens
                </Typography>
                <Typography variant="body2">
                  {job.prompt_tokens + job.completion_tokens}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Cost
                </Typography>
                <Typography variant="body2">
                  ${job.total_cost.toFixed(4)}
                </Typography>
              </Box>
            </Stack>
          </Box>
        )}
      </Stack>
    </Paper>
  );
}
