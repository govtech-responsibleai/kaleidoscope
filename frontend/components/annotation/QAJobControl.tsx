"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  IconPlayerPause,
  IconPlayerPlay,
} from "@tabler/icons-react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
} from "@mui/material";
import {
  Answer,
  QAJob,
  QAJobStageEnum,
  JobStatus,
  QAMap,
  QARecord,
  TargetRubricResponse,
  RubricSpec,
} from "@/lib/types";
import { answerApi, getApiErrorMessage, qaJobApi, questionApi, targetApi } from "@/lib/api";
import { actionIconProps } from "@/lib/iconStyles";
import {
  buildMissingRubricCoverage,
  emptyMissingRubricCoverage,
  hasMissingRubricCoverage,
  type MissingRubricCoverage,
} from "@/lib/evaluationCoverage";

interface QAJobControlProps {
  targetId: number;
  snapshotId: number | null;
  approvedQuestionIds: number[];
  qaJobs: QAJob[];
  setQaJobs: React.Dispatch<React.SetStateAction<QAJob[]>>;
  qaMap: QAMap;
  setQaMap: React.Dispatch<React.SetStateAction<QAMap>>;
  rubrics?: TargetRubricResponse[];
  onRubricCoverageChange?: (coverage: MissingRubricCoverage) => void;
  onError?: (message: string) => void;
}

type ControlState = "start" | "pause" | "resume" | "disabled";

/**
 * Merge updated jobs into an existing list by id. Existing jobs are replaced
 * with their updated version; jobs not present in `updated` are preserved;
 * new jobs in `updated` that aren't in `prev` are appended.
 */
const mergeJobs = (prev: QAJob[], updated: QAJob[]): QAJob[] => {
  const byId = new Map(updated.map((job) => [job.id, job]));
  const merged = prev.map((job) => byId.get(job.id) ?? job);
  const prevIds = new Set(prev.map((job) => job.id));
  const appended = updated.filter((job) => !prevIds.has(job.id));
  return [...merged, ...appended];
};

