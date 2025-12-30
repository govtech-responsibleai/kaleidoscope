"use client";

import { useState, useEffect, useMemo } from "react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import { ResultRow, JudgeConfig, AnswerClaim, AnswerClaimScore, QuestionResponse, PersonaResponse } from "@/lib/types";
import { answerApi, questionApi, personaApi } from "@/lib/api";
import ClaimHighlighter from "@/components/annotation/ClaimHighlighter";

interface ResultsTableExpandedRowProps {
  result: ResultRow;
  reliableJudges: JudgeConfig[];
  selectedJudgeIds: number[];
}

interface ClaimsData {
  claims: AnswerClaim[];
  judgeScores: Map<number, AnswerClaimScore[]>; // judgeId -> scores
}

export default function ResultsTableExpandedRow({
  result,
  reliableJudges,
  selectedJudgeIds,
}: ResultsTableExpandedRowProps) {
  const [claimsData, setClaimsData] = useState<ClaimsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState<QuestionResponse | null>(null);
  const [persona, setPersona] = useState<PersonaResponse | null>(null);

  // Filter for claim-based judges only (response-level judges don't have claim scores)
  const claimBasedJudges = useMemo(
    () => reliableJudges.filter((j) => j.judge_type === "claim_based"),
    [reliableJudges]
  );

  // Filter selected judges to only claim-based ones
  const selectedClaimBasedJudgeIds = useMemo(
    () => selectedJudgeIds.filter((id) => claimBasedJudges.some((j) => j.id === id)),
    [selectedJudgeIds, claimBasedJudges]
  );

  // Fetch question and persona details
  useEffect(() => {
    const fetchQuestionAndPersona = async () => {
      try {
        const questionRes = await questionApi.get(result.question_id);
        setQuestion(questionRes.data);

        const personaRes = await personaApi.get(questionRes.data.persona_id);
        setPersona(personaRes.data);
      } catch (err) {
        console.error("Failed to fetch question/persona:", err);
      }
    };

    fetchQuestionAndPersona();
  }, [result.question_id]);

  // Fetch claims from all claim-based judges when component mounts
  useEffect(() => {
    const fetchClaims = async () => {
      if (claimBasedJudges.length === 0) {
        setLoading(false);
        // No claim-based judges - just show plain answer text
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const judgeScores = new Map<number, AnswerClaimScore[]>();
        let claims: AnswerClaim[] = [];

        // Fetch claims for each claim-based judge
        const fetchPromises = claimBasedJudges.map(async (judge) => {
          const response = await answerApi.getClaims(result.answer_id, judge.id);
          const data = response.data;

          // Store the claims (should be the same for all judges)
          // Use the raw claim data, stripping out the score property
          if (claims.length === 0 && data.claims.length > 0) {
            claims = data.claims.map(({ score, ...claim }) => claim as AnswerClaim);
          }

          // Extract claim scores for this judge
          // Important: Associate each score with its claim_id since the score object
          // may not have claim_id - it comes from the parent claim
          const scores: AnswerClaimScore[] = data.claims
            .filter((item) => item.score)
            .map((item) => ({
              ...item.score!,
              claim_id: item.id, // Ensure claim_id is set from the parent claim
            }));

          return { judgeId: judge.id, scores };
        });

        const results = await Promise.all(fetchPromises);

        // Populate the judgeScores map
        results.forEach(({ judgeId, scores }) => {
          judgeScores.set(judgeId, scores);
        });

        setClaimsData({ claims, judgeScores });
      } catch (err) {
        console.error("Failed to fetch claims:", err);
        setError("Failed to fetch claims. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchClaims();
  }, [result.answer_id, claimBasedJudges]);

  return (
    <Box sx={{ py: 3, px: 4, bgcolor: "rgba(0, 0, 0, 0.02)" }}>
      <Stack spacing={2}>
        {/* Question Metadata */}
        {(question || persona) && (
          <Box display="flex" gap={1} alignItems="center">
            {persona && (
              <Chip label={persona.title} size="small" />
            )}
            {question && (
              <>
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
              </>
            )}
          </Box>
        )}

        {/* Full Question */}
        <Box>
          <Typography variant="caption" fontWeight={600} color="text.secondary">
            Full Question:
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}>
            {result.question_text}
          </Typography>
        </Box>

        {/* Claims with Highlights */}
        <Box>
          <Typography variant="caption" fontWeight={600} color="text.secondary">
            Full Answer:
          </Typography>

          {loading && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Loading claims...
              </Typography>
            </Box>
          )}

          {error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {error}
            </Alert>
          )}

          {!loading && claimsData && claimsData.claims.length > 0 && (
            <Box sx={{ mt: 0.5 }}>
              <ClaimHighlighter
                answerContent={result.answer_content}
                claims={claimsData.claims}
                multiJudgeScores={claimsData.judgeScores}
                judges={claimBasedJudges}
                selectedJudgeIds={selectedClaimBasedJudgeIds}
              />
            </Box>
          )}

          {/* Fallback: show plain answer when no claims or no claim-based judges */}
          {!loading && !error && (!claimsData || claimsData.claims.length === 0) && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mt: 1, whiteSpace: "pre-wrap" }}
            >
              {result.answer_content}
            </Typography>
          )}
        </Box>
      </Stack>
    </Box>
  );
}
