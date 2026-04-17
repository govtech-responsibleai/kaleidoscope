"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  Chip,
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
  IconCode,
  IconPlus,
} from "@tabler/icons-react";
import AccuracyGauge from "@/components/shared/AccuracyGauge";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import JudgeCard from "@/components/scoring/JudgeCard";
import RubricJudgeCard from "@/components/scoring/RubricJudgeCard";
import CreateJudgeDialog from "@/components/scoring/CreateJudgeDialog";
import ResultsTable from "@/components/scoring/ResultsTable";
import {
  Snapshot,
  JudgeConfig,
  ResultRow,
  AnnotationCompletionStatus,
  QAJob,
  SnapshotMetric,
  TargetRubricResponse,
  JudgeType,
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
import { actionIconProps, compactActionIconProps } from "@/lib/iconStyles";
import { groupColors } from "@/lib/theme";
import { sortJudges } from "@/lib/judgeOrdering";

type SourceGroup = "fixed" | "preset" | "custom";

interface MetricSectionConfig {
  key: string;
  title: string;
  description: string;
  sourceGroup: SourceGroup;
  category: string;
  judgeType: JudgeType;
  rubric: TargetRubricResponse | null;
  metric: SnapshotMetric | null;
  judges: JudgeConfig[];
  emptyMessage: string;
  gaugeLabel: string;
  defaultPromptTemplate: string;
}

interface DialogConfig {
  category: string;
  rubricId: number | null;
  judgeType: JudgeType | null;
  metricLabel: string;
  defaultPromptTemplate: string;
}

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
  const [dialogConfig, setDialogConfig] = useState<DialogConfig>({
    category: "accuracy",
    rubricId: null,
    judgeType: null,
    metricLabel: "Accuracy",
    defaultPromptTemplate: "",
  });
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
  const [rubricPendingCounts, setRubricPendingCounts] = useState<Record<string, number>>({});

  const [labelOverrideCount, setLabelOverrideCount] = useState(0);

  const [error, setError] = useState<string | null>(null);
  const [mainTab, setMainTab] = useState(0);
  const pendingCountsRequestRef = useRef(0);
  const snapshotMetricsRequestRef = useRef(0);

  const accuracyJudges = sortJudges(
    judges.filter((judge) => judge.category === "accuracy" && judge.judge_type === "claim_based")
  );
  const baselineJudge = accuracyJudges.find((judge) => judge.is_baseline) ?? null;

  const getRubricJudgesForRubric = useCallback((rubric: TargetRubricResponse) => {
    return sortJudges(
      judges.filter((judge) => {
        if (judge.judge_type !== "response_level" || judge.category !== rubric.category) {
          return false;
        }
        if (rubric.template_key) {
          return judge.rubric_id == null || judge.rubric_id === rubric.id;
        }
        return judge.rubric_id == null || judge.rubric_id === rubric.id;
      })
    );
  }, [judges]);

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
      const hasSelected = selectedSnapshotId !== null && response.data.some((snapshot) => snapshot.id === selectedSnapshotId);
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
    } catch (snapshotError) {
      setError(getApiErrorMessage(snapshotError, "Failed to load snapshots."));
    } finally {
      setSnapshotsLoading(false);
    }
  }, [targetId, selectedSnapshotId, updateSnapshotSelection]);

  const fetchJudges = useCallback(async () => {
    setJudgesLoading(true);
    try {
      const response = await judgeApi.list(targetId);
      setJudges(response.data);
    } catch (judgeError) {
      setError(getApiErrorMessage(judgeError, "Failed to load judges."));
    } finally {
      setJudgesLoading(false);
    }
  }, [targetId]);

  const checkAnnotationCompletion = useCallback(async (snapshotId: number, requestId?: number) => {
    setCheckingAnnotations(true);
    try {
      const response = await annotationApi.getCompletionStatus(snapshotId);
      if (requestId && requestId !== pendingCountsRequestRef.current) return;
      setAnnotationStatus(response.data);
    } catch {
      if (requestId && requestId !== pendingCountsRequestRef.current) return;
      setAnnotationStatus(null);
    } finally {
      if (!requestId || requestId === pendingCountsRequestRef.current) {
        setCheckingAnnotations(false);
      }
    }
  }, []);

  const fetchResults = useCallback(async (snapshotId: number, requestId?: number) => {
    setResultsLoading(true);
    try {
      const response = await metricsApi.getResults(snapshotId);
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      setResults(response.data ?? []);
    } catch (resultsError) {
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      setError(getApiErrorMessage(resultsError, "Failed to load results."));
    } finally {
      if (!requestId || requestId === snapshotMetricsRequestRef.current) {
        setResultsLoading(false);
      }
    }
  }, []);

  const fetchSnapshotMetrics = useCallback(async (snapshotId: number, requestId?: number) => {
    setSnapshotMetricLoading(true);
    try {
      const response = await metricsApi.getSnapshotMetrics(targetId);
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      const currentMetric = response.data.find((metric) => metric.snapshot_id === snapshotId) || null;
      setSnapshotMetric(currentMetric);
    } catch {
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      setSnapshotMetric(null);
    } finally {
      if (!requestId || requestId === snapshotMetricsRequestRef.current) {
        setSnapshotMetricLoading(false);
      }
    }
  }, [targetId]);

  const fetchRubricMetrics = useCallback(async (snapshotId: number, requestId?: number) => {
    setRubricMetricsLoading(true);
    try {
      const response = await metricsApi.getRubricSnapshotMetrics(targetId, snapshotId);
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      setRubricMetrics(response.data);
    } catch {
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      setRubricMetrics([]);
    } finally {
      if (!requestId || requestId === snapshotMetricsRequestRef.current) {
        setRubricMetricsLoading(false);
      }
    }
  }, [targetId]);

  const fetchScoringPendingCounts = useCallback(async (snapshotId: number, requestId?: number) => {
    try {
      const response = await metricsApi.getScoringPendingCounts(snapshotId);
      if (requestId && requestId !== pendingCountsRequestRef.current) return;
      setQuestionsWithoutAnswers(response.data.unanswered_question_count);
      setQuestionsWithoutScores(response.data.accuracy_pending_counts as Record<number, number>);
      setRubricPendingCounts(response.data.rubric_pending_counts);
    } catch (pendingError) {
      if (requestId && requestId !== pendingCountsRequestRef.current) return;
      setQuestionsWithoutAnswers(0);
      setQuestionsWithoutScores({});
      setRubricPendingCounts({});
      setError(getApiErrorMessage(pendingError, "Failed to load scoring pending counts."));
    }
  }, []);

  useEffect(() => {
    fetchSnapshots();
    fetchJudges();
    targetRubricApi.list(targetId).then((res) => {
      setRubrics(res.data);
    }).catch(() => {});
  }, [targetId, fetchJudges, fetchSnapshots]);

  useEffect(() => {
    setAnnotationStatus(null);
    setResults([]);
    setQuestionsWithoutAnswers(0);
    setQuestionsWithoutScores({});
    setSnapshotMetric(null);
    setRubricMetrics([]);
    setRubricPendingCounts({});
    setError(null);
    if (selectedSnapshotId) {
      const requestId = ++pendingCountsRequestRef.current;
      void Promise.allSettled([
        checkAnnotationCompletion(selectedSnapshotId, requestId),
        fetchScoringPendingCounts(selectedSnapshotId, requestId),
      ]);
    }
  }, [selectedSnapshotId, checkAnnotationCompletion, fetchScoringPendingCounts]);

  useEffect(() => {
    if (selectedSnapshotId && annotationStatus?.is_complete) {
      const requestId = ++snapshotMetricsRequestRef.current;
      void Promise.allSettled([
        fetchResults(selectedSnapshotId, requestId),
        fetchSnapshotMetrics(selectedSnapshotId, requestId),
        fetchRubricMetrics(selectedSnapshotId, requestId),
      ]);
    }
  }, [selectedSnapshotId, annotationStatus, fetchResults, fetchSnapshotMetrics, fetchRubricMetrics]);

  const handleSnapshotSelect = (snapshotId: number | null) => updateSnapshotSelection(snapshotId);

  const handleJobStart = async (judgeId: number): Promise<QAJob[] | null> => {
    if (!selectedSnapshotId) {
      setError("Select a snapshot to run judges.");
      return null;
    }
    try {
      const questionsResponse = await questionApi.listApprovedWithoutScores(selectedSnapshotId, judgeId);
      const questionIdsToScore = questionsResponse.data.map((question) => question.id);
      if (questionIdsToScore.length === 0) {
        setError("All questions already scored for this judge.");
        return null;
      }
      const response = await qaJobApi.start(selectedSnapshotId, { judge_id: judgeId, question_ids: questionIdsToScore });
      return response.data;
    } catch (jobError) {
      setError(getApiErrorMessage(jobError, "Unable to start judge run."));
      return null;
    }
  };

  const handleRubricJobStart = async (judgeId: number, rubricId: number): Promise<QAJob[] | null> => {
    if (!selectedSnapshotId) {
      setError("Select a snapshot to run judges.");
      return null;
    }
    if (!baselineJudge) {
      setError("Baseline judge not found.");
      return null;
    }
    try {
      const questionsResponse = await questionApi.listApprovedWithoutRubricScores(selectedSnapshotId, judgeId, rubricId);
      const questionIds = questionsResponse.data.map((question) => question.id);
      if (questionIds.length === 0) {
        setError("All questions already scored for this rubric judge.");
        return null;
      }
      const response = await qaJobApi.startAll(selectedSnapshotId, {
        judge_id: baselineJudge.id,
        question_ids: questionIds,
        rubric_specs: [{ rubric_id: rubricId, judge_id: judgeId }],
      });
      return response.data;
    } catch (jobError) {
      setError(getApiErrorMessage(jobError, "Unable to start rubric judge run."));
      return null;
    }
  };

  const handleJobComplete = useCallback(async () => {
    if (!selectedSnapshotId) return;
    const pendingRequestId = ++pendingCountsRequestRef.current;
    const metricsRequestId = ++snapshotMetricsRequestRef.current;
    await Promise.all([
      fetchResults(selectedSnapshotId, metricsRequestId),
      fetchScoringPendingCounts(selectedSnapshotId, pendingRequestId),
      fetchSnapshotMetrics(selectedSnapshotId, metricsRequestId),
      fetchRubricMetrics(selectedSnapshotId, metricsRequestId),
      fetchJudges(),
    ]);
  }, [
    selectedSnapshotId,
    fetchResults,
    fetchScoringPendingCounts,
    fetchSnapshotMetrics,
    fetchRubricMetrics,
    fetchJudges,
  ]);

  const openDialog = (
    mode: "create" | "edit" | "duplicate",
    config: DialogConfig,
    judge?: JudgeConfig
  ) => {
    setDialogMode(mode);
    setDialogConfig(config);
    setDialogJudge(judge || null);
    setDialogOpen(true);
  };

  const handleDeleteJudge = (judge: JudgeConfig) => {
    if (!judge.is_editable || judge.is_baseline) {
      setError("Cannot delete this judge.");
      return;
    }
    setJudgeToDelete(judge);
  };

  const handleLabelChange = useCallback(async () => {
    if (!selectedSnapshotId) return;
    const requestId = ++snapshotMetricsRequestRef.current;
    await Promise.all([
      fetchResults(selectedSnapshotId, requestId),
      fetchSnapshotMetrics(selectedSnapshotId, requestId),
    ]);
    setLabelOverrideCount((count) => count + 1);
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

  const metricSections = buildMetricSections({
    rubrics,
    snapshotMetric,
    rubricMetrics,
    accuracyJudges,
    getRubricJudgesForRubric,
    baselineJudge,
  });

  if (snapshotsLoading || judgesLoading) {
    return <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}><CircularProgress /></Box>;
  }

  return (
    <Box>
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
            <Button
              onClick={handleExportSnapshot}
              disabled={!selectedSnapshotId}
              sx={{
                bgcolor: "secondary.main",
                color: "white",
                borderRadius: 1,
                "&:hover": { bgcolor: "secondary.dark" },
                "&.Mui-disabled": { bgcolor: "action.disabledBackground", color: "action.disabled" },
              }}
              startIcon={<IconCode {...actionIconProps} />}
            >
              Export JSON
            </Button>
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
                const unannotatedIds = annotationStatus.selected_ids.filter((id) => !annotatedSet.has(id));
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
                              sx={{
                                color: "primary.main",
                                cursor: "pointer",
                                textDecoration: "underline",
                                "&:hover": { color: "primary.dark" },
                              }}
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

          <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
            <Tabs value={mainTab} onChange={(_, value) => setMainTab(value)}>
              <Tab label="Scores" />
              <Tab label="Error Analysis" />
            </Tabs>
          </Box>

          {mainTab === 0 && (
            <Stack spacing={2}>
              {metricSections.map((section) => (
                <MetricSection
                  key={section.key}
                  section={section}
                  snapshotId={selectedSnapshotId}
                  loading={section.rubric ? rubricMetricsLoading : snapshotMetricLoading}
                  labelOverrideCount={labelOverrideCount}
                  questionsWithoutScores={questionsWithoutScores}
                  questionsWithoutAnswers={questionsWithoutAnswers}
                  rubricPendingCounts={rubricPendingCounts}
                  onAccuracyJobStart={handleJobStart}
                  onRubricJobStart={handleRubricJobStart}
                  onJobComplete={handleJobComplete}
                  onAddJudge={(config) => openDialog("create", config)}
                  onEditJudge={(judge, config) => openDialog("edit", config, judge)}
                  onDuplicateJudge={(judge, config) => openDialog("duplicate", config, judge)}
                  onDeleteJudge={handleDeleteJudge}
                />
              ))}
            </Stack>
          )}

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
        category={dialogConfig.category}
        rubricId={dialogConfig.rubricId}
        mode={dialogMode}
        judge={dialogJudge}
        defaultPromptTemplate={dialogConfig.defaultPromptTemplate}
        lockedJudgeType={dialogConfig.judgeType}
        metricLabel={dialogConfig.metricLabel}
        onClose={() => {
          setDialogOpen(false);
          setDialogJudge(null);
        }}
        onSuccess={async () => {
          await fetchJudges();
          setDialogOpen(false);
          setDialogJudge(null);
        }}
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

function buildMetricSections({
  rubrics,
  snapshotMetric,
  rubricMetrics,
  accuracyJudges,
  getRubricJudgesForRubric,
  baselineJudge,
}: {
  rubrics: TargetRubricResponse[];
  snapshotMetric: SnapshotMetric | null;
  rubricMetrics: SnapshotMetric[];
  accuracyJudges: JudgeConfig[];
  getRubricJudgesForRubric: (rubric: TargetRubricResponse) => JudgeConfig[];
  baselineJudge: JudgeConfig | null;
}): MetricSectionConfig[] {
  const presetRubrics = rubrics.filter((rubric) => !!rubric.template_key);
  const customRubrics = rubrics.filter((rubric) => !rubric.template_key);

  const sections: MetricSectionConfig[] = [
    {
      key: "accuracy",
      title: "Accuracy",
      description: "Hallucination and claim-support evaluation for generated responses.",
      sourceGroup: "fixed",
      category: "accuracy",
      judgeType: "claim_based",
      rubric: null,
      metric: snapshotMetric,
      judges: accuracyJudges,
      emptyMessage: "Run judges to see results",
      gaugeLabel: "Share rated accurate",
      defaultPromptTemplate: baselineJudge?.prompt_template || accuracyJudges[0]?.prompt_template || "",
    },
  ];

  for (const rubric of presetRubrics) {
    const sectionJudges = getRubricJudgesForRubric(rubric);
    sections.push({
      key: `rubric-${rubric.id}`,
      title: rubric.name,
      description: rubric.best_option
        ? `Ideal outcome: ${rubric.best_option}`
        : "Preset rubric evaluation",
      sourceGroup: "preset",
      category: rubric.category,
      judgeType: "response_level",
      rubric,
      metric: rubricMetrics.find((metric) => metric.rubric_id === rubric.id) ?? null,
      judges: sectionJudges,
      emptyMessage: "Run judges to see results",
      gaugeLabel: `Share choosing ${rubric.best_option || rubric.options?.[0]?.option || "Positive"}`,
      defaultPromptTemplate: sectionJudges[0]?.prompt_template || "",
    });
  }

  for (const rubric of customRubrics) {
    const sectionJudges = getRubricJudgesForRubric(rubric);
    sections.push({
      key: `rubric-${rubric.id}`,
      title: rubric.name,
      description: rubric.best_option
        ? `Ideal outcome: ${rubric.best_option}`
        : "Custom rubric evaluation",
      sourceGroup: "custom",
      category: rubric.category,
      judgeType: "response_level",
      rubric,
      metric: rubricMetrics.find((metric) => metric.rubric_id === rubric.id) ?? null,
      judges: sectionJudges,
      emptyMessage: "Run judges to see results",
      gaugeLabel: `Share choosing ${rubric.best_option || rubric.options?.[0]?.option || "Positive"}`,
      defaultPromptTemplate: sectionJudges[0]?.prompt_template || "",
    });
  }

  return sections;
}

function MetricSection({
  section,
  snapshotId,
  loading,
  labelOverrideCount,
  questionsWithoutScores,
  questionsWithoutAnswers,
  rubricPendingCounts,
  onAccuracyJobStart,
  onRubricJobStart,
  onJobComplete,
  onAddJudge,
  onEditJudge,
  onDuplicateJudge,
  onDeleteJudge,
}: {
  section: MetricSectionConfig;
  snapshotId: number;
  loading: boolean;
  labelOverrideCount: number;
  questionsWithoutScores: Record<number, number>;
  questionsWithoutAnswers: number;
  rubricPendingCounts: Record<string, number>;
  onAccuracyJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onRubricJobStart: (judgeId: number, rubricId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onAddJudge: (config: DialogConfig) => void;
  onEditJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
}) {
  const sectionColor = groupColors[section.sourceGroup];
  const dialogConfig: DialogConfig = {
    category: section.category,
    rubricId: section.rubric && !section.rubric.template_key ? section.rubric.id : null,
    judgeType: section.judgeType,
    metricLabel: section.title,
    defaultPromptTemplate: section.defaultPromptTemplate,
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        borderLeft: "4px solid",
        borderColor: sectionColor.border,
        bgcolor: "white",
        p: 2,
      }}
    >
      <Stack spacing={2}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "flex-start", sm: "center" }}
          spacing={1.5}
        >
          <Stack spacing={0.5}>
            <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap">
              <Typography variant="h6" fontWeight={700}>
                {section.title}
              </Typography>
              <Chip
                label={section.sourceGroup === "fixed" ? "Fixed" : section.sourceGroup === "preset" ? "Preset" : "Custom"}
                size="small"
                variant="outlined"
                sx={{
                  borderColor: sectionColor.border,
                  color: sectionColor.border,
                  bgcolor: "white",
                  fontWeight: 600,
                }}
              />
            </Stack>
            <Typography variant="body2" color="text.secondary">
              {section.description}
            </Typography>
          </Stack>

          <Tooltip title={`Add judge for ${section.title}`}>
            <IconButton
              size="small"
              onClick={() => onAddJudge(dialogConfig)}
              sx={{
                border: "1px solid",
                borderColor: sectionColor.border,
                color: sectionColor.border,
                bgcolor: "white",
                "&:hover": {
                  bgcolor: sectionColor.border,
                  color: "#fff",
                },
              }}
            >
              <IconPlus {...compactActionIconProps} />
            </IconButton>
          </Tooltip>
        </Stack>

        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", xl: "280px minmax(0, 1fr)" },
            alignItems: "start",
          }}
        >
          <MetricSummaryTile
            title={section.title}
            metric={section.metric}
            loading={loading}
            emptyMessage={section.emptyMessage}
            gaugeLabel={section.gaugeLabel}
          />

          <Stack spacing={2}>
            {section.judges.length > 0 ? (
              <JudgeStrip
                judges={section.judges}
                section={section}
                snapshotId={snapshotId}
                labelOverrideCount={labelOverrideCount}
                questionsWithoutScores={questionsWithoutScores}
                questionsWithoutAnswers={questionsWithoutAnswers}
                rubricPendingCounts={rubricPendingCounts}
                onAccuracyJobStart={onAccuracyJobStart}
                onRubricJobStart={onRubricJobStart}
                onJobComplete={onJobComplete}
                onEditJudge={onEditJudge}
                onDuplicateJudge={onDuplicateJudge}
                onDeleteJudge={onDeleteJudge}
                dialogConfig={dialogConfig}
              />
            ) : (
              <Paper variant="outlined" sx={{ bgcolor: "white", p: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  No judges configured for this metric.
                </Typography>
              </Paper>
            )}
          </Stack>
        </Box>
      </Stack>
    </Paper>
  );
}

