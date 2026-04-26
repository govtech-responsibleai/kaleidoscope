"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Chip,
  Paper,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { QAJob, QuestionResponse, QARecord, QAJobStageEnum, PersonaResponse, TargetRubricResponse, RubricAnswerScore, JudgeConfig, QARubricStatus } from "@/lib/types";
import { rubricScoreApi, judgeApi, qaJobApi } from "@/lib/api";
import ClaimHighlighter from "./ClaimHighlighter";
import QAJobProgress from "./QAJobProgress";

interface QAContentProps {
  targetId: number;
  question: QuestionResponse | null;
  persona: PersonaResponse | null;
  qaEntry?: QARecord;
  job: QAJob | null;
  activeRubric: TargetRubricResponse | null;
  pendingRubricIds?: number[];
}

export default function QAContent({
  targetId,
  question,
  persona,
  qaEntry,
  job,
  activeRubric,
  pendingRubricIds = [],
}: QAContentProps) {
  const [rubricScores, setRubricScores] = useState<RubricAnswerScore[]>([]);
  const [rubricScoresLoading, setRubricScoresLoading] = useState(false);
  const [rubricJudges, setRubricJudges] = useState<JudgeConfig[]>([]);
  const [jobDetail, setJobDetail] = useState<QAJob | null>(job);
  const [rubricVerdictLoading, setRubricVerdictLoading] = useState(false);
  const hasLoadedJobDetailRef = useRef(false);
  const isClaimBasedRubric = activeRubric?.scoring_mode === "claim_based";

  useEffect(() => {
    const answerId = qaEntry?.answer?.id;
    if (!activeRubric || !answerId) {
      setRubricScores([]);
      setRubricJudges([]);
      setJobDetail(job);
      setRubricVerdictLoading(false);
      return;
    }

    judgeApi.getForRubric(activeRubric.id, targetId)
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
        if (pendingRubricIds.includes(activeRubric.id)) {
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
  }, [activeRubric, qaEntry?.answer?.id, targetId, pendingRubricIds, job]);

  useEffect(() => {
    if (!job?.id) {
      setJobDetail(job);
      setRubricVerdictLoading(false);
      hasLoadedJobDetailRef.current = false;
      return;
    }

    let cancelled = false;
    let pollTimer: number | null = null;

    const fetchJobDetail = async () => {
      try {
        if (!cancelled && !hasLoadedJobDetailRef.current) setRubricVerdictLoading(true);
        const response = await qaJobApi.get(job.id);
        if (cancelled) return;
        const fetched = response.data;
        setJobDetail((prev) => {
          if (
            prev?.id === fetched.id &&
            prev?.status === fetched.status &&
            prev?.stage === fetched.stage &&
            JSON.stringify(prev?.rubric_statuses) === JSON.stringify(fetched.rubric_statuses)
          ) {
            return prev;
          }
          return fetched;
        });
        hasLoadedJobDetailRef.current = true;
        if (fetched.stage !== QAJobStageEnum.COMPLETED && fetched.status === "running") {
          pollTimer = window.setTimeout(fetchJobDetail, 5000);
        }
      } catch {
        if (!cancelled && job.stage !== QAJobStageEnum.COMPLETED && job.status === "running") {
          pollTimer = window.setTimeout(fetchJobDetail, 5000);
        }
      } finally {
        if (!cancelled) setRubricVerdictLoading(false);
      }
    };

    void fetchJobDetail();
    return () => {
      cancelled = true;
      if (pollTimer !== null) window.clearTimeout(pollTimer);
    };
  }, [job?.id, job?.status, job?.stage]);

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

  const isActiveRubricPending = Boolean(activeRubric && pendingRubricIds.includes(activeRubric.id));

  // For custom rubric tabs, show the first (recommended) judge
  const recommendedJudge = React.useMemo(
    () => rubricJudges[0] ?? null,
    [rubricJudges]
  );
  const recommendedScore = React.useMemo(
    () => recommendedJudge ? rubricScores.find((s) => s.judge_id === recommendedJudge.id) : undefined,
    [rubricScores, recommendedJudge]
  );
  const activeMetricStatus: QARubricStatus | null = React.useMemo(() => {
    const activeRubricId = activeRubric?.id ?? null;
    if (!activeRubricId) return null;
    return jobDetail?.rubric_statuses?.find((status) => status.rubric_id === activeRubricId) ?? null;
  }, [activeRubric?.id, jobDetail?.rubric_statuses]);
  const verdictScore = activeMetricStatus?.score;

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
      <Stack spacing={3} sx={{ p: 2 }}>
        <QAJobProgress job={job} />
        <Typography variant="body2" color="text.secondary">{message}</Typography>
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
      <QAJobProgress job={job} />

      {/* Judge verdict — inline, no accordion */}
      <Box sx={{
        p: 2,
        bgcolor: isClaimBasedRubric
          ? (answerScore ? (answerScore.overall_label === activeRubric?.best_option ? "#f0faf0" : "#fef0f0") : undefined)
          : (verdictScore
            ? ((verdictScore.value === (activeRubric?.best_option || activeRubric?.options?.[0]?.option || "")) ? "#f0faf0" : "#fef0f0")
            : undefined),
      }}>
        {isClaimBasedRubric ? (
          <Stack spacing={1}>
            {answerScore ? (
              <>
                <Typography variant="body2" color="text.primary">
                  <Tooltip title="AI-generated evaluation — always verify with your own judgement before annotating." placement="top" arrow>
                    <Box component="span" color="text.disabled" sx={{ cursor: "help", mr: 0.5 }}>ⓘ</Box>
                  </Tooltip>
                  Judge recommends{" "}
                  <Box component="span" fontWeight={700} color={answerScore.overall_label === activeRubric?.best_option ? "success.main" : "error.main"}>
                    {answerScore.overall_label}
                  </Box>
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ px: 2, lineHeight: 1.5 }}>
                  {claimScoreSummary.totalCheckworthy === 0
                    ? "No claims found, answer defaults to accurate."
                    : claimScoreSummary.scored === 0
                      ? "Claims are still waiting on judge scores."
                      : claimScoreSummary.inaccurate > 0
                        ? `${claimScoreSummary.inaccurate}/${claimScoreSummary.scored} claim(s) unsupported — marked inaccurate.`
                        : `All ${claimScoreSummary.scored} claims supported — marked accurate.`}
                </Typography>
              </>
            ) : (
              <Typography
                variant="body2"
                color={activeMetricStatus?.state === "job_failed" ? "error.main" : "text.disabled"}
              >
                {activeMetricStatus?.message ?? "Verdict pending"}
              </Typography>
            )}
          </Stack>
        ) : activeRubric ? (
          <Stack spacing={1}>
            {rubricVerdictLoading ? (
              <Skeleton variant="text" width={220} height={24} />
            ) : activeMetricStatus?.state === "success" && activeMetricStatus.score ? (() => {
              const best = activeRubric.best_option || activeRubric.options?.[0]?.option || "";
              const isPositive = activeMetricStatus.score.value === best;
              const color = isPositive ? "success.main" : activeRubric.options.length <= 2 ? "error.main" : "text.primary";
              return (
                <>
                  <Typography variant="body2" color="text.primary">
                    <Tooltip title="AI-generated evaluation — always verify with your own judgement before annotating." placement="top" arrow>
                      <Box component="span" color="text.disabled" sx={{ cursor: "help", mr: 0.5 }}>ⓘ</Box>
                    </Tooltip>
                    Judge recommends{" "}
                    <Box component="span" fontWeight={700} color={color}>
                      {activeMetricStatus.score.value}
                    </Box>
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ px:2, lineHeight: 1.5 }}>
                    {activeMetricStatus.score.explanation}
                  </Typography>
                </>
              );
            })() : (
              <Typography
                variant="body2"
                color={
                  activeMetricStatus?.state === "job_failed"
                    ? "error.main"
                    : activeMetricStatus?.state === "pending_evaluation" ||
                      activeMetricStatus?.state === "awaiting_answer" ||
                      activeMetricStatus?.state === "no_judge_configured"
                    ? "warning.main"
                    : isActiveRubricPending
                    ? "warning.main"
                    : "text.disabled"
                }
              >
                {activeMetricStatus?.message ?? (isActiveRubricPending ? "Pending rubric evaluation" : "No judge verdict available")}
              </Typography>
            )}
          </Stack>
        ) : null}

      </Box>

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
                  borderRadius: "30px 30px 30px 0",
                  border: (theme) => `1px solid ${theme.palette.divider}`,
                }}
              >
                {isClaimBasedRubric && claims.length > 0 ? (
                <ClaimHighlighter
                  answerContent={answer.answer_content}
                  claims={claims}
                  claimScores={claimScores}
                  isProcessingClaimScores={job?.status === "running"}
                  missingScoreMessage="Claim score missing unexpectedly after evaluation completed."
                  instrumentationContext={{
                    surface: "annotation",
                    answerId: answer.id,
                    questionId: question.id,
                    snapshotJobId: job?.id ?? null,
                  }}
                />
              ) : (
                  <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", p:2, lineHeight: 1.5 }}>
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
