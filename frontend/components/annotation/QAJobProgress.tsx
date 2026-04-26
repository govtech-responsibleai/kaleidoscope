"use client";

import React from "react";
import { IconAlertCircle, IconPlayerPauseFilled } from "@tabler/icons-react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import { QAJob, QAJobStageEnum, JobStatus } from "@/lib/types";
import { compactActionIconProps } from "@/lib/iconStyles";

interface QAJobProgressProps {
  job: QAJob | null;
}

export default function QAJobProgress({ job }: QAJobProgressProps) {
  if (!job) {
    return null;
  }

  if (job.status === JobStatus.COMPLETED) {
    return null;
  }

  const getStageLabel = (stage: QAJobStageEnum): string => {
    switch (stage) {
      case QAJobStageEnum.STARTING:
        return "Starting";
      case QAJobStageEnum.GENERATING_ANSWERS:
        return "Generating Answer";
      case QAJobStageEnum.PROCESSING_ANSWERS:
        return "Processing Claims";
      case QAJobStageEnum.SCORING_ANSWERS:
        return "Scoring";
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

  const friendlyError = (raw: string | null, stage: QAJobStageEnum): string => {
    if (!raw) {
      return `Evaluation failed during "${getStageLabel(stage).toLowerCase()}". Click retry to try again.`;
    }
    const lower = raw.toLowerCase();
    if (lower.includes("failed to connect") || lower.includes("dns") || lower.includes("unreachable")) {
      return "Could not reach the evaluation service. Please check your connection and retry.";
    }
    if (lower.includes("timeout") || lower.includes("timed out")) {
      return "The evaluation timed out. This may happen with long responses. Please retry.";
    }
    if (lower.includes("rate limit")) {
      return "Rate limited by the API. Please wait a moment and retry.";
    }
    const maxLen = 120;
    return raw.length > maxLen ? raw.slice(0, maxLen) + "…" : raw;
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

    if (job.status === JobStatus.FAILED) {
      return (
        <Chip
          icon={<IconAlertCircle {...compactActionIconProps} />}
          label="Failed"
          color="error"
          size="small"
        />
      );
    }

    if (job.status === JobStatus.PAUSED) {
      return (
        <Chip
          icon={<IconPlayerPauseFilled {...compactActionIconProps} />}
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
    <Stack spacing={2} sx={{ p: 2, bgcolor: "grey.50", borderBottom: 1, borderColor: "divider" }}>
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
            {`${getStageLabel(job.stage)}...`}
          </Typography>
        </>
      )}

      {isFailed && (
        <Alert severity="error" sx={{ py: 0.5 }}>
          {friendlyError(job.error_message, job.stage)}
        </Alert>
      )}

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
  );
}
