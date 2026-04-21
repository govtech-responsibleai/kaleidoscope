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
  MetricScoringContract,
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
import { actionIconProps, compactActionIconProps } from "@/lib/iconStyles";
import { groupColors } from "@/lib/theme";
import { sortJudges } from "@/lib/judgeOrdering";

type SourceGroup = "fixed" | "preset" | "custom";

interface MetricSectionConfig {
  key: string;
  title: string;
  sourceGroup: SourceGroup;
  rubric: TargetRubricResponse | null;
  contract: MetricScoringContract | null;
  metric: SnapshotMetric | null;
  judges: JudgeConfig[];
  emptyMessage: string;
  gaugeLabel: string;
  defaultPromptTemplate: string;
}

interface DialogConfig {
  rubricId: number | null;
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
    rubricId: null,
    metricLabel: "Accuracy",
    defaultPromptTemplate: "",
  });
  const [judgeToDelete, setJudgeToDelete] = useState<JudgeConfig | null>(null);

  const [annotationStatus, setAnnotationStatus] = useState<AnnotationCompletionStatus | null>(null);
  const [checkingAnnotations, setCheckingAnnotations] = useState(true);

  const [questionsWithoutAnswers, setQuestionsWithoutAnswers] = useState<number>(0);
  const [questionsWithoutScores, setQuestionsWithoutScores] = useState<Record<number, number>>({});

  const [snapshotMetric, setSnapshotMetric] = useState<SnapshotMetric | null>(null);
  const [snapshotMetricLoading, setSnapshotMetricLoading] = useState(false);

  const [rubricMetrics, setRubricMetrics] = useState<SnapshotMetric[]>([]);
  const [rubricMetricsLoading, setRubricMetricsLoading] = useState(false);
  const [scoringContracts, setScoringContracts] = useState<MetricScoringContract[]>([]);
  const [rubricPendingCounts, setRubricPendingCounts] = useState<Record<string, number>>({});

  const [labelOverrideCount, setLabelOverrideCount] = useState(0);

  const [error, setError] = useState<string | null>(null);
  const [activeMetricTab, setActiveMetricTab] = useState(0);
  const pendingCountsRequestRef = useRef(0);
  const snapshotMetricsRequestRef = useRef(0);

  const fixedRubric = rubrics.find((r) => r.group === "fixed") ?? null;
  const accuracyJudges = sortJudges(
    judges.filter((judge) => judge.rubric_id === fixedRubric?.id)
  );
  const baselineJudge = accuracyJudges.find((judge) => judge.is_baseline) ?? null;

  const getRubricJudgesForRubric = useCallback((rubric: TargetRubricResponse) => {
    return sortJudges(
      judges.filter((judge) => judge.rubric_id === rubric.id)
    );
  }, [judges]);

  const fetchJudgesForRubrics = useCallback(async (currentRubrics: TargetRubricResponse[]) => {
    setJudgesLoading(true);
    try {
      if (currentRubrics.length === 0) {
        setJudges([]);
        return;
      }
      const responses = await Promise.all(
        currentRubrics.map((rubric) => judgeApi.getForRubric(rubric.id, targetId))
      );
      const deduped = new Map<number, JudgeConfig>();
      responses.forEach((response) => {
        response.data.forEach((judge) => {
          deduped.set(judge.id, judge);
        });
      });
      setJudges(sortJudges(Array.from(deduped.values())));
    } catch (judgeError) {
      setError(getApiErrorMessage(judgeError, "Failed to load judges."));
    } finally {
      setJudgesLoading(false);
    }
  }, [targetId]);

  const applyScoringContracts = useCallback((contracts: MetricScoringContract[]) => {
    setScoringContracts(contracts);
    const accuracyContract = contracts.find((contract) => contract.group === "fixed") ?? null;
    const rubricContracts = contracts.filter((contract) => contract.group !== "fixed");

    setSnapshotMetric(
      accuracyContract ? {
        snapshot_id: accuracyContract.snapshot_id ?? selectedSnapshotId ?? 0,
        snapshot_name: accuracyContract.snapshot_name ?? null,
        created_at: accuracyContract.created_at ?? null,
        rubric_id: accuracyContract.rubric_id ?? null,
        rubric_name: accuracyContract.rubric_name ?? null,
        aggregated_accuracy: accuracyContract.aggregated_accuracy,
        total_answers: accuracyContract.total_answers,
        accurate_count: accuracyContract.accurate_count,
        inaccurate_count: accuracyContract.inaccurate_count,
        pending_count: accuracyContract.pending_count,
        edited_count: accuracyContract.edited_count,
        judge_alignment_range: accuracyContract.judge_alignment_range,
        aligned_judges: accuracyContract.aligned_judges,
      } : null
    );

    setRubricMetrics(rubricContracts.map((contract) => ({
      snapshot_id: contract.snapshot_id ?? selectedSnapshotId ?? 0,
      snapshot_name: contract.snapshot_name ?? null,
      created_at: contract.created_at ?? null,
      rubric_id: contract.rubric_id ?? null,
      rubric_name: contract.rubric_name ?? null,
      aggregated_accuracy: contract.aggregated_accuracy,
      total_answers: contract.total_answers,
      accurate_count: contract.accurate_count,
      inaccurate_count: contract.inaccurate_count,
      pending_count: contract.pending_count,
      edited_count: contract.edited_count,
      judge_alignment_range: contract.judge_alignment_range,
      aligned_judges: contract.aligned_judges,
    })));

  }, [selectedSnapshotId]);

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

  const fetchScoringContracts = useCallback(async (snapshotId: number, requestId?: number) => {
    setSnapshotMetricLoading(true);
    setRubricMetricsLoading(true);
    try {
      const response = await metricsApi.getScoringContracts(snapshotId);
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      applyScoringContracts(response.data.metrics ?? []);
    } catch (contractError) {
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      setScoringContracts([]);
      setSnapshotMetric(null);
      setRubricMetrics([]);
      setError(getApiErrorMessage(contractError, "Failed to load scoring data."));
    } finally {
      if (!requestId || requestId === snapshotMetricsRequestRef.current) {
        setSnapshotMetricLoading(false);
        setRubricMetricsLoading(false);
      }
    }
  }, [applyScoringContracts]);

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
    targetRubricApi.list(targetId).then((res) => {
      setRubrics(res.data);
      void fetchJudgesForRubrics(res.data);
    }).catch((rubricError) => {
      setRubrics([]);
      setJudges([]);
      setJudgesLoading(false);
      setError(getApiErrorMessage(rubricError, "Failed to load rubrics."));
    });
  }, [targetId, fetchJudgesForRubrics, fetchSnapshots]);

  useEffect(() => {
    setAnnotationStatus(null);
    setQuestionsWithoutAnswers(0);
    setQuestionsWithoutScores({});
    setScoringContracts([]);
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
      void fetchScoringContracts(selectedSnapshotId, requestId);
    }
  }, [selectedSnapshotId, annotationStatus, fetchScoringContracts]);

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
      fetchScoringPendingCounts(selectedSnapshotId, pendingRequestId),
      fetchScoringContracts(selectedSnapshotId, metricsRequestId),
      fetchJudgesForRubrics(rubrics),
    ]);
  }, [
    selectedSnapshotId,
    fetchScoringPendingCounts,
    fetchScoringContracts,
    fetchJudgesForRubrics,
    rubrics,
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
    await fetchScoringContracts(selectedSnapshotId, requestId);
    setLabelOverrideCount((count) => count + 1);
  }, [selectedSnapshotId, fetchScoringContracts]);

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
    scoringContracts,
    snapshotMetric,
    rubricMetrics,
    accuracyJudges,
    getRubricJudgesForRubric,
    baselineJudge,
  });
  const activeMetricSection = metricSections[activeMetricTab] ?? metricSections[0] ?? null;

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
            <Tabs value={activeMetricTab} onChange={(_, value) => setActiveMetricTab(value)}>
              {metricSections.map((section, index) => (
                <Tab
                  key={section.key}
                  label={section.title}
                  value={index}
                  sx={{
                    textTransform: "none",
                    fontWeight: 600,
                    color: groupColors[section.sourceGroup].border,
                    "&.Mui-selected": {
                      color: groupColors[section.sourceGroup].border,
                      fontWeight: 700,
                    },
                  }}
                />
              ))}
            </Tabs>
          </Box>

          {activeMetricSection && (
            <Stack spacing={2}>
              <MetricSection
                section={activeMetricSection}
                snapshotId={selectedSnapshotId}
                loading={activeMetricSection.rubric ? rubricMetricsLoading : snapshotMetricLoading}
                labelOverrideCount={labelOverrideCount}
                questionsWithoutScores={questionsWithoutScores}
                questionsWithoutAnswers={questionsWithoutAnswers}
                rubricPendingCounts={rubricPendingCounts}
                onAccuracyJobStart={handleJobStart}
                onRubricJobStart={handleRubricJobStart}
                onJobComplete={handleJobComplete}
                onEditJudge={(judge, config) => openDialog("edit", config, judge)}
                onDuplicateJudge={(judge, config) => openDialog("duplicate", config, judge)}
                onDeleteJudge={handleDeleteJudge}
                onAddJudge={(config) => openDialog("create", config)}
              />

              <ResultsTable
                results={mapContractRowsToResults(activeMetricSection.contract)}
                contract={activeMetricSection.contract}
                targetId={targetId}
                snapshotId={selectedSnapshotId}
                judges={activeMetricSection.judges}
                rubrics={activeMetricSection.rubric ? [activeMetricSection.rubric] : []}
                onLabelChange={handleLabelChange}
              />
            </Stack>
          )}
        </Stack>
      )}

      <CreateJudgeDialog
        open={dialogOpen}
        targetId={targetId}
        rubricId={dialogConfig.rubricId}
        mode={dialogMode}
        judge={dialogJudge}
        defaultPromptTemplate={dialogConfig.defaultPromptTemplate}
        metricLabel={dialogConfig.metricLabel}
        onClose={() => {
          setDialogOpen(false);
          setDialogJudge(null);
        }}
        onSuccess={async () => {
          await fetchJudgesForRubrics(rubrics);
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
          await fetchJudgesForRubrics(rubrics);
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
  scoringContracts,
  snapshotMetric,
  rubricMetrics,
  accuracyJudges,
  getRubricJudgesForRubric,
  baselineJudge,
}: {
  rubrics: TargetRubricResponse[];
  scoringContracts: MetricScoringContract[];
  snapshotMetric: SnapshotMetric | null;
  rubricMetrics: SnapshotMetric[];
  accuracyJudges: JudgeConfig[];
  getRubricJudgesForRubric: (rubric: TargetRubricResponse) => JudgeConfig[];
  baselineJudge: JudgeConfig | null;
}): MetricSectionConfig[] {
  const sections: MetricSectionConfig[] = [];
  const orderedRubrics = [
    ...rubrics.filter((rubric) => rubric.group === "fixed"),
    ...rubrics.filter((rubric) => rubric.group === "preset"),
    ...rubrics.filter((rubric) => rubric.group === "custom"),
  ];

  for (const rubric of orderedRubrics) {
    const sectionJudges = getRubricJudgesForRubric(rubric);
    const contract = scoringContracts.find((metric) => metric.rubric_id === rubric.id) ?? null;
    sections.push({
      key: `rubric-${rubric.id}`,
      title: rubric.name,
      sourceGroup: rubric.group,
      rubric,
      contract,
      metric: rubric.group === "fixed"
        ? snapshotMetric
        : rubricMetrics.find((metric) => metric.rubric_id === rubric.id) ?? null,
      judges: rubric.group === "fixed" ? accuracyJudges : sectionJudges,
      emptyMessage: "Run judges to see results",
      gaugeLabel: `Share labeled ${contract?.target_label || rubric.best_option || rubric.options?.[0]?.option || rubric.name}`,
      defaultPromptTemplate:
        rubric.group === "fixed"
          ? baselineJudge?.prompt_template || accuracyJudges[0]?.prompt_template || ""
          : sectionJudges[0]?.prompt_template || "",
    });
  }

  return sections;
}