export default function QAJobControl({
  targetId,
  snapshotId,
  approvedQuestionIds,
  qaJobs,
  setQaJobs,
  qaMap,
  setQaMap,
  rubrics,
  onRubricCoverageChange,
  onError,
}: QAJobControlProps) {
  const [jobInAction, setJobInAction] = useState(false);
  const [loadingInitialData, setLoadingInitialData] = useState(true);
  const pollingIntervalRef = useRef<number | null>(null);
  const qaMapRef = useRef<QAMap>({});
  const activeSnapshotIdRef = useRef<number | null>(null);
  const onErrorRef = useRef(onError);
  const defaultSelectionAttemptedRef = useRef<Set<number>>(new Set());
  const defaultSelectionInFlightRef = useRef<Set<number>>(new Set());
  const [missingRubricCoverage, setMissingRubricCoverage] = useState<MissingRubricCoverage>(emptyMissingRubricCoverage);
  const [resolvedRubricSpecs, setResolvedRubricSpecs] = useState<RubricSpec[]>([]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    onRubricCoverageChange?.(missingRubricCoverage);
  }, [missingRubricCoverage, onRubricCoverageChange]);

  const notifyError = useCallback((message: string) => {
    onErrorRef.current?.(message);
  }, []);

  const claimBasedRubricId = useMemo(
    () => rubrics?.find((rubric) => rubric.scoring_mode === "claim_based")?.id ?? null,
    [rubrics]
  );

  const claimBasedJudgeId = useMemo(() => {
    if (!claimBasedRubricId) return null;
    const spec = resolvedRubricSpecs.find((entry) => entry.rubric_id === claimBasedRubricId);
    return spec?.judge_id ?? null;
  }, [claimBasedRubricId, resolvedRubricSpecs]);

  const getClaimBasedJudgeIdForJob = useCallback((job: QAJob): number | null => {
    if (!claimBasedRubricId) {
      return job.judge_id ?? null;
    }
    const jobSpec = job.rubric_specs?.find((entry) => entry.rubric_id === claimBasedRubricId);
    if (jobSpec) {
      return jobSpec.judge_id;
    }
    return job.judge_id ?? claimBasedJudgeId ?? null;
  }, [claimBasedJudgeId, claimBasedRubricId]);

  // refs don't trigger re-renders
  useEffect(() => {
    qaMapRef.current = qaMap;
  }, [qaMap]);

  useEffect(() => {
    activeSnapshotIdRef.current = snapshotId;
  }, [snapshotId]);

  // With one job per question, completed count = jobs in terminal state
  const questionsFullyComplete = useMemo(() => {
    return qaJobs.filter(
      (j) => j.status === JobStatus.COMPLETED
    ).length;
  }, [qaJobs]);

  const totalQuestions = qaJobs.length;

  // Update STATUS counts
  const statusGroups = useMemo(() => {
    return qaJobs.reduce(
      (groups, job) => {
        groups[job.status] = (groups[job.status] ?? 0) + 1;
        return groups;
      },
      {
        [JobStatus.RUNNING]: 0,
        [JobStatus.COMPLETED]: 0,
        [JobStatus.FAILED]: 0,
        [JobStatus.PAUSED]: 0,
      } as Record<JobStatus, number>
    );
  }, [qaJobs]);

  const runningCount = statusGroups[JobStatus.RUNNING] ?? 0;
  const failedCount = statusGroups[JobStatus.FAILED] ?? 0;
  const pausedCount = statusGroups[JobStatus.PAUSED] ?? 0;

  // Track questions without answers (fetched from backend)
  const [questionsWithoutAnswers, setQuestionsWithoutAnswers] = useState<number[]>([]);
  const approvedQuestionIdSet = useMemo(() => new Set(approvedQuestionIds), [approvedQuestionIds]);

  // Fetch helpers — return partial QARecord data without calling setQaMap.
  // The hydrate effect collects all partials and applies them in a single batch.

  const fetchAnswer = useCallback(
    async (job: QAJob): Promise<Partial<QARecord> | null> => {
      if (!job.answer_id) return null;
      const entry = qaMapRef.current[job.question_id];
      if (entry?.answer && entry.answer.id === job.answer_id && entry.answer.answer_content) {
        return null;
      }
      try {
        const response = await answerApi.get(job.answer_id);
        return { answer: response.data };
      } catch (err) {
        console.error("Failed to fetch answer:", err);
        notifyError("Unable to load answers for this snapshot.");
        return null;
      }
    },
    [notifyError]
  );

  const fetchClaims = useCallback(
    async (job: QAJob): Promise<Partial<QARecord> | null> => {
      const judgeId = getClaimBasedJudgeIdForJob(job);
      if (!job.answer_id || !judgeId) return null;
      const entry = qaMapRef.current[job.question_id];
      if (entry?.claims && entry.claims.length > 0) {
        return null;
      }
      try {
        const response = await answerApi.getClaims(
          job.answer_id,
          judgeId,
          claimBasedRubricId ?? undefined,
        );
        const claims = response.data.claims.map((item) => {
          const claim = { ...item };
          delete claim.score;
          return claim;
        });
        const claimScores = response.data.claims
          .map((item) => item.score)
          .filter((score): score is NonNullable<typeof score> => Boolean(score));
        return { claims, claimScores };
      } catch (err) {
        console.error("Failed to fetch claims:", err);
        return null;
      }
    },
    [claimBasedRubricId, getClaimBasedJudgeIdForJob]
  );

  const fetchScore = useCallback(
    async (job: QAJob): Promise<Partial<QARecord> | null> => {
      const judgeId = getClaimBasedJudgeIdForJob(job);
      if (!job.answer_id || !judgeId) return null;
      const entry = qaMapRef.current[job.question_id];
      if (entry?.answerScore) {
        return null;
      }
      try {
        const response = await answerApi.getScores(
          job.answer_id,
          judgeId,
          claimBasedRubricId ?? undefined,
        );
        return { answerScore: response.data, claimScores: response.data.claim_scores };
      } catch (err) {
        console.error("Failed to fetch score:", err);
        return null;
      }
    },
    [claimBasedRubricId, getClaimBasedJudgeIdForJob]
  );

  useEffect(() => {
    let cancelled = false;

    const loadRubricSpecs = async () => {
      try {
        const response = await targetApi.getRubricSpecs(targetId);
        if (cancelled) return;
        setResolvedRubricSpecs(Object.values(response.data));
      } catch (err) {
        console.error("Failed to load rubric specs:", err);
        if (!cancelled) {
          setResolvedRubricSpecs([]);
          notifyError(getApiErrorMessage(err, "Failed to load rubric judge configuration."));
        }
      }
    };

    void loadRubricSpecs();

    return () => {
      cancelled = true;
    };
  }, [targetId, notifyError]);

  // Load existing answers and jobs when snapshot changes
  useEffect(() => {
    if (!snapshotId) {
      return;
    }

    let cancelled = false;

    const loadData = async () => {
      setLoadingInitialData(true);
      try {
        const [jobsResponse, answersResponse] = await Promise.all([
          qaJobApi.list(snapshotId),
          answerApi.list(snapshotId),
        ]);

        if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;

        const allJobs = jobsResponse.data.filter((job) => approvedQuestionIdSet.has(job.question_id));
        setQaJobs(allJobs);

        const answers = answersResponse.data.answers;

        // Ensure any already annotated answers stay in the annotation set.
        const annotatedNeedingSelection = answers.filter(
          (answer) => answer.has_annotation && !answer.is_selected_for_annotation
        );
        let normalizedAnswers = answers;

        if (annotatedNeedingSelection.length > 0) {
          try {
            await answerApi.bulkSelection(snapshotId, {
              selections: annotatedNeedingSelection.map((answer) => ({
                answer_id: answer.id,
                is_selected: true,
              })),
            });
            if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;
            const annotatedIds = new Set(annotatedNeedingSelection.map((answer) => answer.id));
            normalizedAnswers = answers.map((answer) =>
              annotatedIds.has(answer.id)
                ? { ...answer, is_selected_for_annotation: true }
                : answer
            );
          } catch (err) {
            console.error("Failed to sync annotation selections:", err);
            notifyError("Some annotated answers temporarily dropped out of the annotation set.");
          }
        }

        if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;

        setQaMap(() => {
          const initial: QAMap = { ...qaMapRef.current };
          normalizedAnswers.forEach((answer) => {
            const existing = initial[answer.question_id];
            initial[answer.question_id] = {
              ...existing,
              questionId: answer.question_id,
              answer,
            };
          });
          qaMapRef.current = initial;
          return initial;
        });
      } catch (err) {
        console.error("Failed to load QA data:", err);
        notifyError("Failed to load QA data for this snapshot.");
      } finally {
        if (!cancelled && snapshotId === activeSnapshotIdRef.current) {
          setLoadingInitialData(false);
        }
      }
    };

    loadData();

    return () => {
      cancelled = true;
    };
  }, [snapshotId, approvedQuestionIdSet, setQaJobs, setQaMap, notifyError]);

  // Fetch questions without answers when snapshot or judge changes
  useEffect(() => {
    if (!snapshotId) {
      setQuestionsWithoutAnswers([]);
      return;
    }

    let cancelled = false;

    const fetchQuestionsWithoutAnswers = async () => {
      try {
        const response = await questionApi.listApprovedWithoutAnswers(snapshotId);
        if (!cancelled) {
          const questionIds = response.data.map((q) => q.id);
          setQuestionsWithoutAnswers(questionIds);
        }
      } catch (err) {
        console.error("Failed to fetch questions without answers:", err);
        if (!cancelled) {
          setQuestionsWithoutAnswers([]);
        }
      }
    };

    fetchQuestionsWithoutAnswers();

    return () => {
      cancelled = true;
    };
  }, [snapshotId, qaJobs]);

  // Update QA data as jobs progress depending on their STAGE.
  // Only hydrates from claim-based jobs to avoid duplicate fetches.
  useEffect(() => {
    if (!snapshotId) {
      return;
    }

    let cancelled = false;

    const hydrate = async () => {
      const updates: { questionId: number; promise: Promise<Partial<QARecord> | null> }[] = [];

      for (const job of qaJobs) {
        if (!job.answer_id) continue;

        if (job.stage === QAJobStageEnum.PROCESSING_ANSWERS) {
          updates.push({ questionId: job.question_id, promise: fetchAnswer(job) });
        } else if (job.stage === QAJobStageEnum.SCORING_ANSWERS) {
          updates.push({ questionId: job.question_id, promise: fetchAnswer(job) });
          updates.push({ questionId: job.question_id, promise: fetchClaims(job) });
        } else if (job.stage === QAJobStageEnum.COMPLETED) {
          updates.push({ questionId: job.question_id, promise: fetchAnswer(job) });
          updates.push({ questionId: job.question_id, promise: fetchClaims(job) });
          updates.push({ questionId: job.question_id, promise: fetchScore(job) });
        }
      }

      if (updates.length === 0) return;

      const results = await Promise.all(
        updates.map(async ({ questionId, promise }) => ({
          questionId,
          partial: await promise,
        }))
      );

      if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;

      const merged: Record<number, Partial<QARecord>> = {};
      for (const { questionId, partial } of results) {
        if (!partial) continue;
        merged[questionId] = { ...merged[questionId], ...partial };
      }

      if (Object.keys(merged).length === 0) return;

      setQaMap((prev) => {
        const next = { ...prev };
        for (const [qidStr, partial] of Object.entries(merged)) {
          const qid = Number(qidStr);
          const base = next[qid] || { questionId: qid };
          next[qid] = { ...base, ...partial };
        }
        qaMapRef.current = next;
        return next;
      });
    };

    hydrate();

    return () => {
      cancelled = true;
    };
  }, [qaJobs, snapshotId, fetchAnswer, fetchClaims, fetchScore, setQaMap]);

  // Polling control functions
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current !== null) {
      window.clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  const checkData = useCallback(async () => {
    if (!snapshotId) return;
    try {
      const response = await qaJobApi.list(snapshotId);
      const allJobs = response.data.filter((job) => approvedQuestionIdSet.has(job.question_id));
      setQaJobs(allJobs);

      const allDone = allJobs.length > 0 && allJobs.every(
        (job) => job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED
      );

      if (allDone) {
        stopPolling();
      }
    } catch (err) {
      console.error("Failed to poll job status:", err);
    }
  }, [approvedQuestionIdSet, snapshotId, setQaJobs, stopPolling]);

  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current !== null) return;
    pollingIntervalRef.current = window.setInterval(checkData, 2000);
  }, [checkData]);

  // Automatically trigger default selection once answers exist but none are selected.
  useEffect(() => {
    if (!snapshotId) return;
    if (defaultSelectionAttemptedRef.current.has(snapshotId)) return;
    if (defaultSelectionInFlightRef.current.has(snapshotId)) return;

    const answers: Answer[] = Object.values(qaMap)
      .map((entry) => entry.answer)
      .filter((answer): answer is Answer => Boolean(answer));

    if (answers.length === 0) return;

    const hasSelection = answers.some((answer) => answer.is_selected_for_annotation);
    if (hasSelection) {
      defaultSelectionAttemptedRef.current.add(snapshotId);
      return;
    }

    let cancelled = false;
    defaultSelectionInFlightRef.current.add(snapshotId);

    const applyDefaultSelection = async () => {
      try {
        await answerApi.selectDefault(snapshotId);
        if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;

        const refreshed = await answerApi.list(snapshotId);
        if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;

        setQaMap((prev) => {
          const next: QAMap = { ...prev };
          refreshed.data.answers.forEach((answer) => {
            const existing = next[answer.question_id];
            next[answer.question_id] = {
              ...existing,
              questionId: answer.question_id,
              answer,
            };
          });
          qaMapRef.current = next;
          return next;
        });
        if (!cancelled) {
          defaultSelectionAttemptedRef.current.add(snapshotId);
        }
      } catch (err) {
        console.error("Failed to auto-select default answers:", err);
      } finally {
        defaultSelectionInFlightRef.current.delete(snapshotId);
      }
    };

    applyDefaultSelection();

    return () => {
      cancelled = true;
    };
  }, [snapshotId, qaMap, setQaMap]);

  // Cleanup polling on snapshot/judge change
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [snapshotId, stopPolling]);

  const fetchMissingRubricCoverage = useCallback(async () => {
    if (!snapshotId || !rubrics || rubrics.length === 0) {
      setMissingRubricCoverage(emptyMissingRubricCoverage);
      return;
    }

    const rubricSpecs = resolvedRubricSpecs;
    if (rubricSpecs.length === 0) {
      setMissingRubricCoverage(emptyMissingRubricCoverage);
      return;
    }

    const answeredQuestionIds = new Set(
      Object.values(qaMapRef.current)
        .filter((entry) => entry.answer)
        .map((entry) => entry.questionId)
    );

    const entries = await Promise.all(
      rubricSpecs.map(async (spec) => {
        try {
          const response = await questionApi.listApprovedWithoutScores(
            snapshotId,
            spec.judge_id,
            spec.rubric_id,
          );
          return {
            rubricId: spec.rubric_id,
            questionIds: response.data
              .map((question) => question.id)
              .filter((questionId) => answeredQuestionIds.has(questionId)),
          };
        } catch {
          return { rubricId: spec.rubric_id, questionIds: [] };
        }
      })
    );

    setMissingRubricCoverage(buildMissingRubricCoverage(entries, rubrics));
  }, [snapshotId, rubrics, resolvedRubricSpecs]);

  useEffect(() => {
    fetchMissingRubricCoverage().catch(() => {
      setMissingRubricCoverage(emptyMissingRubricCoverage);
    });
  }, [fetchMissingRubricCoverage, qaJobs, snapshotId, qaMap]);

  const totalJobs = qaJobs.length;
  const hasPendingRubricMetrics = hasMissingRubricCoverage(missingRubricCoverage);

  // UI chip to display progress
  const getStatusChip = () => {
    if (!snapshotId) {
      return <Chip label="Select a snapshot" size="small" />;
    }

    if (loadingInitialData) {
      return (
        <Chip
          icon={<CircularProgress size={14} />}
          label="Loading..."
          size="small"
        />
      );
    }

    if (totalJobs === 0) {
      return <Chip label="Not Started" color="default" size="small" />;
    }

    if (runningCount > 0) {
      return (
        <Chip
          icon={<CircularProgress size={14} />}
          label={`Evaluating \u2022 ${questionsFullyComplete}/${totalQuestions}`}
          color="warning"
          size="small"
        />
      );
    }

    if (hasPendingRubricMetrics) {
      return (
        <Chip
          label={`Metrics pending • ${missingRubricCoverage.pendingQuestionCount} question${missingRubricCoverage.pendingQuestionCount === 1 ? "" : "s"}`}
          color="warning"
          size="small"
        />
      );
    }

    if (questionsFullyComplete === totalQuestions && totalQuestions > 0) {
      if (questionsWithoutAnswers.length > 0) {
        return (
          <Chip
            label={`${questionsWithoutAnswers.length} new question${questionsWithoutAnswers.length === 1 ? "" : "s"} ready to evaluate`}
            color="warning"
            size="small"
          />
        );
      }
      return <Chip label="Evaluations complete — ready to annotate" color="success" size="small" />;
    }

    if (failedCount > 0 && runningCount === 0 && pausedCount === 0) {
      const failedQuestions = new Set(
        qaJobs.filter((j) => j.status === JobStatus.FAILED).map((j) => j.question_id)
      ).size;
      return (
        <Chip
          label={`${failedQuestions} of ${totalQuestions} evaluation${failedQuestions === 1 ? "" : "s"} failed`}
          color="error"
          size="small"
        />
      );
    }

    if (pausedCount > 0) {
      return (
        <Chip
          label={`Paused: ${questionsFullyComplete}/${totalQuestions}`}
          color="default"
          size="small"
        />
      );
    }

    return <Chip label="Idle" size="small" />;
  };

  const controlState: ControlState = (() => {
    if (!snapshotId) {
      return "disabled";
    }

    if (runningCount > 0) {
      return "pause";
    }

    if (pausedCount > 0) {
      return "resume";
    }

    if (hasPendingRubricMetrics) {
      return "start";
    }

    if (
      totalJobs === 0 ||
      (questionsFullyComplete === totalQuestions && totalQuestions > 0)
    ) {
      return "start";
    }

    return "start";
  })();

  const isScoringComplete = totalQuestions > 0
    && questionsFullyComplete === totalQuestions
    && questionsWithoutAnswers.length === 0
    && !hasPendingRubricMetrics;

  const controlButtonText = (() => {
    switch (controlState) {
      case "start":
        if (hasPendingRubricMetrics) {
          return "Retry Missing Metrics";
        }
        if (failedCount > 0) {
          return "Retry Failed Evaluations";
        }
        if (questionsFullyComplete > 0 && questionsWithoutAnswers.length > 0) {
          return "Evaluate New Questions";
        }
        if (isScoringComplete) {
          return "All Evaluations Complete";
        }
        return "Start Evaluations";
      case "pause":
        return "Pause Evaluation";
      case "resume":
        return "Resume Evaluation";
      default:
        return "Select a Snapshot";
    }
  })();

  // Functions to start, pause, and resume the QA jobs
  const handleStart = async () => {
    if (!snapshotId) return;

    setJobInAction(true);
    try {
      if (hasPendingRubricMetrics) {
        const retries = await Promise.all(
          Object.entries(missingRubricCoverage.missingQuestionIdsByRubric).map(async ([rubricId, questionIds]) => {
            const spec = resolvedRubricSpecs.find((entry) => entry.rubric_id === Number(rubricId));
            if (!spec || questionIds.length === 0) {
              return [];
            }
            const response = await qaJobApi.start(snapshotId, {
              question_ids: questionIds,
              rubric_specs: [spec],
            });
            return response.data;
          })
        );

        const mergedJobs = retries.flat();
        if (mergedJobs.length > 0) {
          setQaJobs((prev) => mergeJobs(prev, mergedJobs));
          startPolling();
          checkData();
        }
        return;
      }

      // Determine which questions to evaluate
      const failedJobs = qaJobs.filter((job) => job.status === JobStatus.FAILED);
      const questionIds = failedJobs.length > 0
        ? failedJobs.map((job) => job.question_id)
        : questionsWithoutAnswers;
      const jobIds = failedJobs.length > 0
        ? failedJobs.map((job) => job.id)
        : undefined;

      if (questionIds.length === 0 && !jobIds) return;

      const response = await qaJobApi.start(snapshotId, {
        question_ids: questionIds,
        job_ids: jobIds,
      });

      if (failedJobs.length > 0) {
        const retriedIds = new Set(failedJobs.map((job) => job.id));
        const optimistic = response.data.map((job) =>
          retriedIds.has(job.id) ? { ...job, status: JobStatus.RUNNING } : job
        );
        setQaJobs((prev) => mergeJobs(prev, optimistic));
      } else {
        setQaJobs((prev) => mergeJobs(prev, response.data));
      }
      startPolling();
      checkData();
    } catch (err) {
      console.error("Failed to start QA jobs:", err);
      notifyError(getApiErrorMessage(err, "Failed to start QA jobs."));
    } finally {
      setJobInAction(false);
    }
  };

  const handlePause = async () => {
    const runningJobs = qaJobs.filter((job) => job.status === JobStatus.RUNNING);
    if (runningJobs.length === 0) return;
    setJobInAction(true);
    try {
      const response = await qaJobApi.pause(runningJobs.map((job) => job.id));
      setQaJobs((prev) => mergeJobs(prev, response.data));
      await checkData();
      stopPolling();
    } catch (err) {
      console.error("Failed to pause QA jobs:", err);
      notifyError(getApiErrorMessage(err, "Failed to pause QA jobs."));
    } finally {
      setJobInAction(false);
    }
  };

  const handleResume = async () => {
    if (!snapshotId) return;
    const pausedJobs = qaJobs.filter((job) => job.status === JobStatus.PAUSED);
    if (pausedJobs.length === 0) return;

    setJobInAction(true);
    try {
      const response = await qaJobApi.start(snapshotId, {
        question_ids: pausedJobs.map((job) => job.question_id),
        job_ids: pausedJobs.map((job) => job.id),
      });
      const resumedIds = new Set(pausedJobs.map((job) => job.id));
      const optimistic = response.data.map((job) =>
        resumedIds.has(job.id) ? { ...job, status: JobStatus.RUNNING } : job
      );
      setQaJobs((prev) => mergeJobs(prev, optimistic));
      startPolling();
      checkData();
    } catch (err) {
      console.error("Failed to resume QA jobs:", err);
      notifyError(getApiErrorMessage(err, "Failed to resume QA jobs."));
    } finally {
      setJobInAction(false);
    }
  };

  const handleControlClick = () => {
    if (controlState === "start") {
      handleStart();
    } else if (controlState === "pause") {
      handlePause();
    } else if (controlState === "resume") {
      handleResume();
    }
  };

  return (
    <Box sx={{ mb: 2 }}>
      <Stack direction="row" spacing={2} alignItems="center">
        <Button
          variant="contained"
          color="primary"
          onClick={handleControlClick}
          disabled={
            controlState === "disabled" ||
            jobInAction ||
            loadingInitialData ||
            isScoringComplete
          }
          startIcon={
            jobInAction ? (
              <CircularProgress size={16} />
            ) : controlState === "pause" ? (
              <IconPlayerPause {...actionIconProps} />
            ) : (
              <IconPlayerPlay {...actionIconProps} />
            )
          }
        >
          {controlButtonText}
        </Button>

        {getStatusChip()}
      </Stack>
    </Box>
  );
}
