"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Alert,
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
} from "@/lib/types";
import { answerApi, judgeApi, qaJobApi, questionApi, rubricQAJobApi } from "@/lib/api";

interface QAJobControlProps {
  snapshotId: number | null;
  baselineJudgeId: number | null;
  qaJobs: QAJob[];
  setQaJobs: React.Dispatch<React.SetStateAction<QAJob[]>>;
  qaMap: QAMap;
  setQaMap: React.Dispatch<React.SetStateAction<QAMap>>;
  rubrics?: TargetRubricResponse[];
  onError?: (message: string) => void;
  onRubricJobsCompleteChange?: (complete: boolean) => void;
  onRubricPendingQuestionsChange?: (pendingQuestionIds: Set<number>) => void;
}

type ControlState = "start" | "pause" | "resume" | "disabled";

const getStageLabel = (stage: QAJobStageEnum): string => {
  switch (stage) {
    case QAJobStageEnum.STARTING:
      return "Starting";
    case QAJobStageEnum.GENERATING_ANSWERS:
      return "Generating";
    case QAJobStageEnum.PROCESSING_ANSWERS:
      return "Processing";
    case QAJobStageEnum.SCORING_ANSWERS:
      return "Scoring";
    case QAJobStageEnum.COMPLETED:
      return "Completed";
    default:
      return "Unknown";
  }
};

