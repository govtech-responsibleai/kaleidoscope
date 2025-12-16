"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
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
  const targetId = Number(params.id);

  // Snapshot state
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(null);
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
        setSelectedSnapshotId(response.data[0].id);
      }
    } catch (error) {
      console.error("Failed to fetch snapshots:", error);
      setError("Failed to load snapshots.");
    } finally {
      setSnapshotsLoading(false);
    }
  }, [targetId, selectedSnapshotId]);

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
        }
      };

      runPoll();

      const intervalId = window.setInterval(runPoll, 5000);
      pollingRefs.current[judgeId] = intervalId;
    },
    [checkJudgeJobStatuses, fetchResults]
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

    if (selectedSnapshotId) {
      checkAnnotationCompletion(selectedSnapshotId);
      checkJudgeJobStatuses(selectedSnapshotId);
    }
  }, [selectedSnapshotId, checkAnnotationCompletion, checkJudgeJobStatuses]);

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
      // Get only approved questions (matching annotation flow)
      const questionsResponse = await questionApi.listByTarget(targetId);
      const approvedQuestionIds = questionsResponse.data
        .filter((q) => q.status === "approved")
        .map((q) => q.id);

      // Start judge job
      if (approvedQuestionIds.length === 0) {
        setError("No approved questions available to score. Approve questions first.");
        return;
      }

      const response = await qaJobApi.start(selectedSnapshotId, {
        judge_id: judgeId,
        question_ids: approvedQuestionIds,
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
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
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
          <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>

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

          {/* Judge Cards */}
          <JudgeCards
            judges={judges}
            snapshotId={selectedSnapshotId}
            judgeJobs={judgeJobs}
            scrollContainerRef={judgeCardsRef}
            onRunJudge={handleRunJudge}
            onEditJudge={(judge) => handleOpenDialog("edit", judge)}
            onDuplicateJudge={(judge) => handleOpenDialog("duplicate", judge)}
            onDeleteJudge={handleDeleteJudge}
          />

          <Divider />

          {/* Results Table */}
          {resultsLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <ResultsTable
              results={results}
              snapshotId={selectedSnapshotId}
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
