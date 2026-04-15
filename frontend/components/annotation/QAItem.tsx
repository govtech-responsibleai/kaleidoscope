"use client";

import React from "react";
import {
  Box,
  Checkbox,
  ListItem,
  ListItemButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Answer,
  QAJob,
  QAJobStageEnum,
  JobStatus,
  QuestionResponse,
} from "@/lib/types";
import LoadingDots from "@/components/shared/LoadingDots";

interface QAItemProps {
  question: QuestionResponse;
  answer: Answer | null;
  job: QAJob | null;
  isActive: boolean;
  isChecked: boolean;
  onToggleSelection: () => void;
  onSelect: () => void;
}

const getStageLabel = (
  job: QAJob | null,
  answer: Answer | null,
): string => {
  if (!job) {
    if (answer?.has_annotation) {
      return "Annotated";
    }
    if (answer) {
      return "Answer Only";
    }
    return "Not Started";
  }

  if (job.status === JobStatus.RUNNING) {
    switch (job.stage) {
      case QAJobStageEnum.STARTING:
        return "Starting";
      case QAJobStageEnum.GENERATING_ANSWERS:
        return "Generating";
      case QAJobStageEnum.PROCESSING_ANSWERS:
        return "Processing";
      case QAJobStageEnum.SCORING_ANSWERS:
        return "Scoring";
      default:
        return "Running";
    }
  }

  if (job.status === JobStatus.COMPLETED) {
    return "Completed";
  }

  if (job.status === JobStatus.FAILED) {
    return "Failed";
  }

  if (job.status === JobStatus.PAUSED) {
    return "Paused";
  }

  return "Pending";
};

const getStageColor = (
  job: QAJob | null,
  answer: Answer | null,
): "default" | "warning" | "success" | "error" | "info" => {
  if (!job) {
    if (answer?.has_annotation) {
      return "success";
    }
    if (answer) {
      return "info";
    }
    return "default";
  }

  switch (job.status) {
    case JobStatus.RUNNING:
      return "warning";
    case JobStatus.COMPLETED:
      return "success";
    case JobStatus.FAILED:
      return "error";
    case JobStatus.PAUSED:
      return "info";
    default:
      return "default";
  }
};

const isActiveStage = (job: QAJob | null): boolean =>
  job?.status === JobStatus.RUNNING;

const truncate = (text: string, length = 100) => {
  if (text.length <= length) return text;
  return `${text.slice(0, length)}…`;
};

export default function QAItem({
  question,
  answer,
  job,
  isActive,
  isChecked,
  onToggleSelection,
  onSelect,
}: QAItemProps) {
  const checkbox = (
    <Checkbox
      checked={isChecked}
      size="small"
      disabled={!answer}
      onClick={(event) => {
        event.stopPropagation();
        if (answer) {
          onToggleSelection();
        }
      }}
    />
  );

  return (
    <ListItem disablePadding sx={{ mb: 1.5 }}>
      <ListItemButton
        selected={isActive}
        onClick={onSelect}
        alignItems="flex-start"
        sx={{
          borderRadius: 1,
          border: (theme) =>
            isActive ? `1px solid ${theme.palette.primary.main}` : `1px solid ${theme.palette.divider}`,
          borderLeft: isChecked ? "3px solid" : undefined,
          borderLeftColor: isChecked ? "primary.main" : undefined,
        }}
      >
        <Stack spacing={2} sx={{ width: "100%" }}>
          <Stack direction="row" spacing={1.5} alignItems="flex-start">
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, textOverflow: 'ellipsis', overflow: 'hidden', display: '-webkit-box', lineClamp: 2, WebkitLineClamp: 2, WebkitBoxOrient: 'vertical'  }}>
              <Typography component="span" variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600, mr: 0.5 }}>
                {question.id}.
              </Typography>
              {question?.text
                ? question.text
                : "Question not found."}
              </Typography>
              {job?.error_message ? (
                <Tooltip title={job.error_message}>
                  <Typography variant="caption" color={`${getStageColor(job, answer)}.main`} sx={{ mt: 0.25 }}>
                    {getStageLabel(job, answer)}{isActiveStage(job) && <LoadingDots />}
                  </Typography>
                </Tooltip>
              ) : (
                <Typography variant="caption" color={`${getStageColor(job, answer)}.main`} sx={{ mt: 0.25 }}>
                  {getStageLabel(job, answer)}{isActiveStage(job) && <LoadingDots />}
                </Typography>
              )}
            </Box>

            {answer ? (
              checkbox
            ) : (
              <Tooltip title="Answer not available yet">
                <Box>{checkbox}</Box>
              </Tooltip>
            )}
          </Stack>

          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600, textOverflow: 'ellipsis', overflow: 'hidden', display: '-webkit-box', lineClamp: 3, WebkitLineClamp: 3, WebkitBoxOrient: 'vertical'  }}>
            {answer?.answer_content
              ? answer.answer_content
              : "No response generated yet."}
          </Typography>
        </Stack>
      </ListItemButton>
    </ListItem>
  );
}
