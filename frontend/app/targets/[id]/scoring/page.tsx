"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Add as AddIcon,
  ArrowBackIosNew as ArrowBackIosNewIcon,
  ArrowForwardIos as ArrowForwardIosIcon,
  Download as DownloadIcon,
  ExpandMore as ExpandMoreIcon,
} from "@mui/icons-material";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
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
  TargetRubricResponse,
} from "@/lib/types";
import {
  snapshotApi,
  judgeApi,
  qaJobApi,
  metricsApi,
  annotationApi,
  questionApi,
  targetRubricApi,
} from "@/lib/api";

export default function ScoringPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const targetId = Number(params.id);

  const snapshotIdFromUrl = searchParams.get("snapshot");
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(
    snapshotIdFromUrl ? Number(snapshotIdFromUrl) : null
  );
  const [snapshotsLoading, setSnapshotsLoading] = useState(true);

  const [judges, setJudges] = useState<JudgeConfig[]>([]);
  const [judgesLoading, setJudgesLoading] = useState(true);

  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit" | "duplicate">("create");
  const [dialogJudge, setDialogJudge] = useState<JudgeConfig | null>(null);
  const [judgeToDelete, setJudgeToDelete] = useState<JudgeConfig | null>(null);

  const [results, setResults] = useState<ResultRow[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);

  const [annotationStatus, setAnnotationStatus] = useState<AnnotationCompletionStatus | null>(null);
  const [checkingAnnotations, setCheckingAnnotations] = useState(true);

  const [questionsWithoutAnswers, setQuestionsWithoutAnswers] = useState<number>(0);
  const [questionsWithoutScores, setQuestionsWithoutScores] = useState<Record<number, number>>({});

  const [snapshotMetric, setSnapshotMetric] = useState<SnapshotMetric | null>(null);
  const [snapshotMetricLoading, setSnapshotMetricLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [mainTab, setMainTab] = useState(0); // 0 = Scores, 1 = Error Analysis

  const judgeCardsRef = useRef<HTMLDivElement | null>(null);

  const updateSnapshotSelection = useCallback((snapshotId: number | null) => {
    setSelectedSnapshotId(snapshotId);
    const newSearchParams = new URLSearchParams(searchParams.toString());
    if (snapshotId === null) {
      newSearchParams.delete("snapshot");
    } else {
      newSearchParams.set("snapshot", snapshotId.toString());
    }
    const query = newSearchParams.toString();
    router.push(`/targets/${targetId}/scoring${query ? `?${query}` : ""}`, { scroll: false });
  }, [searchParams, router, targetId]);

  const fetchSnapshots = useCallback(async () => {
    setSnapshotsLoading(true);
    try {
      const response = await snapshotApi.list(targetId);
      setSnapshots(response.data);
      const hasSelected = selectedSnapshotId !== null && response.data.some(s => s.id === selectedSnapshotId);
      if (!hasSelected) {
        if (response.data.length > 0) {
          const mostRecent = [...response.data].sort((a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          )[0];
          updateSnapshotSelection(mostRecent.id);
        } else if (selectedSnapshotId !== null) {
          updateSnapshotSelection(null);
        }
      }
    } catch {
      setError("Failed to load snapshots.");
    } finally {
      setSnapshotsLoading(false);
    }
  }, [targetId, selectedSnapshotId, updateSnapshotSelection]);

  const fetchJudges = useCallback(async () => {
    setJudgesLoading(true);
    try {
      const response = await judgeApi.list(targetId);
      setJudges(response.data.sort((a, b) => Number(b.is_baseline) - Number(a.is_baseline)));
    } catch {
      setError("Failed to load judges.");
    } finally {
      setJudgesLoading(false);
    }
  }, [targetId]);

  const checkAnnotationCompletion = useCallback(async (snapshotId: number) => {
    setCheckingAnnotations(true);
    try {
      const response = await annotationApi.getCompletionStatus(snapshotId);
      setAnnotationStatus(response.data);
    } catch {
      setAnnotationStatus(null);
    } finally {
      setCheckingAnnotations(false);
    }
  }, []);

  const fetchResults = useCallback(async (snapshotId: number) => {
    setResultsLoading(true);
    try {
      const response = await metricsApi.getResults(snapshotId);
      setResults(response.data ?? []);
    } catch {
      setError("Failed to load results.");
    } finally {
      setResultsLoading(false);
    }
  }, []);

  const fetchSnapshotMetrics = useCallback(async () => {
    setSnapshotMetricLoading(true);
    try {
      const response = await metricsApi.getSnapshotMetrics(targetId);
      const currentMetric = response.data.find((m) => m.snapshot_id === selectedSnapshotId) || null;
      setSnapshotMetric(currentMetric);
    } catch {
      setSnapshotMetric(null);
    } finally {
      setSnapshotMetricLoading(false);
    }
  }, [targetId, selectedSnapshotId]);

  const fetchQuestionsWithoutAnswers = useCallback(async (snapshotId: number) => {
    const baselineJudge = judges.find((j) => j.is_baseline);
    if (!baselineJudge) { setQuestionsWithoutAnswers(0); return; }
    try {
      const response = await questionApi.listApprovedWithoutAnswers(snapshotId, baselineJudge.id);
      setQuestionsWithoutAnswers(response.data.length);
    } catch {
      setQuestionsWithoutAnswers(0);
    }
  }, [judges]);

  const fetchQuestionsWithoutScores = useCallback(async (snapshotId: number) => {
    try {
      const counts: Record<number, number> = {};
      for (const judge of judges) {
        const response = await questionApi.listApprovedWithoutScores(snapshotId, judge.id);
        counts[judge.id] = response.data.length;
      }
      setQuestionsWithoutScores(counts);
    } catch {
      setQuestionsWithoutScores({});
    }
  }, [judges]);

  useEffect(() => {
    fetchSnapshots();
    fetchJudges();
    targetRubricApi.list(targetId).then((res) => setRubrics(res.data)).catch(() => {});
  }, [fetchSnapshots, fetchJudges]);

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

  useEffect(() => {
    if (selectedSnapshotId && annotationStatus?.is_complete) {
      fetchResults(selectedSnapshotId);
      fetchSnapshotMetrics();
    }
  }, [selectedSnapshotId, annotationStatus, fetchResults, fetchSnapshotMetrics]);

  const handleSnapshotSelect = (snapshotId: number | null) => updateSnapshotSelection(snapshotId);

  const handleScrollJudgeCards = (direction: "left" | "right") => {
    const container = judgeCardsRef.current;
    if (!container) return;
    container.scrollBy({ left: direction === "left" ? -container.clientWidth * 0.8 : container.clientWidth * 0.8, behavior: "smooth" });
  };

  const handleJobStart = async (judgeId: number): Promise<QAJob[] | null> => {
    if (!selectedSnapshotId) { setError("Select a snapshot to run judges."); return null; }
    try {
      const questionsResponse = await questionApi.listApprovedWithoutScores(selectedSnapshotId, judgeId);
      const questionIdsToScore = questionsResponse.data.map((q) => q.id);
      if (questionIdsToScore.length === 0) { setError("All questions already scored for this judge."); return null; }
      const response = await qaJobApi.start(selectedSnapshotId, { judge_id: judgeId, question_ids: questionIdsToScore });
      return response.data;
    } catch {
      setError("Unable to start judge run.");
      return null;
    }
  };

  const handleJobComplete = useCallback(async () => {
    if (!selectedSnapshotId) return;
    await Promise.all([fetchResults(selectedSnapshotId), fetchQuestionsWithoutScores(selectedSnapshotId), fetchSnapshotMetrics()]);
  }, [selectedSnapshotId, fetchResults, fetchQuestionsWithoutScores, fetchSnapshotMetrics]);

  const handleOpenDialog = (mode: "create" | "edit" | "duplicate", judge?: JudgeConfig) => {
    setDialogMode(mode); setDialogJudge(judge || null); setDialogOpen(true);
  };

  const handleLabelChange = useCallback(async () => {
    if (!selectedSnapshotId) return;
    await Promise.all([fetchResults(selectedSnapshotId), fetchSnapshotMetrics()]);
  }, [selectedSnapshotId, fetchResults, fetchSnapshotMetrics]);

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
    } catch {
      alert("Failed to export snapshot. Please try again.");
    }
  };

  if (snapshotsLoading || judgesLoading) {
    return <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}><CircularProgress /></Box>;
  }

  return (
    <Box>
      {/* Snapshot header + export */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 1, mb: 2 }}>
        <Box sx={{ flex: 1 }}>
          <SnapshotHeader
            targetId={targetId}
            snapshots={snapshots}
            selectedSnapshotId={selectedSnapshotId}
            onSelectSnapshot={handleSnapshotSelect}
            onSnapshotCreated={fetchSnapshots}
            onSnapshotDeleted={fetchSnapshots}
          />
        </Box>
        <Tooltip title="Download data for this snapshot">
          <span>
            <IconButton
              onClick={handleExportSnapshot}
              disabled={!selectedSnapshotId}
              sx={{
                bgcolor: "secondary.main", color: "white", borderRadius: 1,
                "&:hover": { bgcolor: "secondary.dark" },
                "&.Mui-disabled": { bgcolor: "action.disabledBackground", color: "action.disabled" },
              }}
            >
              <DownloadIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      {!selectedSnapshotId ? (
        <Box sx={{ py: 6, textAlign: "center" }}>
          <Typography variant="body1" color="text.secondary">Select a snapshot to compare judges.</Typography>
        </Box>
      ) : checkingAnnotations ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}><CircularProgress /></Box>
      ) : !annotationStatus?.is_complete ? (
        <Alert severity="info">
          {annotationStatus ? (() => {
            const totalSelected = annotationStatus.selected_ids.length;
            const totalAnnotated = annotationStatus.selected_and_annotated_ids.length;
            const annotatedSet = new Set(annotationStatus.selected_and_annotated_ids);
            const unannotatedIds = annotationStatus.selected_ids.filter(id => !annotatedSet.has(id));
            return <>
              {`Complete all ${totalSelected} annotations to view scoring. (${totalAnnotated} / ${totalSelected} done)`}
              {unannotatedIds.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <strong>Unannotated:</strong>
                  <Box component="ul" sx={{ mt: 0, mb: 0, pl: 2 }}>
                    {unannotatedIds.map((id) => <li key={id}>Q{id}</li>)}
                  </Box>
                </Box>
              )}
            </>;
          })() : "Complete annotations to view scoring."}
        </Alert>
      ) : (
        <Stack spacing={2}>
          {questionsWithoutAnswers > 0 && (
            <Alert severity="warning">
              {questionsWithoutAnswers} new question{questionsWithoutAnswers > 1 ? "s" : ""} found. Run baseline judge in Annotations tab first.
            </Alert>
          )}

          {/* Main Tabs */}
          <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
            <Tabs value={mainTab} onChange={(_, v) => setMainTab(v)}>
              <Tab label="Scores" />
              <Tab label="Error Analysis" />
            </Tabs>
          </Box>

          {/* ── SCORES TAB ── */}
          {mainTab === 0 && (
            <Stack spacing={2}>
              {/* Overall score card */}
              <SnapshotAccuracyCard
                snapshotMetric={snapshotMetric}
                loading={snapshotMetricLoading}
                emptyMessage="Run evaluators to see results"
                showExplanatoryText
              />

              {/* Accuracy evaluators section (collapsible) */}
              <EvaluatorSection
                title="Accuracy Evaluators"
                description="Evaluators that measure factual accuracy against your knowledge base."
                judges={judges}
                snapshotId={selectedSnapshotId}
                scrollContainerRef={judgeCardsRef}
                questionsWithoutScores={questionsWithoutScores}
                hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                onJobStart={handleJobStart}
                onJobComplete={handleJobComplete}
                onEditJudge={(j) => handleOpenDialog("edit", j)}
                onDuplicateJudge={(j) => handleOpenDialog("duplicate", j)}
                onDeleteJudge={(j) => {
                  if (!j.is_editable || j.is_baseline) { setError("Cannot delete this judge."); return; }
                  setJudgeToDelete(j);
                }}
                onAddJudge={() => handleOpenDialog("create")}
                onScrollLeft={() => handleScrollJudgeCards("left")}
                onScrollRight={() => handleScrollJudgeCards("right")}
              />

              {/* Custom rubric evaluator stubs */}
              {rubrics.map((rubric) => (
                <Accordion key={rubric.id} variant="outlined" disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography fontWeight={600}>{rubric.name} Evaluators</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Typography variant="body2" color="text.secondary">
                      No evaluators configured for this rubric yet. Custom rubric evaluators will appear here once added.
                    </Typography>
                  </AccordionDetails>
                </Accordion>
              ))}
            </Stack>
          )}

          {/* ── ERROR ANALYSIS TAB ── */}
          {mainTab === 1 && (
            resultsLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}><CircularProgress /></Box>
            ) : (
              <ResultsTable
                results={results}
                snapshotId={selectedSnapshotId}
                judges={judges}
                rubrics={rubrics}
                onLabelChange={handleLabelChange}
              />
            )
          )}
        </Stack>
      )}

      <CreateJudgeDialog
        open={dialogOpen}
        targetId={targetId}
        mode={dialogMode}
        judge={dialogJudge}
        onClose={() => { setDialogOpen(false); setDialogJudge(null); }}
        onSuccess={async () => { await fetchJudges(); setDialogOpen(false); setDialogJudge(null); }}
      />

      <ConfirmDeleteDialog
        open={judgeToDelete !== null}
        onClose={() => setJudgeToDelete(null)}
        onConfirm={async () => {
          if (!judgeToDelete) return;
          await judgeApi.delete(judgeToDelete.id);
          await fetchJudges();
          setJudgeToDelete(null);
        }}
        title="Delete Judge"
        itemName={judgeToDelete?.name}
      />
    </Box>
  );
}

