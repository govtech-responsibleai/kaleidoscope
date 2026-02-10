"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Alert,
  Box,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Add as AddIcon,
  ArrowBackIosNew as ArrowBackIosNewIcon,
  ArrowForwardIos as ArrowForwardIosIcon,
  Download as DownloadIcon,
} from "@mui/icons-material";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import JudgeCards from "@/components/scoring/JudgeCards";
import CreateJudgeDialog from "@/components/scoring/CreateJudgeDialog";
import ResultsTable from "@/components/scoring/ResultsTable";
import SnapshotAccuracyCard from "@/components/shared/SnapshotAccuracyCard";
import {
  Snapshot,
  JudgeConfig,
  ResultRow,
  AnnotationCompletionStatus,
  QAJob,
  SnapshotMetric,
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

  // Aggregated metrics state
  const [snapshotMetric, setSnapshotMetric] = useState<SnapshotMetric | null>(null);
  const [snapshotMetricLoading, setSnapshotMetricLoading] = useState(false);

  // UI state
  const [error, setError] = useState<string | null>(null);
  const judgeCardsRef = useRef<HTMLDivElement | null>(null);

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
    } catch (error) {
      console.error("Failed to fetch results:", error);
      setError("Failed to load results.");
    } finally {
      setResultsLoading(false);
    }
  }, []);

  // Fetch snapshot metrics (aggregated accuracy)
  const fetchSnapshotMetrics = useCallback(async () => {
    setSnapshotMetricLoading(true);
    try {
      const response = await metricsApi.getSnapshotMetrics(targetId);
      const metrics = response.data.snapshots;
      // Find the metric for the selected snapshot
      const currentMetric = metrics.find((m) => m.snapshot_id === selectedSnapshotId) || null;
      setSnapshotMetric(currentMetric);
    } catch (error) {
      console.error("Failed to fetch snapshot metrics:", error);
      setSnapshotMetric(null);
    } finally {
      setSnapshotMetricLoading(false);
    }
  }, [targetId, selectedSnapshotId]);

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

  // Initial data fetch
  useEffect(() => {
    fetchSnapshots();
    fetchJudges();
  }, [fetchSnapshots, fetchJudges]);

  // Fetch data when snapshot changes
  useEffect(() => {
    setAnnotationStatus(null);
    setResults([]);
    setQuestionsWithoutAnswers(0);
    setQuestionsWithoutScores({});
    setSnapshotMetric(null);

    if (selectedSnapshotId) {
      checkAnnotationCompletion(selectedSnapshotId);
      fetchQuestionsWithoutAnswers(selectedSnapshotId);
      fetchQuestionsWithoutScores(selectedSnapshotId);
    }
  }, [selectedSnapshotId, checkAnnotationCompletion, fetchQuestionsWithoutAnswers, fetchQuestionsWithoutScores]);

  // Fetch results and metrics when annotations are complete
  useEffect(() => {
    if (selectedSnapshotId && annotationStatus?.is_complete) {
      fetchResults(selectedSnapshotId);
      fetchSnapshotMetrics();
    }
  }, [selectedSnapshotId, annotationStatus, fetchResults, fetchSnapshotMetrics]);

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

  // Handle job start - creates jobs and returns them for JudgeCard to manage
  const handleJobStart = async (judgeId: number): Promise<QAJob[] | null> => {
    if (!selectedSnapshotId) {
      setError("Select a snapshot to run judges.");
      return null;
    }

    try {
      // Get only questions without scores for this judge
      const questionsResponse = await questionApi.listApprovedWithoutScores(selectedSnapshotId, judgeId);
      const questionIdsToScore = questionsResponse.data.map((q) => q.id);

      if (questionIdsToScore.length === 0) {
        setError("All questions already scored for this judge.");
        return null;
      }

      const response = await qaJobApi.start(selectedSnapshotId, {
        judge_id: judgeId,
        question_ids: questionIdsToScore,
        is_scoring: true,
      });

      return response.data;
    } catch (error) {
      console.error("Failed to run judge:", error);
      setError("Unable to start judge run.");
      return null;
    }
  };

  // Handle job completion - refresh results and metrics
  const handleJobComplete = useCallback(async () => {
    if (!selectedSnapshotId) return;

    await Promise.all([
      fetchResults(selectedSnapshotId),
      fetchQuestionsWithoutScores(selectedSnapshotId),
      fetchSnapshotMetrics(),
    ]);
  }, [selectedSnapshotId, fetchResults, fetchQuestionsWithoutScores, fetchSnapshotMetrics]);

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

  // Handle label change (refresh results and metrics)
  const handleLabelChange = useCallback(async () => {
    if (!selectedSnapshotId) return;

    // Refresh both results and metrics to reflect the label change
    await Promise.all([
      fetchResults(selectedSnapshotId),
      fetchSnapshotMetrics(),
    ]);
  }, [selectedSnapshotId, fetchResults, fetchSnapshotMetrics]);

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

  const handleExportSnapshot = async () => {
    if (!selectedSnapshotId) return;
    try {
      const response = await metricsApi.exportJSON(selectedSnapshotId);
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `snapshot_${selectedSnapshotId}_results.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to export snapshot:", error);
      alert("Failed to export snapshot. Please try again.");
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
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 1 }}>
        <Box sx={{ flex: 1 }}>
          <SnapshotHeader
            targetId={targetId}
            snapshots={snapshots}
            selectedSnapshotId={selectedSnapshotId}
            onSelectSnapshot={handleSnapshotSelect}
            onSnapshotCreated={fetchSnapshots}
          />
        </Box>
        <Tooltip title="Download data for this snapshot">
          <span>
            <IconButton
              onClick={handleExportSnapshot}
              disabled={!selectedSnapshotId}
              sx={{
                bgcolor: "secondary.main",
                color: "white",
                borderRadius: 1,
                "&:hover": { bgcolor: "secondary.dark" },
                "&.Mui-disabled": { bgcolor: "action.disabledBackground", color: "action.disabled" },
              }}
            >
              <DownloadIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

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
            ? (() => {
                const totalSelected = annotationStatus.selected_ids.length;
                const totalAnnotated = annotationStatus.selected_and_annotated_ids.length;
                const annotatedSet = new Set(annotationStatus.selected_and_annotated_ids);
                const unannotatedIds = annotationStatus.selected_ids.filter(id => !annotatedSet.has(id));
                return <>
                  {`Complete all ${totalSelected} annotations in the annotation tab to view scoring. (${totalAnnotated} / ${totalSelected} completed)`}
                  {unannotatedIds.length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <strong>Incomplete Questions:</strong>
                      <Box component="ul" sx={{ mt: 0, mb: 0, pl: 2 }}>
                        {unannotatedIds.map((id) => (
                          <li key={id}>Q{id}</li>
                        ))}
                      </Box>
                    </Box>
                  )}
                </>;
              })()
            : "Complete annotations in the annotation tab to view scoring."}
        </Alert>
      ) : (
          <Stack spacing={1.5}>
            {/* Alert for questions without answers */}
            {questionsWithoutAnswers > 0 && (
              <Alert severity="warning">
                {questionsWithoutAnswers} new question{questionsWithoutAnswers > 1 ? "s" : ""} found. Run baseline judge in Annotations tab first.
              </Alert>
            )}

            {/* Aggregated Accuracy Card + Evaluators Section */}
            <Stack direction="row" spacing={3} alignItems="stretch">
              {/* Aggregated Accuracy Card - Fixed on left */}
              <SnapshotAccuracyCard
                snapshotMetric={snapshotMetric}
                loading={snapshotMetricLoading}
                emptyMessage="Run evaluators to see results"
                showExplanatoryText
              />

              {/* Evaluators Header + Carousel */}
              <Paper
                variant="outlined"
                sx={{
                  flex: 1,
                  minWidth: 0,
                  bgcolor: "rgb(0, 0, 0, 0.01)",
                  p: 2
                }}
              >
                {/* Header */}
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 1 }}>
                    <Typography variant="h5">
                      Your Evaluator List
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
                    Accuracy is aggregated from the following evaluators. Test multiple AI evaluators to measure your chatbot&apos;s accuracy!
                    <br/>
                    More reliable evaluators (those that align with your annotations) give you more confidence in the accuracy score.
                  </Typography>
                </Box>

                {/* Judge Cards Carousel */}
                <JudgeCards
                  judges={judges}
                  snapshotId={selectedSnapshotId}
                  scrollContainerRef={judgeCardsRef}
                  questionsWithoutScores={questionsWithoutScores}
                  hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                  onJobStart={handleJobStart}
                  onJobComplete={handleJobComplete}
                  onEditJudge={(judge) => handleOpenDialog("edit", judge)}
                  onDuplicateJudge={(judge) => handleOpenDialog("duplicate", judge)}
                  onDeleteJudge={handleDeleteJudge}
                />
              </Paper>
            </Stack>

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
                onLabelChange={handleLabelChange}
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
