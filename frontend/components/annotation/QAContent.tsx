"use client";

import React, { use, useEffect } from "react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
} from "@mui/icons-material";
import { QAJob, QuestionResponse, QARecord, QAJobStageEnum, PersonaResponse } from "@/lib/types";
import ClaimHighlighter from "./ClaimHighlighter";
import QAJobProgress from "./QAJobProgress";

interface QAContentProps {
  question: QuestionResponse | null;
  persona: PersonaResponse | null;
  qaEntry?: QARecord;
  job: QAJob | null;
}

export default function QAContent({
  question,
  persona,
  qaEntry,
  job,
}: QAContentProps) {
  if (!question) {
    return (
      <Paper
        variant="outlined"
        sx={{ p: 3, textAlign: "center" }}
      >
        <Typography variant="body1" color="text.secondary">
          Select a question from the list to view details.
        </Typography>
      </Paper>
    );
  }

  const answer = qaEntry?.answer;
  const claims = qaEntry?.claims ?? [];
  const claimScores = qaEntry?.claimScores ?? [];
  const answerScore = qaEntry?.answerScore ?? null;

  if (!answer) {
    // Determine message based on job stage
    let message = "Waiting for chatbot answer to be generated before running baseline judge.";

    if (job) {
      if (job.stage === QAJobStageEnum.STARTING || job.stage === QAJobStageEnum.GENERATING_ANSWERS) {
        message = "Chatbot is generating an answer for this question.";
      } else if (job.stage === QAJobStageEnum.PROCESSING_ANSWERS || job.stage === QAJobStageEnum.SCORING_ANSWERS) {
        message = "Baseline judge is generating an evaluation for the chatbot answer.";
      }
    }

    return (
      <Stack spacing={3}>
        <QAJobProgress job={job} />
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="body1" color="text.secondary">
            {message}
          </Typography>
        </Paper>
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <QAJobProgress job={job} />

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Stack spacing={3}>
          <Stack direction="row" spacing={1}>
            {answerScore ? (
              <Chip
                icon={
                  answerScore.overall_label ? (
                    <CheckCircleIcon fontSize="small" />
                  ) : (
                    <CancelIcon fontSize="small" />
                  )
                }
                label={`Baseline: ${
                  answerScore.overall_label ? "Accurate" : "Inaccurate"
                }`}
                color={answerScore.overall_label ? "success" : "error"}
                size="small"
              />
            ) : (
              <Chip
                icon={<CircularProgress size={12} />}
                label="Judge label pending"
                size="small"
              />
            )}
          </Stack>

          <Stack spacing={2}>
            <Box display="flex" justifyContent="flex-end">
              <Box
                sx={{
                  maxWidth: { xs: "100%", sm: "75%" },
                  bgcolor: "grey.100",
                  color: "text.primary",
                  px: 3,
                  py: 1.5,
                  borderRadius: "30px 30px 0 30px",
                }}
              >
                <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                  {question.text}
                </Typography>
                {/* Question Metadata Chips */}
                <Box display="flex" gap={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1.5 }}>
                  {persona && (
                    <Chip label={persona.title} size="small" />
                  )}
                  <Chip
                    label={question.type}
                    size="small"
                    color={question.type === "edge" ? "warning" : "default"}
                    variant={question.type === "edge" ? "filled" : "outlined"}
                  />
                  <Chip
                    label={question.scope === "in_kb" ? "In KB" : "Out KB"}
                    size="small"
                    color={question.scope === "in_kb" ? "success" : "info"}
                    variant="outlined"
                  />
                </Box>
              </Box>
            </Box>

            <Box display="flex" justifyContent="flex-start">
              <Box
                sx={{
                  maxWidth: { xs: "100%", sm: "85%" },
                  px: 1,
                  py: 0.5,
                  borderRadius: "30px 30px 30px 0",
                  border: (theme) => `1px solid ${theme.palette.divider}`,
                }}
              >
                {claims.length > 0 ? (
                  <ClaimHighlighter
                    answerContent={answer.answer_content}
                    claims={claims}
                    claimScores={claimScores}
                  />
                ) : (
                  <Typography
                    variant="body1"
                    sx={{ p: 2, whiteSpace: "pre-wrap" }}
                  >
                    {answer.answer_content}
                  </Typography>
                )}
              </Box>
            </Box>
          </Stack>
        </Stack>
      </Paper>
    </Stack>
  );
}
