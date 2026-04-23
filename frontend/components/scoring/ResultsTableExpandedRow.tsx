"use client";

import { useState, useEffect, useMemo } from "react";
import {
  Alert,
  Box,
  Chip,
  ChipProps,
  CircularProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  ScoringRowResult,
  JudgeConfig,
  AnswerClaim,
  AnswerClaimScore,
  QuestionResponse,
  PersonaResponse,
  TargetRubricResponse,
  RubricAnswerScore,
} from "@/lib/types";
import { answerApi, questionApi, personaApi, rubricScoreApi } from "@/lib/api";
import ClaimHighlighter from "@/components/annotation/ClaimHighlighter";
import { compactChipSx } from "@/lib/uiStyles";

interface ResultsTableExpandedRowProps {
  result: ScoringRowResult;
  targetId: number;
  tableJudges: JudgeConfig[];
  selectedJudgeIds: number[];
  rubrics: TargetRubricResponse[];
  activeRubricId: number | null;
  answerRubricLabels: Record<number, string>; // rubricId -> option_value
}

interface ClaimsData {
  claims: AnswerClaim[];
  judgeScores: Map<number, AnswerClaimScore[]>;
}

const isBinaryRubric = (rubric: TargetRubricResponse | null): boolean => (rubric?.options.length ?? 0) === 2;

const getRubricOptionColor = (
  value: string | null | undefined,
  rubric: TargetRubricResponse | null,
): ChipProps["color"] => {
  if (!value || !rubric) {
    return "default";
  }
  if (value === rubric.best_option) {
    return "success";
  }
  return isBinaryRubric(rubric) ? "error" : "primary";
};

