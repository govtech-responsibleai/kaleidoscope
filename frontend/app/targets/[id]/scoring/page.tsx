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
import AccuracyGauge from "@/components/shared/AccuracyGauge";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import JudgeCards from "@/components/scoring/JudgeCards";
import RubricJudgeCard from "@/components/scoring/RubricJudgeCard";
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
  getApiErrorMessage,
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
  const [dialogCategory, setDialogCategory] = useState<string>("accuracy");
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

  const [rubricMetrics, setRubricMetrics] = useState<SnapshotMetric[]>([]);
  const [rubricMetricsLoading, setRubricMetricsLoading] = useState(false);

  // Incremented on label override to signal JudgeCards to refetch metrics
  const [labelOverrideCount, setLabelOverrideCount] = useState(0);

  const [error, setError] = useState<string | null>(null);
  const [mainTab, setMainTab] = useState(0); // 0 = Scores, 1 = Error Analysis

  const judgeCardsRef = useRef<HTMLDivElement | null>(null);
  const baselineJudge = judges.find((j) => j.is_baseline) ?? null;

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
      setJudges(response.data);
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

  const fetchRubricMetrics = useCallback(async () => {
    if (!selectedSnapshotId) return;
    setRubricMetricsLoading(true);
    try {
      const response = await metricsApi.getRubricSnapshotMetrics(targetId, selectedSnapshotId);
      setRubricMetrics(response.data);
    } catch {
      setRubricMetrics([]);
    } finally {
      setRubricMetricsLoading(false);
    }
  }, [targetId, selectedSnapshotId]);

  const fetchQuestionsWithoutAnswers = useCallback(async (snapshotId: number) => {
    if (!baselineJudge) { setQuestionsWithoutAnswers(0); return; }
    try {
      const response = await questionApi.listApprovedWithoutAnswers(snapshotId, baselineJudge.id);
      setQuestionsWithoutAnswers(response.data.length);
    } catch {
      setQuestionsWithoutAnswers(0);
    }
  }, [baselineJudge]);

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
    targetRubricApi.list(targetId).then((res) => {
      setRubrics(res.data);
    }).catch(() => {});
  }, [targetId]);

  useEffect(() => {
    setAnnotationStatus(null);
    setResults([]);
    setQuestionsWithoutAnswers(0);
    setQuestionsWithoutScores({});
    setSnapshotMetric(null);
    setRubricMetrics([]);
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
      fetchRubricMetrics();
    }
  }, [selectedSnapshotId, annotationStatus, fetchResults, fetchSnapshotMetrics, fetchRubricMetrics]);

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
    } catch (error) {
      setError(getApiErrorMessage(error, "Unable to start judge run."));
      return null;
    }
  };

  const handleRubricJobStart = async (judgeId: number, rubricId: number): Promise<QAJob[] | null> => {
    if (!selectedSnapshotId) { setError("Select a snapshot to run judges."); return null; }
    if (!baselineJudge) { setError("Baseline judge not found."); return null; }
    try {
      const questionsResponse = await questionApi.listApprovedWithoutRubricScores(selectedSnapshotId, judgeId, rubricId);
      const questionIds = questionsResponse.data.map((q) => q.id);
      if (questionIds.length === 0) { setError("All questions already scored for this rubric judge."); return null; }
      const response = await qaJobApi.startAll(selectedSnapshotId, {
        judge_id: baselineJudge.id,
        question_ids: questionIds,
        rubric_specs: [{ rubric_id: rubricId, judge_id: judgeId }],
      });
      return response.data;
    } catch (error) {
      setError(getApiErrorMessage(error, "Unable to start rubric judge run."));
      return null;
    }
  };

  const handleJobComplete = useCallback(async () => {
    if (!selectedSnapshotId) return;
    await Promise.all([fetchResults(selectedSnapshotId), fetchQuestionsWithoutScores(selectedSnapshotId), fetchSnapshotMetrics(), fetchRubricMetrics()]);
  }, [selectedSnapshotId, fetchResults, fetchQuestionsWithoutScores, fetchSnapshotMetrics, fetchRubricMetrics]);

  const handleOpenDialog = (mode: "create" | "edit" | "duplicate", judge?: JudgeConfig, category?: string) => {
    setDialogMode(mode);
    setDialogCategory(judge?.category ?? category ?? "accuracy");
    setDialogJudge(judge || null);
    setDialogOpen(true);
  };

  const handleLabelChange = useCallback(async () => {
    if (!selectedSnapshotId) return;
    await Promise.all([fetchResults(selectedSnapshotId), fetchSnapshotMetrics()]);
    setLabelOverrideCount((c) => c + 1);
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
                          <li key={id}>
                            <Box
                              component="a"
                              onClick={() => router.push(`/targets/${targetId}/annotation?snapshot=${selectedSnapshotId}&question=${id}`)}
                              sx={{ color: "primary.main", cursor: "pointer", textDecoration: "underline", "&:hover": { color: "primary.dark" } }}
                            >
                              Q{id}
                            </Box>
                          </li>
                        ))}
                      </Box>
                    </Box>
                  )}
                </>;
              })()
            : "Complete annotations in the annotation tab to view scoring."}
        </Alert>
      ) : (
        <Stack spacing={2}>
          {questionsWithoutAnswers > 0 && (
            <Alert severity="warning">
              {questionsWithoutAnswers} new question{questionsWithoutAnswers > 1 ? "s" : ""} found. Run primary judge in Annotations tab first.
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
              {/* Score gauges - side by side */}
              <Stack direction="row" spacing={2} sx={{ overflowX: "auto", pb: 1 }}>
                <Paper variant="outlined" sx={{ flex: "1 1 0", minWidth: 280, p: 2 }}>
                  <SnapshotAccuracyCard
                    snapshotMetric={snapshotMetric}
                    loading={snapshotMetricLoading}
                    emptyMessage="Run judges to see results"
                    showExplanatoryText
                  />
                </Paper>
                {rubrics.map((rubric) => {
                  const rubricMetric = rubricMetrics.find((m) => m.rubric_id === rubric.id);
                  return (
                    <Paper key={rubric.id} variant="outlined" sx={{ flex: "1 1 0", minWidth: 280, p: 2 }}>
                      <RubricScoreGauge
                        rubric={rubric}
                        metric={rubricMetric ?? null}
                        loading={rubricMetricsLoading}
                      />
                    </Paper>
                  );
                })}
              </Stack>

              {/* Baseline Evaluators + pre-made rubric judges */}
              {(() => {
                const premadeRubrics = rubrics.filter((r) => !!r.template_key);
                const customRubrics = rubrics.filter((r) => !r.template_key);
                return (
                  <>
                    <EvaluatorSection
                      title="Baseline Evaluators"
                      description="Judges that detect hallucinations and verify claims are supported by the provided context."
                      judges={judges.filter((j) => j.category === "accuracy")}
                      snapshotId={selectedSnapshotId}
                      scrollContainerRef={judgeCardsRef}
                      questionsWithoutScores={questionsWithoutScores}
                      hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                      getDisplayName={(j) => j.name}
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
                      labelOverrideCount={labelOverrideCount}
                    >
                      {premadeRubrics.length > 0 && (
                        <Box sx={{ mt: 2 }}>
                          {premadeRubrics.map((rubric, idx) => {
                            const rubricJudges = judges.filter((j) => j.category === rubric.template_key);
                            return (
                              <Box key={rubric.id} sx={{ mb: idx < premadeRubrics.length - 1 ? 3 : 0 }}>
                                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                                  {rubric.name}
                                </Typography>
                                <Box sx={{ display: "flex", gap: 2, overflowX: "auto", pb: 1 }}>
                                  {rubricJudges.length > 0 ? rubricJudges.map((judge) => (
                                    <RubricJudgeCard
                                      key={judge.id}
                                      judge={judge}
                                      displayName={judge.name}
                                      snapshotId={selectedSnapshotId}
                                      rubricId={rubric.id}
                                      bestOption={rubric.best_option || rubric.options?.[0]?.option || ""}
                                      hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                                      onJobStart={(judgeId) => handleRubricJobStart(judgeId, rubric.id)}
                                      onJobComplete={handleJobComplete}
                                    />
                                  )) : (
                                    <Typography variant="body2" color="text.secondary">
                                      No judges configured for this rubric.
                                    </Typography>
                                  )}
                                </Box>
                              </Box>
                            );
                          })}
                        </Box>
                      )}
                    </EvaluatorSection>

                    {/* Custom rubric judges */}
                    {customRubrics.length > 0 && (
                      <Accordion variant="outlined" disableGutters>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                          <Typography fontWeight={600}>Custom Rubric Judges</Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ pt: 1 }}>
                          {customRubrics.map((rubric, idx) => {
                            const rubricJudges = judges.filter((j) => j.category === "default" && j.judge_type === "response_level");
                            return (
                              <Box key={rubric.id} sx={{ mb: idx < customRubrics.length - 1 ? 3 : 0 }}>
                                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                                  {rubric.name}
                                </Typography>
                                <Box sx={{ display: "flex", gap: 2, overflowX: "auto", pb: 1 }}>
                                  {rubricJudges.length > 0 ? rubricJudges.map((judge) => (
                                    <RubricJudgeCard
                                      key={judge.id}
                                      judge={judge}
                                      displayName={judge.name}
                                      snapshotId={selectedSnapshotId}
                                      rubricId={rubric.id}
                                      bestOption={rubric.best_option || rubric.options?.[0]?.option || ""}
                                      hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                                      onJobStart={(judgeId) => handleRubricJobStart(judgeId, rubric.id)}
                                      onJobComplete={handleJobComplete}
                                    />
                                  )) : (
                                    <Typography variant="body2" color="text.secondary">
                                      No judges configured for this rubric.
                                    </Typography>
                                  )}
                                </Box>
                              </Box>
                            );
                          })}
                        </AccordionDetails>
                      </Accordion>
                    )}
                  </>
                );
              })()}
            </Stack>
          )}

          {/* ── ERROR ANALYSIS TAB ── */}
          {mainTab === 1 && (
            resultsLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}><CircularProgress /></Box>
            ) : (
              <ResultsTable
                results={results}
                targetId={targetId}
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
        category={dialogCategory}
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

// ── Collapsible judge section ──────────────────────────────────────────
interface EvaluatorSectionProps {
  title: string;
  description: string;
  judges: JudgeConfig[];
  snapshotId: number;
  scrollContainerRef: React.Ref<HTMLDivElement>;
  questionsWithoutScores: Record<number, number>;
  hasQuestionsWithoutAnswers: boolean;
  getDisplayName?: (judge: JudgeConfig) => string;
  onJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEditJudge: (judge: JudgeConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
  onAddJudge: () => void;
  onScrollLeft: () => void;
  onScrollRight: () => void;
  labelOverrideCount: number;
  children?: React.ReactNode;
}

function EvaluatorSection({
  title, description, judges, snapshotId, scrollContainerRef,
  questionsWithoutScores, hasQuestionsWithoutAnswers, getDisplayName,
  onJobStart, onJobComplete, onEditJudge, onDuplicateJudge, onDeleteJudge,
  onAddJudge, onScrollLeft, onScrollRight, labelOverrideCount, children,
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
          getDisplayName={getDisplayName}
          onJobStart={onJobStart}
          onJobComplete={onJobComplete}
          onEditJudge={onEditJudge}
          onDuplicateJudge={onDuplicateJudge}
          onDeleteJudge={onDeleteJudge}
          labelOverrideCount={labelOverrideCount}
        />
        {children}
      </AccordionDetails>
    </Accordion>
  );
}

// ── Rubric score gauge (analogous to SnapshotAccuracyCard) ─────────────
function RubricScoreGauge({
  rubric,
  metric,
  loading,
}: {
  rubric: TargetRubricResponse;
  metric: SnapshotMetric | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="160px">
          <CircularProgress />
        </Box>
      </Box>
    );
  }

  if (!metric || metric.total_answers === 0) {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
        <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
          Overall {rubric.name}
        </Typography>
        <Typography variant="h2" fontWeight={700} color="text.disabled">
          --%
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Run judges to see results
        </Typography>
      </Box>
    );
  }

  const hasReliableJudges = metric.aligned_judges.length > 0;
  const reliableJudgeCount = metric.aligned_judges.length;
  const alignmentRange = metric.judge_alignment_range;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        Overall {rubric.name}
      </Typography>

      <AccuracyGauge
        value={hasReliableJudges ? metric.aggregated_accuracy : null}
        size={300}
        label={`% ${rubric.best_option || rubric.options?.[0]?.option || "best option"}`}
      />

      <Stack spacing={0.5} alignItems="center" sx={{ mt: 1 }}>
        {hasReliableJudges && alignmentRange ? (
          <Typography variant="body2" color="text.secondary" textAlign="center">
            from {reliableJudgeCount} judge{reliableJudgeCount !== 1 ? "s" : ""}{" "}
            <Box component="span" sx={{ color: "success.main", fontWeight: 500 }}>
              ({(alignmentRange.min * 100).toFixed(0)}%-{(alignmentRange.max * 100).toFixed(0)}% reliability)
            </Box>
          </Typography>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No reliable judges yet
          </Typography>
        )}
      </Stack>

      <Typography
        variant="caption"
        color="text.secondary"
        textAlign="center"
        sx={{ mt: 2, maxWidth: 350 }}
      >
        Score shows the % of answers where reliable judges chose &ldquo;{rubric.best_option || rubric.options?.[0]?.option || "best option"}&rdquo; via majority vote.
      </Typography>
    </Box>
  );
}
