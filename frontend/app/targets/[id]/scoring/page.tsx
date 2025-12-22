"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Alert,
  Box,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Add as AddIcon,
  ArrowBackIosNew as ArrowBackIosNewIcon,
  ArrowForwardIos as ArrowForwardIosIcon,
} from "@mui/icons-material";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import JudgeCards from "@/components/scoring/JudgeCards";
import CreateJudgeDialog from "@/components/scoring/CreateJudgeDialog";
import ResultsTable from "@/components/scoring/ResultsTable";
import {
  Snapshot,
  JudgeConfig,
  ResultRow,
  JobStatus,
  AnnotationCompletionStatus,
  QAJob
} from "@/lib/types";
import {
  snapshotApi,
  judgeApi,
  qaJobApi,
  metricsApi,
  annotationApi,
  questionApi,
} from "@/lib/api";

export default function ScoringPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const targetId = Number(params.id);

  // Snapshot state - initialize from URL if available
  const snapshotIdFromUrl = searchParams.get("snapshot");
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(
    snapshotIdFromUrl ? Number(snapshotIdFromUrl) : null
  );
  const [snapshotsLoading, setSnapshotsLoading] = useState(true);

  // Judges state
  const [judges, setJudges] = useState<JudgeConfig[]>([]);
  const [judgesLoading, setJudgesLoading] = useState(true);
  const [judgeJobs, setJudgeJobs] = useState<Record<number, QAJob[]>>({});

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit" | "duplicate">("create");
  const [dialogJudge, setDialogJudge] = useState<JudgeConfig | null>(null);

  // Results state
  const [results, setResults] = useState<ResultRow[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);

  // Annotation completion state
  const [annotationStatus, setAnnotationStatus] = useState<AnnotationCompletionStatus | null>(null);
  const [checkingAnnotations, setCheckingAnnotations] = useState(true);

  // Questions status state
  const [questionsWithoutAnswers, setQuestionsWithoutAnswers] = useState<number>(0);
  const [questionsWithoutScores, setQuestionsWithoutScores] = useState<Record<number, number>>({});

  // UI state
  const [error, setError] = useState<string | null>(null);
  const judgeCardsRef = useRef<HTMLDivElement | null>(null);

  // Polling refs
  const pollingRefs = useRef<Record<number, number>>({});

  // Fetch snapshots
  const fetchSnapshots = useCallback(async () => {
    setSnapshotsLoading(true);
    try {
      const response = await snapshotApi.list(targetId);
      setSnapshots(response.data);
      if (!selectedSnapshotId && response.data.length > 0) {
        // Select the most recent snapshot (sort by created_at descending)
        const mostRecent = [...response.data].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )[0];
        setSelectedSnapshotId(mostRecent.id);
        // Update URL with default selection
        const newSearchParams = new URLSearchParams(searchParams.toString());
        newSearchParams.set("snapshot", mostRecent.id.toString());
        router.push(`/targets/${targetId}/scoring?${newSearchParams.toString()}`, { scroll: false });
      }
    } catch (error) {
      console.error("Failed to fetch snapshots:", error);
      setError("Failed to load snapshots.");
    } finally {
      setSnapshotsLoading(false);
    }
  }, [targetId, selectedSnapshotId, searchParams, router]);

  // Fetch judges
  const fetchJudges = useCallback(async () => {
    setJudgesLoading(true);
    try {
      const response = await judgeApi.list(targetId);
      // Sort: baseline first, then others
      const sorted = response.data.sort((a, b) =>
        Number(b.is_baseline) - Number(a.is_baseline)
      );
      setJudges(sorted);
    } catch (error) {
      console.error("Failed to fetch judges:", error);
      setError("Failed to load judges.");
    } finally {
      setJudgesLoading(false);
    }
  }, [targetId]);

  // Check annotation completion
  const checkAnnotationCompletion = useCallback(async (snapshotId: number) => {
    setCheckingAnnotations(true);
    try {
      const response = await annotationApi.getCompletionStatus(snapshotId);
      setAnnotationStatus(response.data);
    } catch (error) {
      console.error("Failed to check annotation status:", error);
      setAnnotationStatus(null);
    } finally {
      setCheckingAnnotations(false);
    }
  }, []);

  // Fetch results
  const fetchResults = useCallback(async (snapshotId: number) => {
    setResultsLoading(true);
    try {
      const response = await metricsApi.getResults(snapshotId);
      setResults(response.data.results ?? []);
      // console.log("RESULTS", response.data.results);
    } catch (error) {
      console.error("Failed to fetch results:", error);
      setError("Failed to load results.");
    } finally {
      setResultsLoading(false);
    }
  }, []);

  // Fetch questions without answers (using baseline judge)
  const fetchQuestionsWithoutAnswers = useCallback(async (snapshotId: number) => {
    const baselineJudge = judges.find((j) => j.is_baseline);
    if (!baselineJudge) {
      setQuestionsWithoutAnswers(0);
      return;
    }

    try {
      const response = await questionApi.listApprovedWithoutAnswers(snapshotId, baselineJudge.id);
      setQuestionsWithoutAnswers(response.data.length);
    } catch (error) {
      console.error("Failed to fetch questions without answers:", error);
      setQuestionsWithoutAnswers(0);
    }
  }, [judges]);

  // Fetch questions without scores for all judges
  const fetchQuestionsWithoutScores = useCallback(async (snapshotId: number) => {
    try {
      const counts: Record<number, number> = {};

      for (const judge of judges) {
        const response = await questionApi.listApprovedWithoutScores(snapshotId, judge.id);
        counts[judge.id] = response.data.length;
      }
      setQuestionsWithoutScores(counts);
    } catch (error) {
      console.error("Failed to fetch questions without scores:", error);
      setQuestionsWithoutScores({});
    }
  }, [judges]);

  // Check judge job statuses
  const checkJudgeJobStatuses = useCallback(
    async (snapshotId: number) => {
      try {
        const response = await qaJobApi.list(snapshotId);
        const jobs = response.data;

        // Group jobs by judge_id
        const jobsByJudge: Record<number, QAJob[]> = {};
        jobs.forEach((job) => {
          if (!jobsByJudge[job.judge_id]) {
            jobsByJudge[job.judge_id] = [];
          }
          jobsByJudge[job.judge_id].push(job);
        });

        setJudgeJobs(jobsByJudge);
        return jobsByJudge;
      } catch (error) {
        console.error("Failed to check judge job statuses:", error);
        return null;
      }
    },
    []
  );

  const startJudgePolling = useCallback(
    (judgeId: number, snapshotId: number) => {
      if (!snapshotId) {
        return;
      }

      const existingInterval = pollingRefs.current[judgeId];
      if (existingInterval) {
        window.clearInterval(existingInterval);
        delete pollingRefs.current[judgeId];
      }

      const runPoll = async () => {
        const jobsByJudge = await checkJudgeJobStatuses(snapshotId);
        if (!jobsByJudge) {
          return;
        }

        const jobsForJudge = jobsByJudge[judgeId] || [];
        const allCompleted =
          jobsForJudge.length > 0 &&
          jobsForJudge.every((job) => job.status === JobStatus.COMPLETED);

        if (allCompleted) {
          const activeInterval = pollingRefs.current[judgeId];
          if (activeInterval) {
            window.clearInterval(activeInterval);
            delete pollingRefs.current[judgeId];
          }
          await fetchResults(snapshotId);
          await fetchQuestionsWithoutScores(snapshotId);
        }
      };

      runPoll();

      const intervalId = window.setInterval(runPoll, 5000);
      pollingRefs.current[judgeId] = intervalId;
    },
    [checkJudgeJobStatuses, fetchResults, fetchQuestionsWithoutScores]
  );

  // Initial data fetch
  useEffect(() => {
    fetchSnapshots();
    fetchJudges();
  }, [fetchSnapshots, fetchJudges]);

  // Fetch data when snapshot changes
  useEffect(() => {
    setAnnotationStatus(null);
    setResults([]);
    setJudgeJobs({});
    setQuestionsWithoutAnswers(0);
    setQuestionsWithoutScores({});

    if (selectedSnapshotId) {
      checkAnnotationCompletion(selectedSnapshotId);
      checkJudgeJobStatuses(selectedSnapshotId);
      fetchQuestionsWithoutAnswers(selectedSnapshotId);
      fetchQuestionsWithoutScores(selectedSnapshotId);
    }
  }, [selectedSnapshotId, checkAnnotationCompletion, checkJudgeJobStatuses, fetchQuestionsWithoutAnswers, fetchQuestionsWithoutScores]);

  // Fetch results when annotations are complete
  useEffect(() => {
    if (selectedSnapshotId && annotationStatus?.is_complete) {
      fetchResults(selectedSnapshotId);
    }
  }, [selectedSnapshotId, annotationStatus, fetchResults]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      Object.values(pollingRefs.current).forEach((intervalId) =>
        window.clearInterval(intervalId)
      );
    };
  }, []);

  // Handle snapshot selection
  const handleSnapshotSelect = (snapshotId: number) => {
    setSelectedSnapshotId(snapshotId);
    // Update URL to persist selection across tab switches
    const newSearchParams = new URLSearchParams(searchParams.toString());
    newSearchParams.set("snapshot", snapshotId.toString());
    router.push(`/targets/${targetId}/scoring?${newSearchParams.toString()}`, { scroll: false });
  };

  const handleScrollJudgeCards = (direction: "left" | "right") => {
    const container = judgeCardsRef.current;
    if (!container) {
      return;
    }

    const scrollAmount = container.clientWidth * 0.8;
    container.scrollBy({
      left: direction === "left" ? -scrollAmount : scrollAmount,
      behavior: "smooth",
    });
  };

  // Handle run judge
  const handleRunJudge = async (judgeId: number) => {
    if (!selectedSnapshotId) {
      setError("Select a snapshot to run judges.");
      return;
    }

    try {
      // Get only questions without scores for this judge
      const questionsResponse = await questionApi.listApprovedWithoutScores(selectedSnapshotId, judgeId);
      const questionIdsToScore = questionsResponse.data.map((q) => q.id);

      // Start judge job
      if (questionIdsToScore.length === 0) {
        setError("All questions already scored for this judge.");
        return;
      }

      const response = await qaJobApi.start(selectedSnapshotId, {
        judge_id: judgeId,
        question_ids: questionIdsToScore,
        is_scoring: true, // Because this is scoring page
      });

      // Store the returned jobs
      const jobs = response.data;
      setJudgeJobs((prev) => ({
        ...prev,
        [judgeId]: jobs,
      }));

      // Refresh current job statuses and scoring results once run kicks off
      await checkJudgeJobStatuses(selectedSnapshotId);
      await fetchResults(selectedSnapshotId);
      await fetchQuestionsWithoutScores(selectedSnapshotId);
      startJudgePolling(judgeId, selectedSnapshotId);

    } catch (error) {
      console.error("Failed to run judge:", error);
      setError("Unable to start judge run.");
    }
  };

  // Handle judge dialog
  const handleOpenDialog = (
    mode: "create" | "edit" | "duplicate",
    judge?: JudgeConfig
  ) => {
    setDialogMode(mode);
    setDialogJudge(judge || null);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setDialogJudge(null);
  };

  const handleDialogSuccess = async () => {
    await fetchJudges();
    handleCloseDialog();
  };

  // Handle delete judge
  const handleDeleteJudge = async (judge: JudgeConfig) => {
    if (!judge.is_editable || judge.is_baseline) {
      setError("Cannot delete this judge.");
      return;
    }

    if (!confirm(`Are you sure you want to delete judge "${judge.name}"?`)) {
      return;
    }

    try {
      await judgeApi.delete(judge.id);
      await fetchJudges();
    } catch (error) {
      console.error("Failed to delete judge:", error);
      setError("Failed to delete judge.");
    }
  };

  if (snapshotsLoading || judgesLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <SnapshotHeader
        targetId={targetId}
        snapshots={snapshots}
        selectedSnapshotId={selectedSnapshotId}
        onSelectSnapshot={handleSnapshotSelect}
        onSnapshotCreated={fetchSnapshots}
      />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {!selectedSnapshotId ? (
        <Box sx={{ py: 6, textAlign: "center" }}>
          <Typography variant="body1" color="text.secondary">
            Select a snapshot to compare judges.
          </Typography>
        </Box>
      ) : checkingAnnotations ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : !annotationStatus?.is_complete ? (
        <Alert severity="info">
          {annotationStatus
            ? `Complete all ${annotationStatus.total_selected} annotations in the annotation tab to view scoring. (${annotationStatus.total_annotated} / ${annotationStatus.total_selected} completed)`
            : "Complete annotations in the annotation tab to view scoring."}
        </Alert>
      ) : (
          <Stack spacing={1.5}>
            {/* Judge Controls */}
            <Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 1 }}>
                <Typography variant="h5">
                  Evaluators
                </Typography>

                <Box sx={{ display: "flex", gap: 1 }}>
                <Tooltip title="Add Judge">
                  <IconButton
                    color="primary"
                    sx={{ border: 1, borderColor: "divider" }}
                    aria-label="add judge"
                    onClick={() => handleOpenDialog("create")}
                  >
                    <AddIcon />
                  </IconButton>
                </Tooltip>

              <span>
                <IconButton
                  sx={{ border: 1, borderColor: "divider" }}
                  aria-label="scroll judges left"
                  onClick={() => handleScrollJudgeCards("left")}
                  disabled={judges.length === 0}
                >
                  <ArrowBackIosNewIcon fontSize="small" />
                </IconButton>
              </span>
              <span>
                <IconButton
                  sx={{ border: 1, borderColor: "divider" }}
                  aria-label="scroll judges right"
                  onClick={() => handleScrollJudgeCards("right")}
                  disabled={judges.length === 0}
                >
                  <ArrowForwardIosIcon fontSize="small" />
                </IconButton>
              </span>
                </Box>
              </Box>

              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Test different AI evaluators to measure your chatbot's accuracy. More reliable evaluators (those that align with your annotations) give you more confidence in the accuracy score.
              </Typography>
            </Box>

            {/* Alert for questions without answers */}
            {questionsWithoutAnswers > 0 && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                {questionsWithoutAnswers} new question{questionsWithoutAnswers > 1 ? "s" : ""} found. Run baseline judge in Annotations tab first.
              </Alert>
            )}

            {/* Judge Cards */}
            <JudgeCards
              judges={judges}
              snapshotId={selectedSnapshotId}
              judgeJobs={judgeJobs}
              scrollContainerRef={judgeCardsRef}
              questionsWithoutScores={questionsWithoutScores}
              hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
              onRunJudge={handleRunJudge}
              onEditJudge={(judge) => handleOpenDialog("edit", judge)}
              onDuplicateJudge={(judge) => handleOpenDialog("duplicate", judge)}
              onDeleteJudge={handleDeleteJudge}
            />

            <Divider sx={{ pt: 2 }}/>

            {/* Results Table */}
            {resultsLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
                <CircularProgress />
              </Box>
            ) : (
              <ResultsTable
                results={results}
                snapshotId={selectedSnapshotId}
                judges={judges}
              />
            )}
          </Stack>
      )}

      {/* Create/Edit Judge Dialog */}
      <CreateJudgeDialog
        open={dialogOpen}
        targetId={targetId}
        mode={dialogMode}
        judge={dialogJudge}
        onClose={handleCloseDialog}
        onSuccess={handleDialogSuccess}
      />
    </Box>
  );
}
