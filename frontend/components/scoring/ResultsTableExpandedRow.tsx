"use client";

import { useState, useEffect, useMemo } from "react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  ResultRow,
  JudgeConfig,
  AnswerClaim,
  AnswerClaimScore,
  QuestionResponse,
  PersonaResponse,
  TargetRubricResponse,
  RubricAnswerScore,
} from "@/lib/types";
import { answerApi, questionApi, personaApi, rubricScoreApi, judgeApi } from "@/lib/api";
import ClaimHighlighter from "@/components/annotation/ClaimHighlighter";

interface ResultsTableExpandedRowProps {
  result: ResultRow;
  reliableJudges: JudgeConfig[];
  selectedJudgeIds: number[];
  rubrics: TargetRubricResponse[];
  activeRubricId: number | null;
  answerRubricLabels: Record<number, string>; // rubricId -> option_value
}

interface ClaimsData {
  claims: AnswerClaim[];
  judgeScores: Map<number, AnswerClaimScore[]>;
}

export default function ResultsTableExpandedRow({
  result,
  reliableJudges,
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

  // Local rubric tab (starts synced to the table-level activeRubricId, but can be changed independently)
  const [localActiveRubricId, setLocalActiveRubricId] = useState<number | null>(activeRubricId);

  // Sync when parent changes
  useEffect(() => {
    setLocalActiveRubricId(activeRubricId);
  }, [activeRubricId]);

  const claimBasedJudges = useMemo(
    () => reliableJudges.filter((j) => j.judge_type === "claim_based"),
    [reliableJudges]
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
      if (claimBasedJudges.length === 0) { setLoading(false); return; }
      setLoading(true); setError(null);
      try {
        const judgeScores = new Map<number, AnswerClaimScore[]>();
        let claims: AnswerClaim[] = [];
        const fetchPromises = claimBasedJudges.map(async (judge) => {
          const response = await answerApi.getClaims(result.answer_id, judge.id);
          const data = response.data;
          if (claims.length === 0 && data.claims.length > 0) {
            claims = data.claims.map(({ score, ...claim }) => claim as AnswerClaim);
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
  }, [result.answer_id, claimBasedJudges]);

  // Rubric scores and judges for custom rubric tabs
  const [rubricScores, setRubricScores] = useState<RubricAnswerScore[]>([]);
  const [rubricJudges, setRubricJudges] = useState<JudgeConfig[]>([]);

  useEffect(() => {
    const activeRubric = localActiveRubricId !== null ? rubrics.find((r) => r.id === localActiveRubricId) : null;
    if (!activeRubric || !result.answer_id) {
      setRubricScores([]);
      setRubricJudges([]);
      return;
    }

    judgeApi.getByCategory(activeRubric.category)
      .then((res) => setRubricJudges(res.data))
      .catch(() => setRubricJudges([]));

    rubricScoreApi.getForAnswer(result.answer_id, activeRubric.id)
      .then((res) => setRubricScores(res.data))
      .catch(() => setRubricScores([]));
  }, [localActiveRubricId, rubrics, result.answer_id]);

  const tabValue = localActiveRubricId === null ? 0 : rubrics.findIndex((r) => r.id === localActiveRubricId) + 1;
  const activeRubric = localActiveRubricId !== null ? rubrics.find((r) => r.id === localActiveRubricId) : null;

  // Determine the best_option and recommended judge verdict for answer highlighting
  const bestOption = activeRubric?.best_option || activeRubric?.options?.[0]?.option || "";
  const recommendedJudge = useMemo(
    () => rubricJudges.find((j) => j.category !== "common"),
    [rubricJudges]
  );
  const recommendedScore = useMemo(
    () => recommendedJudge ? rubricScores.find((s) => s.judge_id === recommendedJudge.id) : undefined,
    [rubricScores, recommendedJudge]
  );
  const isPositiveVerdict = recommendedScore ? recommendedScore.option_chosen === bestOption : null;

  return (
    <Box sx={{ py: 2, px: 4, bgcolor: "grey.50", borderTop: 1, borderColor: "divider" }}>
      {/* Rubric tabs inside the collapse */}
      {rubrics.length > 0 && (
        <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}>
          <Tabs
            value={tabValue}
            onChange={(_, v) => setLocalActiveRubricId(v === 0 ? null : rubrics[v - 1].id)}
            sx={{ minHeight: 36, "& .MuiTab-root": { minHeight: 36, py: 0, fontSize: "0.78rem", textTransform: "none", fontWeight: 500 } }}
          >
            <Tab label="Accuracy" />
            {rubrics.map((r) => <Tab key={r.id} label={r.name} />)}
          </Tabs>
        </Box>
      )}

      <Stack spacing={2}>
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
              ...(localActiveRubricId === null && { px: 1, py: 0.5 }),
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
              {/* Accuracy tab: claim-level highlighting */}
              {!loading && !error && localActiveRubricId === null && claimsData && claimsData.claims.length > 0 && (
                <ClaimHighlighter
                  answerContent={result.answer_content}
                  claims={claimsData.claims}
                  multiJudgeScores={claimsData.judgeScores}
                  judges={claimBasedJudges}
                  selectedJudgeIds={selectedClaimBasedJudgeIds}
                />
              )}
              {/* Accuracy tab: no claims fallback */}
              {!loading && !error && localActiveRubricId === null && (!claimsData || claimsData.claims.length === 0) && (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2, whiteSpace: "pre-wrap" }}>
                  {result.answer_content}
                </Typography>
              )}
              {/* Custom rubric tab: whole-response highlighting with hover tooltip */}
              {localActiveRubricId !== null && (
                <Tooltip
                  title={
                    rubricScores.length === 0 ? "No judge scores yet" : (
                      <Stack spacing={1}>
                        {(() => {
                          const sorted = [...rubricJudges].sort((a, b) =>
                            (a.category === "common" ? 1 : 0) - (b.category === "common" ? 1 : 0)
                          );
                          let secondaryIdx = 0;
                          let recommendedAssigned = false;
                          return sorted.map((judge) => {
                            const score = rubricScores.find((s) => s.judge_id === judge.id);
                            if (!score) return null;
                            let displayName: string;
                            if (judge.category !== "common" && !recommendedAssigned) {
                              displayName = "Recommended Judge";
                              recommendedAssigned = true;
                            } else {
                              displayName = `Secondary Judge ${++secondaryIdx}`;
                            }
                            const isPositive = score.option_chosen === bestOption;
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
                                  {displayName}: {score.option_chosen}
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

        {/* Custom rubric: human annotation + criteria */}
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