// ── Collapsible evaluator section ──────────────────────────────────────────
interface EvaluatorSectionProps {
  title: string;
  description: string;
  judges: JudgeConfig[];
  snapshotId: number;
  scrollContainerRef: React.Ref<HTMLDivElement>;
  questionsWithoutScores: Record<number, number>;
  hasQuestionsWithoutAnswers: boolean;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEditJudge: (judge: JudgeConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
  onAddJudge: () => void;
  onScrollLeft: () => void;
  onScrollRight: () => void;
}

function EvaluatorSection({
  title, description, judges, snapshotId, scrollContainerRef,
  questionsWithoutScores, hasQuestionsWithoutAnswers,
  onJobStart, onJobComplete, onEditJudge, onDuplicateJudge, onDeleteJudge,
  onAddJudge, onScrollLeft, onScrollRight,
}: EvaluatorSectionProps) {
  return (
    <Accordion defaultExpanded variant="outlined" disableGutters>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography fontWeight={600}>{title}</Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        {/* Controls row — outside AccordionSummary to avoid nested <button> */}
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
          <Typography variant="body2" color="text.secondary">{description}</Typography>
          <Stack direction="row" spacing={1}>
            <Tooltip title="Add Judge">
              <IconButton size="small" color="primary" sx={{ border: 1, borderColor: "divider" }} onClick={onAddJudge}>
                <AddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <IconButton size="small" sx={{ border: 1, borderColor: "divider" }} onClick={onScrollLeft} disabled={judges.length === 0}>
              <ArrowBackIosNewIcon fontSize="small" />
            </IconButton>
            <IconButton size="small" sx={{ border: 1, borderColor: "divider" }} onClick={onScrollRight} disabled={judges.length === 0}>
              <ArrowForwardIosIcon fontSize="small" />
            </IconButton>
          </Stack>
        </Stack>
        <JudgeCards
          judges={judges}
          snapshotId={snapshotId}
          scrollContainerRef={scrollContainerRef}
          questionsWithoutScores={questionsWithoutScores}
          hasQuestionsWithoutAnswers={hasQuestionsWithoutAnswers}
          onJobStart={onJobStart}
          onJobComplete={onJobComplete}
          onEditJudge={onEditJudge}
          onDuplicateJudge={onDuplicateJudge}
          onDeleteJudge={onDeleteJudge}
        />
      </AccordionDetails>
    </Accordion>
  );
}
