"use client";

import React, { useState, useEffect } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  ArrowBack as ArrowBackIcon,
  ArrowForward as ArrowForwardIcon,
  ExpandMore as ExpandMoreIcon,
} from "@mui/icons-material";
import { QAJob, QuestionResponse, QARecord, QAJobStageEnum, PersonaResponse, TargetRubricResponse, RubricAnswerScore, JudgeConfig } from "@/lib/types";
import { rubricScoreApi, judgeApi } from "@/lib/api";
import ClaimHighlighter from "./ClaimHighlighter";
import QAJobProgress from "./QAJobProgress";

interface QAContentProps {
  targetId: number;
  question: QuestionResponse | null;
  persona: PersonaResponse | null;
  qaEntry?: QARecord;
  job: QAJob | null;
  onPrev: () => void;
  onNext: () => void;
  prevDisabled: boolean;
  nextDisabled: boolean;
  rubrics: TargetRubricResponse[];
}

export default function QAContent({
  targetId,
  question,
  persona,
  qaEntry,
  job,
  onPrev,
  onNext,
  prevDisabled,
  nextDisabled,
  rubrics,
}: QAContentProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [rubricScores, setRubricScores] = useState<RubricAnswerScore[]>([]);
  const [rubricScoresLoading, setRubricScoresLoading] = useState(false);
  const [rubricJudges, setRubricJudges] = useState<JudgeConfig[]>([]);

  // Reset tab when question changes
  React.useEffect(() => {
    setActiveTab(0);
  }, [question?.id]);

  // Fetch rubric judges and scores when a custom rubric tab is active and an answer exists.
  useEffect(() => {
    const activeRubric = activeTab > 0 ? rubrics[activeTab - 1] : null;
    const answerId = qaEntry?.answer?.id;
    if (!activeRubric || !answerId) {
      setRubricScores([]);
      setRubricJudges([]);
      return;
    }

    // Fetch judges for the rubric's category
    judgeApi.getByCategory(activeRubric.category, targetId)
      .then((res) => setRubricJudges(res.data))
      .catch(() => setRubricJudges([]));

    let cancelled = false;
    let pollTimer: number | null = null;

    const fetchScores = async () => {
      try {
        if (!cancelled) setRubricScoresLoading(true);
        const res = await rubricScoreApi.getForAnswer(answerId, activeRubric.id);
        if (cancelled) return;
        setRubricScores(res.data);
        setRubricScoresLoading(false);
        if (res.data.length === 0) {
          pollTimer = window.setTimeout(fetchScores, 5000);
        }
      } catch {
        if (!cancelled) {
          setRubricScores([]);
          setRubricScoresLoading(false);
          pollTimer = window.setTimeout(fetchScores, 5000);
        }
      }
    };

    fetchScores();

    return () => {
      cancelled = true;
      if (pollTimer !== null) window.clearTimeout(pollTimer);
    };
  }, [activeTab, rubrics, qaEntry?.answer?.id, targetId]);

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
      if (!checkworthyIds.has(score.claim_id)) return;
      if (score.label === null || score.label === undefined) return;
      scored += 1;
      if (score.label === false) inaccurate += 1;
    });
    return { totalCheckworthy: checkworthyIds.size, scored, inaccurate };
  }, [claims, claimScores]);

  const activeRubric = activeTab > 0 ? rubrics[activeTab - 1] : null;

  // For custom rubric tabs, show the first (recommended) judge
  const recommendedJudge = React.useMemo(
    () => rubricJudges[0] ?? null,
    [rubricJudges]
  );
  const recommendedScore = React.useMemo(
    () => recommendedJudge ? rubricScores.find((s) => s.judge_id === recommendedJudge.id) : undefined,
    [rubricScores, recommendedJudge]
  );

  if (!answer) {
    let message = "Waiting for target application answer to be generated before running primary judge.";
    if (job) {
      if (job.stage === QAJobStageEnum.STARTING || job.stage === QAJobStageEnum.GENERATING_ANSWERS) {
        message = "Target application is generating an answer for this question.";
      } else if (job.stage === QAJobStageEnum.PROCESSING_ANSWERS || job.stage === QAJobStageEnum.SCORING_ANSWERS) {
        message = "Primary judge is generating an evaluation for the answer.";
      }
    }
    return (
      <Stack spacing={3}>
        <QAJobProgress job={job} />
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="body1" color="text.secondary">{message}</Typography>
        </Paper>
      </Stack>
    );
  }

  if (!question) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          Select a question from the list to view details.
        </Typography>
      </Paper>
    );
  }

  return (
    <Stack>
      {/* Top bar: question ID + navigation */}
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

      {/* Rubric pill toggles */}
      <Stack direction="row" spacing={1} sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: "divider", bgcolor: "grey.50" }}>
        <Chip
          label="Accuracy"
          onClick={() => setActiveTab(0)}
          variant={activeTab === 0 ? "filled" : "outlined"}
          color={activeTab === 0 ? "primary" : "default"}
          sx={{ fontWeight: 600, fontSize: "0.85rem", height: 36, px: 1 }}
        />
        {rubrics.map((r, i) => (
          <Chip
            key={r.id}
            label={r.name}
            onClick={() => setActiveTab(i + 1)}
            variant={activeTab === i + 1 ? "filled" : "outlined"}
            color={activeTab === i + 1 ? "primary" : "default"}
            sx={{ fontWeight: 600, fontSize: "0.85rem", height: 36, px: 1 }}
          />
        ))}
      </Stack>

      {/* Tab panel: Accuracy */}
      {activeTab === 0 && (
        <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
          <Accordion disableGutters elevation={0} sx={{ bgcolor: "grey.50", "&::before": { display: "none" } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="overline" color="text.secondary">Rubric Criteria</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              <Typography variant="body2" sx={{ mb: 1 }}>
                Is the response factually accurate based on the knowledge base?
              </Typography>
              <Stack spacing={0.5}>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Typography variant="caption" fontWeight={700} sx={{ minWidth: 80 }}>Accurate</Typography>
                  <Typography variant="caption" color="text.secondary">The response accurately reflects the source information.</Typography>
                </Box>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Typography variant="caption" fontWeight={700} sx={{ minWidth: 80 }}>Inaccurate</Typography>
                  <Typography variant="caption" color="text.secondary">The response contains factual errors or omissions.</Typography>
                </Box>
              </Stack>
            </AccordionDetails>
          </Accordion>

          <Accordion disableGutters elevation={0} sx={{ bgcolor: "grey.50", "&::before": { display: "none" } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Typography variant="overline" color="text.secondary">Judge Verdict</Typography>
                {answerScore && (
                  <Chip
                    icon={answerScore.overall_label ? <CheckCircleIcon fontSize="small" /> : <CancelIcon fontSize="small" />}
                    label={answerScore.overall_label ? "Accurate" : "Inaccurate"}
                    color={answerScore.overall_label ? "success" : "error"}
                    size="small"
                  />
                )}
              </Stack>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              {answerScore ? (
                <Typography variant="body2" color="text.secondary">
                  {claimScoreSummary.totalCheckworthy === 0
                    ? "No claims found, answer defaults to accurate."
                    : claimScoreSummary.scored === 0
                      ? "Claims are still waiting on judge scores."
                      : claimScoreSummary.inaccurate > 0
                        ? `${claimScoreSummary.inaccurate}/${claimScoreSummary.scored} claim(s) unsupported — marked inaccurate.`
                        : `All ${claimScoreSummary.scored} claims supported — marked accurate.`}
                </Typography>
              ) : (
                <Typography variant="caption" color="text.disabled">No judge score yet.</Typography>
              )}
            </AccordionDetails>
          </Accordion>
        </Box>
      )}

      {/* Tab panel: custom rubric */}
      {activeTab > 0 && activeRubric && (
        <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
          <Accordion disableGutters elevation={0} sx={{ bgcolor: "grey.50", "&::before": { display: "none" } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="overline" color="text.secondary">Rubric Criteria</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              <Typography variant="body2" sx={{ mb: activeRubric.options.length > 0 ? 1.5 : 0 }}>
                {activeRubric.criteria || <em>No criteria defined.</em>}
              </Typography>
              {activeRubric.options.length > 0 && (
                <Stack spacing={0.5}>
                  {activeRubric.options.map((opt) => (
                    <Box key={opt.option} sx={{ display: "flex", gap: 1 }}>
                      <Typography variant="caption" fontWeight={700} sx={{ minWidth: 80 }}>{opt.option}</Typography>
                      <Typography variant="caption" color="text.secondary">{opt.description}</Typography>
                    </Box>
                  ))}
                </Stack>
              )}
            </AccordionDetails>
          </Accordion>

          <Accordion disableGutters elevation={0} sx={{ bgcolor: "grey.50", "&::before": { display: "none" } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Typography variant="overline" color="text.secondary">Judge Verdict</Typography>
                {recommendedScore && activeRubric && (() => {
                  const best = activeRubric.best_option || activeRubric.options?.[0]?.option || "";
                  const isPositive = recommendedScore.option_chosen === best;
                  return (
                    <Chip
                      label={recommendedScore.option_chosen}
                      size="small"
                      color={isPositive ? "success" : activeRubric.options.length <= 2 ? "error" : "primary"}
                    />
                  );
                })()}
              </Stack>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              {rubricScoresLoading ? (
                <Skeleton variant="rounded" width={160} height={24} />
              ) : !recommendedScore ? (
                <Typography variant="caption" color="text.disabled">No judge score yet.</Typography>
              ) : (
                <Typography variant="caption" color="text.secondary">{recommendedScore.explanation}</Typography>
              )}
            </AccordionDetails>
          </Accordion>
        </Box>
      )}

      {/* Answer + question chat display */}
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
                <Box display="flex" gap={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1.5 }}>
                  {persona && <Chip label={persona.title} size="small" />}
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
                {activeTab === 0 && claims.length > 0 ? (
                  <ClaimHighlighter
                    answerContent={answer.answer_content}
                    claims={claims}
                    claimScores={claimScores}
                  />
                ) : (
                  <Typography variant="body1" sx={{ p: 2, whiteSpace: "pre-wrap" }}>
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