export default function ResultsTableExpandedRow({
  result,
  targetId,
  tableJudges,
  selectedJudgeIds,
  rubrics,
  activeRubricId,
  answerRubricLabels,
}: ResultsTableExpandedRowProps) {
  const [claimsData, setClaimsData] = useState<ClaimsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState<QuestionResponse | null>(null);
  const [persona, setPersona] = useState<PersonaResponse | null>(null);
  const activeRubric = useMemo(
    () => activeRubricId !== null ? rubrics.find((rubric) => rubric.id === activeRubricId) ?? null : null,
    [activeRubricId, rubrics]
  );
  const isClaimBasedRubric = activeRubric?.scoring_mode === "claim_based";

  const claimBasedJudges = useMemo(
    () => isClaimBasedRubric ? tableJudges : [],
    [isClaimBasedRubric, tableJudges]
  );

  const selectedClaimBasedJudgeIds = useMemo(
    () => selectedJudgeIds.filter((id) => claimBasedJudges.some((j) => j.id === id)),
    [selectedJudgeIds, claimBasedJudges]
  );

  useEffect(() => {
    const fetchQuestionAndPersona = async () => {
      try {
        const questionRes = await questionApi.get(result.question_id);
        setQuestion(questionRes.data);
        if (questionRes.data.persona_id) {
          const personaRes = await personaApi.get(questionRes.data.persona_id);
          setPersona(personaRes.data);
        }
      } catch (err) {
        console.error("Failed to fetch question/persona:", err);
      }
    };
    fetchQuestionAndPersona();
  }, [result.question_id]);

  useEffect(() => {
    const fetchClaims = async () => {
      if (!isClaimBasedRubric || claimBasedJudges.length === 0 || activeRubricId === null) {
        setClaimsData(null);
        setLoading(false);
        return;
      }
      setLoading(true); setError(null);
      try {
        const judgeScores = new Map<number, AnswerClaimScore[]>();
        let claims: AnswerClaim[] = [];
        const fetchPromises = claimBasedJudges.map(async (judge) => {
          const response = await answerApi.getClaims(result.answer_id, judge.id, activeRubricId);
          const data = response.data;
          if (claims.length === 0 && data.claims.length > 0) {
            claims = data.claims.map((item) => {
              const claim = { ...item } as AnswerClaim & { score?: unknown };
              delete claim.score;
              return claim as AnswerClaim;
            });
          }
          const scores: AnswerClaimScore[] = data.claims
            .filter((item) => item.score)
            .map((item) => ({ ...item.score!, claim_id: item.id }));
          return { judgeId: judge.id, scores };
        });
        const results = await Promise.all(fetchPromises);
        results.forEach(({ judgeId, scores }) => judgeScores.set(judgeId, scores));
        setClaimsData({ claims, judgeScores });
      } catch (err) {
        console.error("Failed to fetch claims:", err);
        setError("Failed to fetch claims.");
      } finally {
        setLoading(false);
      }
    };
    fetchClaims();
  }, [result.answer_id, claimBasedJudges, isClaimBasedRubric, activeRubricId]);

  // Rubric scores and judges for custom rubric tabs
  const [rubricScores, setRubricScores] = useState<RubricAnswerScore[]>([]);

  useEffect(() => {
    if (!activeRubric || !result.answer_id) {
      setRubricScores([]);
      return;
    }

    rubricScoreApi.getForAnswer(result.answer_id, activeRubric.id)
      .then((res) => setRubricScores(res.data))
      .catch(() => setRubricScores([]));
  }, [activeRubric, result.answer_id, targetId]);
  const selectedJudges = useMemo(
    () => tableJudges.filter((judge) => selectedJudgeIds.includes(judge.id)),
    [tableJudges, selectedJudgeIds]
  );

  // Determine the best_option and recommended judge verdict for answer highlighting
  const bestOption = activeRubric?.best_option || activeRubric?.options?.[0]?.option || "";
  const recommendedJudge = useMemo(
    () => tableJudges[0] ?? null,
    [tableJudges]
  );
  const recommendedScore = useMemo(
    () => recommendedJudge ? rubricScores.find((s) => s.judge_id === recommendedJudge.id) : undefined,
    [rubricScores, recommendedJudge]
  );
  const isPositiveVerdict = recommendedScore ? recommendedScore.overall_label === bestOption : null;

  return (
    <Box sx={{ py: 2, px: 4, bgcolor: "grey.50", borderTop: 1, borderColor: "divider" }}>
      <Stack spacing={2}>
        <Box sx={{ p: 2, border: 1, borderColor: "divider", borderRadius: 1.5, bgcolor: "white" }}>
          <Typography variant="overline" color="text.secondary" display="block" sx={{ mb: 1 }}>
            Judge Verdicts
          </Typography>
          {selectedJudges.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No judges selected.
            </Typography>
          ) : (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {selectedJudges.map((judge) => {
                const score = rubricScores.find((entry) => entry.judge_id === judge.id);
                return (
                  <Box
                    key={judge.id}
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      px: 1.25,
                      py: 0.75,
                      border: 1,
                      borderColor: "divider",
                      borderRadius: 999,
                      bgcolor: "grey.50",
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ whiteSpace: "normal", lineHeight: 1.35 }}>
                      {judge.name}
                    </Typography>
                    <Chip
                      label={score?.overall_label ?? "Missing"}
                      size="small"
                      color={score ? getRubricOptionColor(score.overall_label, activeRubric) : "default"}
                      sx={compactChipSx}
                    />
                  </Box>
                );
              })}
            </Stack>
          )}
        </Box>

        {/* Question & Answer Chat Bubbles */}
        <Stack spacing={2}>
          <Box display="flex" justifyContent="flex-end">
            <Box sx={{
              maxWidth: { xs: "100%", sm: "75%" }, bgcolor: "grey.100",
              px: 3, py: 1.5, borderRadius: "30px 30px 0 30px",
            }}>
              <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>{result.question_text}</Typography>
              {(question || persona) && (
                <Box display="flex" gap={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1.5 }}>
                  {persona && <Chip label={persona.title} size="small" />}
                  {question && (
                    <>
                      <Chip label={question.type} size="small"
                        color={question.type === "edge" ? "warning" : "default"}
                        variant={question.type === "edge" ? "filled" : "outlined"} />
                      <Chip label={question.scope === "in_kb" ? "In KB" : "Out KB"} size="small"
                        color={question.scope === "in_kb" ? "success" : "info"} variant="outlined" />
                    </>
                  )}
                </Box>
              )}
            </Box>
          </Box>

          <Box display="flex" justifyContent="flex-start">
            <Box sx={{
              maxWidth: { xs: "100%", sm: "85%" },
              ...(isClaimBasedRubric && { px: 1, py: 0.5 }),
              borderRadius: "30px 30px 30px 0",
              border: (theme) => `1px solid ${theme.palette.divider}`,
              bgcolor: "white",
              overflow: "hidden",
            }}>
              {loading && (
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, p: 2 }}>
                  <CircularProgress size={20} />
                  <Typography variant="body2" color="text.secondary">Loading claims...</Typography>
                </Box>
              )}
              {error && <Alert severity="error" sx={{ m: 1 }}>{error}</Alert>}
              {!loading && !error && isClaimBasedRubric && claimsData && claimsData.claims.length > 0 && (
                <ClaimHighlighter
                  answerContent={result.answer_content}
                  claims={claimsData.claims}
                  multiJudgeScores={claimsData.judgeScores}
                  judges={claimBasedJudges}
                  selectedJudgeIds={selectedClaimBasedJudgeIds}
                  missingScoreMessage="Claim score missing unexpectedly after evaluation completed."
                  instrumentationContext={{
                    surface: "scoring-expanded-row",
                    answerId: result.answer_id,
                    questionId: result.question_id,
                    selectedJudgeIds: selectedClaimBasedJudgeIds,
                  }}
                />
              )}
              {!loading && !error && isClaimBasedRubric && (!claimsData || claimsData.claims.length === 0) && (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2, whiteSpace: "pre-wrap" }}>
                  {result.answer_content}
                </Typography>
              )}
              {!isClaimBasedRubric && activeRubric && (
                <Tooltip
                  title={
                    rubricScores.length === 0 ? "No judge scores yet" : (
                      <Stack spacing={1}>
                        {(() => {
                          return tableJudges.map((judge) => {
                            const score = rubricScores.find((s) => s.judge_id === judge.id);
                            if (!score) return null;
                            const displayName = judge.name;
                            const isPositive = score.overall_label === bestOption;
                            return (
                              <Box
                                key={judge.id}
                                sx={{
                                  p: 1,
                                  borderRadius: 1,
                                  bgcolor: isPositive ? "rgba(99, 199, 125, 0.15)" : "rgba(255, 99, 99, 0.15)",
                                  borderLeft: 3,
                                  borderColor: isPositive ? "success.main" : "error.main",
                                }}
                              >
                                <Typography
                                  variant="caption"
                                  fontWeight={600}
                                  sx={{ color: isPositive ? "rgba(144, 238, 144, 1)" : "rgba(255, 182, 182, 1)" }}
                                >
                                  {displayName}: {score.overall_label}
                                </Typography>
                                {score.explanation && (
                                  <Typography variant="body2" sx={{ mt: 0.5, fontSize: "0.75rem" }}>
                                    {score.explanation}
                                  </Typography>
                                )}
                              </Box>
                            );
                          });
                        })()}
                      </Stack>
                    )
                  }
                  placement="top"
                  arrow
                  slotProps={{
                    tooltip: { sx: { fontSize: "0.8rem", px: 1.5, py: 1, maxWidth: 480 } },
                    arrow: { sx: { fontSize: 14 } },
                  }}
                >
                  <Box sx={{
                    px: 3, py: 2,
                    cursor: "default",
                    transition: "background-color 0.2s ease",
                    ...(isPositiveVerdict === true && {
                      bgcolor: "rgba(46, 125, 50, 0.08)",
                      borderLeft: "3px solid",
                      borderLeftColor: "success.main",
                      "&:hover": { bgcolor: "rgba(46, 125, 50, 0.15)" },
                    }),
                    ...(isPositiveVerdict === false && {
                      bgcolor: "rgba(211, 47, 47, 0.08)",
                      borderLeft: "3px solid",
                      borderLeftColor: "error.main",
                      "&:hover": { bgcolor: "rgba(211, 47, 47, 0.15)" },
                    }),
                    ...(isPositiveVerdict === null && {
                      bgcolor: "rgba(0, 0, 0, 0.04)",
                      "&:hover": { bgcolor: "rgba(0, 0, 0, 0.08)" },
                    }),
                  }}>
                    <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                      {result.answer_content}
                    </Typography>
                  </Box>
                </Tooltip>
              )}
            </Box>
          </Box>
        </Stack>

        {/* Active rubric: human annotation + criteria */}
        {activeRubric && (
          <Box sx={{ p: 2, border: 1, borderColor: "divider", borderRadius: 1, bgcolor: "white" }}>
            <Typography variant="overline" color="text.secondary" display="block" sx={{ mb: 1 }}>
              {activeRubric.name} — Annotation
            </Typography>

            {answerRubricLabels[activeRubric.id] ? (
              <Box sx={{ mb: 1.5 }}>
                <Typography variant="caption" color="text.secondary">Human label: </Typography>
                <Chip
                  label={answerRubricLabels[activeRubric.id]}
                  size="small"
                  color={answerRubricLabels[activeRubric.id] === bestOption ? "success" : activeRubric.options.length <= 2 ? "error" : "primary"}
                  sx={{ ml: 0.5 }}
                />
              </Box>
            ) : (
              <Typography variant="body2" color="text.disabled" sx={{ mb: 1.5, fontStyle: "italic" }}>
                Not yet annotated for this rubric.
              </Typography>
            )}

            {activeRubric.criteria && (
              <Box>
                <Typography variant="caption" fontWeight={600} color="text.secondary">Criteria</Typography>
                <Typography variant="body2" sx={{ mt: 0.25 }}>{activeRubric.criteria}</Typography>
              </Box>
            )}

            {activeRubric.options.length > 0 && (
              <Stack spacing={0.5} sx={{ mt: 1.5 }}>
                {activeRubric.options.map((opt) => (
                  <Box key={opt.option} sx={{ display: "flex", gap: 1 }}>
                    <Typography
                      variant="caption"
                      fontWeight={700}
                      sx={{
                        minWidth: 80,
                        color: answerRubricLabels[activeRubric.id] === opt.option
                          ? (opt.option === bestOption ? "success.main" : activeRubric.options.length <= 2 ? "error.main" : "primary.main")
                          : "text.secondary",
                      }}
                    >
                      {opt.option}
                      {answerRubricLabels[activeRubric.id] === opt.option && " ✓"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">{opt.description}</Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </Box>
        )}
      </Stack>
    </Box>
  );
}