function JudgeStrip({
  judges,
  section,
  snapshotId,
  labelOverrideCount,
  questionsWithoutScores,
  questionsWithoutAnswers,
  rubricPendingCounts,
  onAccuracyJobStart,
  onRubricJobStart,
  onJobComplete,
  onEditJudge,
  onDuplicateJudge,
  onDeleteJudge,
  dialogConfig,
}: {
  judges: JudgeConfig[];
  section: MetricSectionConfig;
  snapshotId: number;
  labelOverrideCount: number;
  questionsWithoutScores: Record<number, number>;
  questionsWithoutAnswers: number;
  rubricPendingCounts: Record<string, number>;
  onAccuracyJobStart: (judgeId: number) => Promise<QAJob[] | null>;
  onRubricJobStart: (judgeId: number, rubricId: number) => Promise<QAJob[] | null>;
  onJobComplete: () => void;
  onEditJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
  dialogConfig: DialogConfig;
}) {
  return (
    <Box
      sx={{
        bgcolor: "grey.100",
        borderRadius: 1.5,
        px: 1.5,
        py: 1.5,
      }}
    >
      <Box
        sx={{
          display: "flex",
          gap: 2,
          overflowX: "auto",
          pb: 1,
          scrollSnapType: "x proximity",
        }}
      >
        {judges.map((judge, index) => {
          const startsCustomGroup = judge.is_editable && !judges[index - 1]?.is_editable;

          return (
            <Box
              key={judge.id}
              sx={{
                flex: {
                  xs: "0 0 85%",
                  sm: "0 0 60%",
                  md: "0 0 38%",
                  lg: "0 0 30%",
                },
                minWidth: 0,
                ml: startsCustomGroup ? 1 : 0,
                scrollSnapAlign: "start",
              }}
            >
              {section.rubric ? (
                <RubricJudgeCard
                  judge={judge}
                  displayName={judge.name}
                  snapshotId={snapshotId}
                  rubricId={section.rubric.id}
                  pendingCount={rubricPendingCounts[`${judge.id}:${section.rubric.id}`] ?? null}
                  bestOption={section.rubric.best_option || section.rubric.options?.[0]?.option || ""}
                  hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                  onJobStart={(judgeId) => onRubricJobStart(judgeId, section.rubric!.id)}
                  onJobComplete={onJobComplete}
                  onEdit={() => onEditJudge(judge, dialogConfig)}
                  onDuplicate={() => onDuplicateJudge(judge, {
                    ...dialogConfig,
                    rubricId: judge.rubric_id ?? dialogConfig.rubricId,
                  })}
                  onDelete={() => onDeleteJudge(judge)}
                  cardSx={{ width: "100%", height: "100%" }}
                />
              ) : (
                <JudgeCard
                  judge={judge}
                  displayName={judge.name}
                  snapshotId={snapshotId}
                  questionsWithoutScores={questionsWithoutScores[judge.id] || 0}
                  hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                  onJobStart={onAccuracyJobStart}
                  onJobComplete={onJobComplete}
                  onEdit={() => onEditJudge(judge, dialogConfig)}
                  onDuplicate={() => onDuplicateJudge(judge, {
                    ...dialogConfig,
                    rubricId: judge.rubric_id ?? dialogConfig.rubricId,
                  })}
                  onDelete={() => onDeleteJudge(judge)}
                  labelOverrideCount={labelOverrideCount}
                  cardSx={{ width: "100%", height: "100%" }}
                />
              )}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

function MetricSummaryTile({
  title,
  metric,
  loading,
  emptyMessage,
  gaugeLabel,
}: {
  title: string;
  metric: SnapshotMetric | null;
  loading: boolean;
  emptyMessage: string;
  gaugeLabel: string;
}) {
  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 180 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!metric || metric.total_answers === 0) {
    return (
      <Stack spacing={1} alignItems="center" textAlign="center">
        <Typography variant="subtitle1" fontWeight={700}>
          {title}
        </Typography>
        <Typography variant="h3" fontWeight={700} color="text.disabled">
          --%
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Stack>
    );
  }

  const hasReliableJudges = metric.aligned_judges.length > 0;
  const reliableJudgeCount = metric.aligned_judges.length;
  const alignmentRange = metric.judge_alignment_range;

  return (
    <Stack spacing={1.5} alignItems="center" textAlign="center">
      <Typography variant="subtitle1" fontWeight={700}>
        {title}
      </Typography>

      <AccuracyGauge
        value={hasReliableJudges ? metric.aggregated_accuracy : null}
        size={220}
        label={gaugeLabel}
      />

      {hasReliableJudges && alignmentRange ? (
        <Typography variant="body2" color="text.secondary">
          {reliableJudgeCount} reliable judge{reliableJudgeCount !== 1 ? "s" : ""} ({(alignmentRange.min * 100).toFixed(0)}%-{(alignmentRange.max * 100).toFixed(0)}% reliability)
        </Typography>
      ) : (
        <Typography variant="body2" color="warning.dark" fontWeight={600}>
          Score withheld until at least one reliable judge is available
        </Typography>
      )}
    </Stack>
  );
}