export default function QAJobControl({
  snapshotId,
  baselineJudgeId,
  qaJobs,
  setQaJobs,
  qaMap,
  setQaMap,
  rubrics,
  onError,
  onRubricJobsCompleteChange,
  onRubricPendingQuestionsChange,
}: QAJobControlProps) {
  const [jobInAction, setJobInAction] = useState(false); // To prevent double submits of a job request
  const [loadingInitialData, setLoadingInitialData] = useState(true); // Wait for the first set of data to be ready
  const [rubricJobsFired, setRubricJobsFired] = useState(false); // Track if rubric jobs have been fired this session
  const [rubricJobsComplete, setRubricJobsComplete] = useState(false); // Track if all rubric jobs have completed
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

  // Propagate rubricJobsComplete to parent
  useEffect(() => {
    onRubricJobsCompleteChange?.(rubricJobsComplete);
  }, [rubricJobsComplete, onRubricJobsCompleteChange]);

  const onRubricPendingQuestionsChangeRef = useRef(onRubricPendingQuestionsChange);
  useEffect(() => {
    onRubricPendingQuestionsChangeRef.current = onRubricPendingQuestionsChange;
  }, [onRubricPendingQuestionsChange]);

  /** Compute which question IDs still have pending rubric jobs and notify parent */
  const updateRubricPendingQuestions = useCallback((allJobs: QAJob[]) => {
    const hasNonAccuracyRubrics = rubrics?.some((r) => r.category !== "accuracy") ?? false;
    if (!hasNonAccuracyRubrics) {
      onRubricPendingQuestionsChangeRef.current?.(new Set());
      return;
    }
    const rubricJobs = allJobs.filter((j) => j.rubric_id !== null);
    // Group rubric jobs by question_id
    const byQuestion = new Map<number, QAJob[]>();
    for (const job of rubricJobs) {
      const existing = byQuestion.get(job.question_id) ?? [];
      existing.push(job);
      byQuestion.set(job.question_id, existing);
    }
    const pending = new Set<number>();
    for (const [questionId, jobs] of byQuestion) {
      const allDone = jobs.every(
        (j) => j.status === JobStatus.COMPLETED || j.status === JobStatus.FAILED
      );
      if (!allDone) pending.add(questionId);
    }
    // Also include questions that have baseline jobs completed but no rubric jobs yet
    // (rubric jobs haven't been created for them yet)
    if (rubricJobs.length === 0) {
      // No rubric jobs at all yet — all questions with baseline jobs are pending
      const baselineCompleted = allJobs
        .filter((j) => j.rubric_id === null && (j.status === JobStatus.COMPLETED || j.status === JobStatus.FAILED))
        .map((j) => j.question_id);
      for (const qid of baselineCompleted) pending.add(qid);
    }
    onRubricPendingQuestionsChangeRef.current?.(pending);
  }, [rubrics]);

  // refs don't trigger re-renders
  useEffect(() => {
    qaMapRef.current = qaMap;
  }, [qaMap]);

  useEffect(() => {
    activeSnapshotIdRef.current = snapshotId;
  }, [snapshotId]);

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
  const completedCount = statusGroups[JobStatus.COMPLETED] ?? 0;
  const failedCount = statusGroups[JobStatus.FAILED] ?? 0;
  const pausedCount = statusGroups[JobStatus.PAUSED] ?? 0;

  // Track questions without answers (fetched from backend)
  const [questionsWithoutAnswers, setQuestionsWithoutAnswers] = useState<number[]>([]);

  // Update counts of the STAGEs each QAJob is in
  const stageGroups = useMemo(() => {
    const groups: Record<QAJobStageEnum, number> = {
      [QAJobStageEnum.STARTING]: 0,
      [QAJobStageEnum.GENERATING_ANSWERS]: 0,
      [QAJobStageEnum.PROCESSING_ANSWERS]: 0,
      [QAJobStageEnum.SCORING_ANSWERS]: 0,
      [QAJobStageEnum.COMPLETED]: 0,
    };

    qaJobs.forEach((job) => {
      if (job.status === JobStatus.RUNNING) {
        groups[job.stage]++;
      }
    });

    return groups;
  }, [qaJobs]);

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
      if (!job.answer_id || !baselineJudgeId) return null;
      const entry = qaMapRef.current[job.question_id];
      if (entry?.claims && entry.claims.length > 0) {
        return null;
      }
      try {
        const response = await answerApi.getClaims(job.answer_id, baselineJudgeId);
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
      if (!job.answer_id || !baselineJudgeId) return null;
      const entry = qaMapRef.current[job.question_id];
      if (entry?.answerScore) {
        return null;
      }
      try {
        const response = await answerApi.getScores(job.answer_id, baselineJudgeId);
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
      console.log("Loading initial data...");
      try {
        const [jobsResponse, answersResponse] = await Promise.all([
          qaJobApi.list(snapshotId),
          answerApi.list(snapshotId),
        ]);

        if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;

        // Get all jobs for this snapshot and (baseline) judge
        const allJobs = jobsResponse.data;
        const baselineJobs = baselineJudgeId
          ? allJobs.filter((job) => job.judge_id === baselineJudgeId)
          : allJobs;
        setQaJobs(baselineJobs);

        // Check if rubric jobs are already complete (returning to a finished snapshot)
        const baselineDone = baselineJobs.length > 0 &&
          baselineJobs.every((j) => j.status === JobStatus.COMPLETED || j.status === JobStatus.FAILED);
        if (baselineDone) {
          const hasNonAccuracyRubrics = rubrics?.some((r) => r.category !== "accuracy") ?? false;
          const rubricJobs = allJobs.filter((j) => j.rubric_id !== null);
          const rubricsDone = !hasNonAccuracyRubrics ||
            (rubricJobs.length > 0 &&
              rubricJobs.every((j) => j.status === JobStatus.COMPLETED || j.status === JobStatus.FAILED));
          setRubricJobsComplete(rubricsDone);
          updateRubricPendingQuestions(allJobs);
        }

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
        console.log("Loaded initial data...");
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
  }, [snapshotId, baselineJudgeId, setQaJobs, setQaMap, notifyError]);

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
          if (questionIds.length > 0) {
            console.log(
              `QAJobControl: Detected ${questionIds.length} questions without answers:`,
              questionIds
            );
          } else {
            console.log("QAJobControl: No new questions to evaluate.");
          }
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
  // Fetches all missing data in parallel and applies a single batched setQaMap.
  useEffect(() => {
    if (!snapshotId) {
      return;
    }

    let cancelled = false;

    const hydrate = async () => {
      // Collect all fetch promises keyed by questionId
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

      // Resolve all fetches in parallel
      const results = await Promise.all(
        updates.map(async ({ questionId, promise }) => ({
          questionId,
          partial: await promise,
        }))
      );

      if (cancelled || snapshotId !== activeSnapshotIdRef.current) return;

      // Merge all non-null results into a single qaMap update
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
      console.log("Current job list...", response);
      const allJobs = response.data;

      const baselineJobs = allJobs.filter(
        (job) => job.judge_id === baselineJudgeId
      );
      setQaJobs(baselineJobs);

      const baselineDone = baselineJobs.every(
        (job) => job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED
      );

      if (baselineDone && baselineJobs.length > 0) {
        // Auto-fire rubric jobs once baseline completes
        if (!rubricJobsFired) {
          setRubricJobsFired(true);
          const answeredIds = Object.values(qaMapRef.current)
            .filter((e) => e.answer)
            .map((e) => e.questionId);
          if (answeredIds.length > 0) {
            console.log("Baseline complete — auto-firing rubric jobs for", answeredIds.length, "answered questions");
            fireRubricJobs(answeredIds);
          }
        }

        // Check rubric job completion
        const hasNonAccuracyRubrics = rubrics?.some((r) => r.category !== "accuracy") ?? false;
        const rubricJobs = allJobs.filter((j) => j.rubric_id !== null);
        const rubricsDone = !hasNonAccuracyRubrics ||
          (rubricJobs.length > 0 &&
            rubricJobs.every((j) => j.status === JobStatus.COMPLETED || j.status === JobStatus.FAILED));
        setRubricJobsComplete(rubricsDone);
        updateRubricPendingQuestions(allJobs);

        // Only stop polling when baseline AND rubric jobs are all done
        if (rubricsDone) {
          stopPolling();
        }
      }
    } catch (err) {
      console.error("Failed to poll job status:", err);
    }
  };

  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current !== null) return; // Already polling

    pollingIntervalRef.current = window.setInterval(checkData, 2000);
    console.log("Started polling...");
  }, [snapshotId, baselineJudgeId, stopPolling]);

  // Automatically trigger default selection once answers exist but none are selected.
  useEffect(() => {
    if (!snapshotId) return;
    if (defaultSelectionAttemptedRef.current.has(snapshotId)) return;
    if (defaultSelectionInFlightRef.current.has(snapshotId)) return;

    const answers: Answer[] = Object.values(qaMap)
      .map((entry) => entry.answer)
      .filter((answer): answer is Answer => Boolean(answer));

    if (answers.length === 0) return;

    // Check if any answer is already selected
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

  // Reset rubric jobs state and cleanup polling on snapshot/judge change
  useEffect(() => {
    setRubricJobsFired(false);
    setRubricJobsComplete(false);
    return () => {
      stopPolling();
    };
  }, [snapshotId, baselineJudgeId, stopPolling]);

  const totalJobs = qaJobs.length;

  // UI chips to display the STATUS and STAGE of the QA job.
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
      const dominantStage = Object.entries(stageGroups).reduce(
        (max, [stage, count]) => {
          return count > max.count
            ? { stage: stage as QAJobStageEnum, count }
            : max;
        },
        { stage: QAJobStageEnum.STARTING, count: 0 }
      ).stage;

      return (
        <Chip
          icon={<CircularProgress size={14} />}
          label={`${getStageLabel(dominantStage)} • ${completedCount}/${totalJobs}`}
          color="warning"
          size="small"
        />
      );
    }

    if (completedCount === totalJobs) {
      if (questionsWithoutAnswers.length > 0) {
        return (
          <Chip
            label={`Pending: (${questionsWithoutAnswers.length}) new questions found.`}
            color="warning"
            size="small"
          />
        );
      }
      const hasNonAccuracyRubrics = rubrics?.some((r) => r.category !== "accuracy") ?? false;
      if (hasNonAccuracyRubrics && !rubricJobsComplete) {
        return (
          <Chip
            icon={<CircularProgress size={14} />}
            label="Scoring custom metrics..."
            color="warning"
            size="small"
          />
        );
      }
      return <Chip label="Completed" color="success" size="small" />;
    }

    if (failedCount > 0) {
      return (
        <Chip
          label={`Failed: ${failedCount}/${totalJobs}`}
          color="error"
          size="small"
        />
      );
    }

    if (pausedCount > 0) {
      return (
        <Chip
          label={`Paused: ${completedCount}/${totalJobs}`}
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
      completedCount === totalJobs ||
      failedCount === totalJobs
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

  const controlButtonText = (() => {
    switch (controlState) {
      case "start":
        // If there are already completed jobs but new questions found, show different text
        if (completedCount > 0 && questionsWithoutAnswers.length > 0) {
          return "Evaluate New Questions";
        }
        return "Evaluate All Questions";
      case "pause":
        return "Pause Evaluation";
      case "resume":
        return "Resume Evaluation";
      default:
        return "Select a Snapshot";
    }
  })();

  const isScoringComplete = totalJobs > 0 && completedCount === totalJobs && questionsWithoutAnswers.length === 0;

  // Fire rubric jobs for all answered questions (fire-and-forget).
  // Fetches judges on-demand so we don't depend on pre-loaded state.
  const fireRubricJobs = useCallback(async (allQuestionIds: number[]) => {
    if (!snapshotId || !rubrics || allQuestionIds.length === 0) return;
    const nonAccuracyRubrics = rubrics.filter((r) => r.category !== "accuracy");
    if (nonAccuracyRubrics.length === 0) return;

    for (const rubric of nonAccuracyRubrics) {
      try {
        const resp = await judgeApi.getByCategory(rubric.category);
        const judges = resp.data;
        // Only fire the first category-specific specialist judge (recommended), not the common judges.
        // Users can manually run additional judges from the scoring tab if desired.
        const specialistJudges = judges.filter((j) => j.category !== "common").slice(0, 1);
        await Promise.allSettled(
          specialistJudges.map((judge) =>
            rubricQAJobApi.start(snapshotId, {
              judge_id: judge.id,
              question_ids: allQuestionIds,
              rubric_id: rubric.id,
            }).catch((err) => {
              console.error(`Failed to start rubric job for rubric ${rubric.id}, judge ${judge.id}:`, err);
            })
          )
        );
      } catch (err) {
        console.error(`Failed to fetch judges for rubric category ${rubric.category}:`, err);
      }
    }
  }, [snapshotId, rubrics]);

  // Functions to start, pause, and resume the QA jobs
  const handleStart = async () => {
    if (!snapshotId || !baselineJudgeId) return;
    console.log("calling handleStart");

    // All question IDs to potentially rubric-score (answered + new)
    const answeredQuestionIds = Object.values(qaMap)
      .filter((entry) => entry.answer)
      .map((entry) => entry.questionId);

    // Check for failed jobs that need restarting
    const failedJobs = qaJobs.filter((job) => job.status === JobStatus.FAILED);

    // If there are failed jobs, restart them; otherwise start new jobs for questions without answers
    if (failedJobs.length > 0) {
      setJobInAction(true);
      try {
        const response = await qaJobApi.start(snapshotId, {
          judge_id: baselineJudgeId,
          question_ids: failedJobs.map((job) => job.question_id),
          job_ids: failedJobs.map((job) => job.id),
        });
        setQaJobs(response.data);
        startPolling();
        // Fire rubric jobs only for already-answered questions (failed baseline jobs don't have answers yet)
        fireRubricJobs(answeredQuestionIds);
      } catch (err) {
        console.error("Failed to restart failed QA jobs:", err);
        notifyError("Failed to restart failed QA jobs.");
      } finally {
        setJobInAction(false);
      }
    } else if (questionsWithoutAnswers.length > 0) {
      setJobInAction(true);
      try {
        const response = await qaJobApi.start(snapshotId, {
          judge_id: baselineJudgeId,
          question_ids: questionsWithoutAnswers,
        });
        setQaJobs(response.data);
        startPolling();
        // Fire rubric jobs only for already-answered questions (new questions don't have answers yet)
        fireRubricJobs(answeredQuestionIds);
      } catch (err) {
        console.error("Failed to start QA jobs:", err);
        notifyError("Failed to start QA jobs.");
      } finally {
        setJobInAction(false);
      }
    } else {
      // No new baseline questions but user may want to run rubric jobs for already-answered questions
      fireRubricJobs(answeredQuestionIds);
    }
  };

  const handlePause = async () => {
    if (qaJobs.length === 0) return;
    console.log("calling handlePause");
    setJobInAction(true);
    try {
      const response = await qaJobApi.pause(qaJobs.map((job) => job.id));
      setQaJobs(response.data);
      stopPolling();
    } catch (err) {
      console.error("Failed to pause QA jobs:", err);
      notifyError("Failed to pause QA jobs.");
    } finally {
      setJobInAction(false);
    }
  };

  const handleResume = async () => {
    if (!snapshotId || !baselineJudgeId) return;
    const pausedJobs = qaJobs.filter((job) => job.status === JobStatus.PAUSED);
    if (pausedJobs.length === 0) return;

    console.log("calling handleResume");
    setJobInAction(true);
    try {
      const response = await qaJobApi.start(snapshotId, {
        judge_id: baselineJudgeId,
        question_ids: pausedJobs.map((job) => job.question_id),
        job_ids: pausedJobs.map((job) => job.id),
      });
      setQaJobs(response.data);
      startPolling();
    } catch (err) {
      console.error("Failed to resume QA jobs:", err);
      notifyError("Failed to resume QA jobs.");
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
          variant="outlined"
          onClick={handleControlClick}
          disabled={
            controlState === "disabled" ||
            jobInAction ||
            loadingInitialData
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