function mapContractRowsToResults(contract: MetricScoringContract | null): ResultRow[] {
  if (!contract) {
    return [];
  }

  return contract.rows.map((row) => ({
    question_id: row.question_id,
    question_text: row.question_text,
    question_type: row.question_type,
    question_scope: row.question_scope,
    answer_id: row.answer_id,
    answer_content: row.answer_content,
    aggregated_accuracy: {
      answer_id: row.answer_id,
      method: row.aggregated_result.method,
      label: row.aggregated_result.value ?? null,
      is_edited: row.aggregated_result.is_edited,
      metadata: row.judge_results.map((judgeResult) => {
        return `- ${judgeResult.name}: ${judgeResult.value ?? "Pending"}`;
      }),
    },
    human_label: row.human_label ?? null,
    human_notes: null,
  }));
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
  onEditJudge,
  onDuplicateJudge,
  onDeleteJudge,
  onAddJudge,
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
  onEditJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
  onAddJudge: (config: DialogConfig) => void;
}) {
  const sectionColor = groupColors[section.sourceGroup];
  const dialogConfig: DialogConfig = {
    rubricId: section.rubric?.id ?? null,
    metricLabel: section.title,
    defaultPromptTemplate: section.defaultPromptTemplate,
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        borderColor: "divider",
        bgcolor: "background.paper",
        p: 2,
      }}
    >
      <Stack spacing={2}>
        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", xl: "280px minmax(0, 1fr)" },
            alignItems: "center",
          }}
        >
          <Box sx={{ display: "flex", justifyContent: "center", alignSelf: "center" }}>
            <MetricSummaryTile
              metric={section.metric}
              loading={loading}
              emptyMessage={section.emptyMessage}
              gaugeLabel={section.gaugeLabel}
            />
          </Box>

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
            onAddJudge={onAddJudge}
            dialogConfig={dialogConfig}
          />
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
  onAddJudge,
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
  onAddJudge: (config: DialogConfig) => void;
  dialogConfig: DialogConfig;
}) {
  const sectionColor = groupColors[section.sourceGroup];
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
          alignItems: "center",
          justifyContent: "space-between",
          gap: 2,
          mb: 1.5,
        }}
      >
        <Typography variant="subtitle2" fontWeight={700} color="text.primary">
          Judge List
        </Typography>
        <Tooltip title={`Add judge for ${section.title}`}>
          <IconButton
            size="small"
            onClick={() => onAddJudge(dialogConfig)}
            sx={{
              border: "1px solid",
              borderColor: sectionColor.border,
              color: sectionColor.border,
              bgcolor: "background.paper",
              "&:hover": {
                bgcolor: sectionColor.border,
                color: "#fff",
              },
            }}
          >
            <IconPlus {...compactActionIconProps} />
          </IconButton>
        </Tooltip>
      </Box>

      <Box
        sx={{
          display: "flex",
          gap: 2,
          overflowX: "auto",
          pb: 1,
          scrollSnapType: "x proximity",
          alignItems: "stretch",
          justifyContent: "flex-start",
        }}
      >
        {judges.map((judge, index) => {
          const startsCustomGroup = judge.is_editable && !judges[index - 1]?.is_editable;
          const judgeSummary = section.contract?.judge_summaries.find((summary) => summary.judge_id === judge.id);

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
              {section.rubric && section.rubric.group !== "fixed" ? (
                <RubricJudgeCard
                  judge={judge}
                  displayName={judge.name}
                  summary={judgeSummary}
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
                  summary={judgeSummary}
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
  metric,
  loading,
  emptyMessage,
  gaugeLabel,
}: {
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
