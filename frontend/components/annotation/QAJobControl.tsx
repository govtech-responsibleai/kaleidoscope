"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
} from "@mui/material";
import {
  PlayArrow as PlayArrowIcon,
  Pause as PauseIcon,
} from "@mui/icons-material";
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
import { answerApi, getApiErrorMessage, judgeApi, qaJobApi, questionApi } from "@/lib/api";

interface QAJobControlProps {
  targetId: number;
  snapshotId: number | null;
  baselineJudgeId: number | null;
  approvedQuestionIds: number[];
  qaJobs: QAJob[];
  setQaJobs: React.Dispatch<React.SetStateAction<QAJob[]>>;
  qaMap: QAMap;
  setQaMap: React.Dispatch<React.SetStateAction<QAMap>>;
  rubrics?: TargetRubricResponse[];
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
  baselineJudgeId,
  approvedQuestionIds,
  qaJobs,
  setQaJobs,
  qaMap,
  setQaMap,
  rubrics,
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

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const notifyError = useCallback((message: string) => {
    onErrorRef.current?.(message);
  }, []);

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
      const judgeId = job.judge_id ?? baselineJudgeId;
      if (!job.answer_id || !judgeId) return null;
      const entry = qaMapRef.current[job.question_id];
      if (entry?.claims && entry.claims.length > 0) {
        return null;
      }
      try {
        const response = await answerApi.getClaims(job.answer_id, judgeId);
        const claims = response.data.claims.map(({ score, ...claim }) => claim);
        const claimScores = response.data.claims
          .map((item) => item.score)
          .filter((score): score is NonNullable<typeof score> => Boolean(score));
        return { claims, claimScores };
      } catch (err) {
        console.error("Failed to fetch claims:", err);
        notifyError("Unable to load claim data.");
        return null;
      }
    },
    [baselineJudgeId, notifyError]
  );

  const fetchScore = useCallback(
    async (job: QAJob): Promise<Partial<QARecord> | null> => {
      const judgeId = job.judge_id ?? baselineJudgeId;
      if (!job.answer_id || !judgeId) return null;
      const entry = qaMapRef.current[job.question_id];
      if (entry?.answerScore) {
        return null;
      }
      try {
        const response = await answerApi.getScores(job.answer_id, judgeId);
        return { answerScore: response.data, claimScores: response.data.claim_scores };
      } catch (err) {
        console.error("Failed to fetch score:", err);
        notifyError("Unable to load judge scores.");
        return null;
      }
    },
    [baselineJudgeId, notifyError]
  );

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
  }, [snapshotId, baselineJudgeId, approvedQuestionIdSet, setQaJobs, setQaMap, notifyError]);

  // Fetch questions without answers when snapshot or judge changes
  useEffect(() => {
    if (!snapshotId || !baselineJudgeId) {
      setQuestionsWithoutAnswers([]);
      return;
    }

    let cancelled = false;

    const fetchQuestionsWithoutAnswers = async () => {
      try {
        const response = await questionApi.listApprovedWithoutAnswers(snapshotId, baselineJudgeId);
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
  }, [snapshotId, baselineJudgeId, qaJobs]);

  // Update QA data as jobs progress depending on their STAGE.
  // Only hydrates from accuracy jobs (rubric_id === null) to avoid duplicate fetches.
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

  const checkData = async () => {
    if (!snapshotId || !baselineJudgeId) return;
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
  };

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
  }, [snapshotId, baselineJudgeId, stopPolling]);

  // Resolve rubric specs: for each non-accuracy rubric, fetch its specialist judge
  const resolveRubricSpecs = useCallback(async (): Promise<RubricSpec[]> => {
    if (!rubrics) return [];
    const nonAccuracyRubrics = rubrics.filter((r) => r.category !== "accuracy");
    if (nonAccuracyRubrics.length === 0) return [];

    const specs: RubricSpec[] = [];
    for (const rubric of nonAccuracyRubrics) {
      try {
        const resp = await judgeApi.getByCategory(rubric.category, targetId);
        const judges = resp.data;
        if (judges.length > 0) {
          specs.push({ rubric_id: rubric.id, judge_id: judges[0].id });
        }
      } catch (err) {
        console.error(`Failed to fetch judges for rubric category ${rubric.category}:`, err);
      }
    }
    return specs;
  }, [rubrics, targetId]);

  const totalJobs = qaJobs.length;

  // UI chip to display progress
  const getStatusChip = () => {
    if (!snapshotId || !baselineJudgeId) {
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
    if (!snapshotId || !baselineJudgeId) {
      return "disabled";
    }

    if (
      totalJobs === 0 ||
      (questionsFullyComplete === totalQuestions && totalQuestions > 0)
    ) {
      return "start";
    }

    if (runningCount > 0) {
      return "pause";
    }

    if (pausedCount > 0) {
      return "resume";
    }

    return "start";
  })();

  const isScoringComplete = totalQuestions > 0
    && questionsFullyComplete === totalQuestions
    && questionsWithoutAnswers.length === 0;

  const controlButtonText = (() => {
    switch (controlState) {
      case "start":
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
    if (!snapshotId || !baselineJudgeId) return;

    setJobInAction(true);
    try {
      const rubricSpecs = await resolveRubricSpecs();

      // Determine which questions to evaluate
      const failedJobs = qaJobs.filter((job) => job.status === JobStatus.FAILED);
      const questionIds = failedJobs.length > 0
        ? failedJobs.map((job) => job.question_id)
        : questionsWithoutAnswers;
      const jobIds = failedJobs.length > 0
        ? failedJobs.map((job) => job.id)
        : undefined;

      if (questionIds.length === 0 && !jobIds) return;

      const response = await qaJobApi.startAll(snapshotId, {
        judge_id: baselineJudgeId,
        question_ids: questionIds,
        rubric_specs: rubricSpecs.length > 0 ? rubricSpecs : undefined,
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
    if (!snapshotId || !baselineJudgeId) return;
    const pausedJobs = qaJobs.filter((job) => job.status === JobStatus.PAUSED);
    if (pausedJobs.length === 0) return;

    setJobInAction(true);
    try {
      const response = await qaJobApi.startAll(snapshotId, {
        judge_id: baselineJudgeId,
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
              <PauseIcon />
            ) : (
              <PlayArrowIcon />
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
