"use client";

import React from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  ArrowBack as ArrowBackIcon,
  ArrowForward as ArrowForwardIcon,
} from "@mui/icons-material";
import { QAJob, QuestionResponse, QARecord, QAJobStageEnum, PersonaResponse } from "@/lib/types";
import ClaimHighlighter from "./ClaimHighlighter";
import QAJobProgress from "./QAJobProgress";

interface QAContentProps {
  question: QuestionResponse | null;
  persona: PersonaResponse | null;
  qaEntry?: QARecord;
  job: QAJob | null;
  onPrev: () => void;
  onNext: () => void;
  prevDisabled: boolean;
  nextDisabled: boolean;
}

export default function QAContent({
  question,
  persona,
  qaEntry,
  job,
  onPrev,
  onNext,
  prevDisabled,
  nextDisabled,
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

  const claimScoreSummary = React.useMemo(() => {
    const checkworthyIds = new Set(
      claims.filter((claim) => claim.checkworthy).map((claim) => claim.id)
    );

    let scored = 0;
    let inaccurate = 0;

    claimScores.forEach((score) => {
      if (!checkworthyIds.has(score.claim_id)) {
        return;
      }
      if (score.label === null || score.label === undefined) {
        return;
      }
      scored += 1;
      if (score.label === false) {
        inaccurate += 1;
      }
    });

    return {
      totalCheckworthy: checkworthyIds.size,
      scored,
      inaccurate,
    };
  }, [claims, claimScores]);

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
    <Stack>
      {/* Top bar with question ID, navigation, and baseline evaluation */}
      <Stack
        direction="row"
        spacing={2} 
        alignItems="center"
        justifyContent="space-between"
        sx={{ px: 2, py: 1, borderBottom: 1, borderColor: "divider" }}
      >
        <Typography variant="body2" color="text.secondary">
          Q{question.id}
        </Typography>

        <Box sx={{ flexGrow: 1 }} />

        <Stack direction="row" spacing={1} alignItems="center">
          <Button
            startIcon={<ArrowBackIcon fontSize="small" />}
            onClick={onPrev}
            disabled={prevDisabled}
            variant="outlined"
            size="small"
            sx={{ "& .MuiButton-startIcon": { margin: "0px", padding: "3px 0" }, minWidth: 0 }}
          />
          <Button
            endIcon={<ArrowForwardIcon fontSize="small" />}
            onClick={onNext}
            disabled={nextDisabled}
            variant="outlined"
            size="small"
            sx={{ "& .MuiButton-endIcon": { margin: "0px", padding: "3px 0" }, minWidth: 0 }}
          />
        </Stack>
      </Stack>

      <QAJobProgress job={job} />

      {answerScore && (
        <Stack
          direction="row" 
          spacing={2} 
          alignItems="center"
          sx={{
            p: 2,
            borderBottom: 1, 
            borderColor: "divider",
            bgcolor: "grey.50",
          }}
        >
          <Chip
            icon={
              answerScore.overall_label ? (
                <CheckCircleIcon fontSize="small" />
              ) : (
                <CancelIcon fontSize="small" />
              )
            }
            label={`Baseline Evaluation: ${answerScore.overall_label ? "Accurate" : "Inaccurate"}`}
            color={answerScore.overall_label ? "success" : "error"}
            size="small"
          />
          <Alert
            severity="info"
            sx={{
              flex: 1,
              "& .MuiAlert-message": { width: "100%" },
              py: 0.5,
              px: 1.5,
            }}
          >
            <Typography variant="body2" color="info.dark">
              {claimScoreSummary.totalCheckworthy === 0
                ? "No claims found, answer defaults to accurate."
                : claimScoreSummary.scored === 0
                  ? "Claims are still waiting on judge scores."
                  : claimScoreSummary.inaccurate > 0
                    ? `The response contains ${claimScoreSummary.inaccurate}/${claimScoreSummary.scored} unsupported claim(s) and is therefore marked as inaccurate.`
                    : `All ${claimScoreSummary.scored} extracted claims are supported, the response is therefore marked as accurate.`}
            </Typography>
          </Alert>
        </Stack>
      )}

      <Box sx={{ p: 3 }}>
        <Stack spacing={3}>
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
      </Box>
    </Stack>
  );
}
