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
import { QAJob, QuestionResponse, QARecord } from "@/lib/types";
import ClaimHighlighter from "./ClaimHighlighter";
import QAJobProgress from "./QAJobProgress";

interface QAContentProps {
  question: QuestionResponse | null;
  qaEntry?: QARecord;
  job: QAJob | null;
}

export default function QAContent({
  question,
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
    return (
      <Stack spacing={3}>
        <QAJobProgress job={job} />
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="body1" color="text.secondary">
            Baseline judge is still generating a response for this question.
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
