"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  IconDownload,
  IconPlus,
} from "@tabler/icons-react";
import { orderRubricsForDisplay } from "@/app/targets/[id]/rubrics";
import { tabSx, tabsSx } from "@/lib/styles";
import ScoreGauge from "@/components/shared/AccuracyGauge";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import JudgeCard from "@/components/scoring/JudgeCard";
import CreateJudgeDialog from "@/components/scoring/CreateJudgeDialog";
import ResultsTable from "@/components/scoring/ResultsTable";
import {
  Snapshot,
  JudgeConfig,
  AnnotationCompletionStatus,
  QAJob,
  ScoringContract,
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
  targetApi,
  targetRubricApi,
  getApiErrorMessage,
} from "@/lib/api";
import { actionIconProps, compactActionIconProps } from "@/lib/styles";
import { groupColors } from "@/lib/theme";
import { usePageActivity } from "@/hooks/useVisibilityPolling";

type SourceGroup = "fixed" | "preset" | "custom";

interface MetricSectionConfig {
  key: string;
  title: string;
  sourceGroup: SourceGroup;
  rubric: TargetRubricResponse | null;
  contract: ScoringContract | null;
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
    metricLabel: "Score",
    defaultPromptTemplate: "",
  });
  const [judgeToDelete, setJudgeToDelete] = useState<JudgeConfig | null>(null);

  const [annotationStatus, setAnnotationStatus] = useState<AnnotationCompletionStatus | null>(null);
  const [checkingAnnotations, setCheckingAnnotations] = useState(true);

  const [questionsWithoutAnswers, setQuestionsWithoutAnswers] = useState<number>(0);
  const [pendingCountsByRubricId, setPendingCountsByRubricId] = useState<Record<number, Record<number, number>>>({});
  const [metricsByRubricId, setMetricsByRubricId] = useState<Record<number, SnapshotMetric>>({});
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [scoringContracts, setScoringContracts] = useState<ScoringContract[]>([]);

  const [error, setError] = useState<string | null>(null);
  const [activeMetricTab, setActiveMetricTab] = useState(0);
  const pendingCountsRequestRef = useRef(0);
  const snapshotMetricsRequestRef = useRef(0);
  const isPageActive = usePageActivity();
  const wasPageActiveRef = useRef(isPageActive);

  const orderedRubrics = useMemo(() => orderRubricsForDisplay(rubrics), [rubrics]);
  const activeRubricId = orderedRubrics[activeMetricTab]?.id ?? null;

  const getJudges = useCallback((rubricId: number | null | undefined) => {
    if (rubricId == null) {
      return [];
    }
    return judges.filter((judge) => judge.rubric_id === rubricId);
  }, [judges]);

  const getBaselineJudge = useCallback((rubricId: number | null | undefined) => (
    getJudges(rubricId).find((judge) => judge.is_baseline) ?? null
  ), [getJudges]);

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
      setJudges(Array.from(deduped.values()));
    } catch (judgeError) {
      setError(getApiErrorMessage(judgeError, "Failed to load judges."));
    } finally {
      setJudgesLoading(false);
    }
  }, [targetId]);

  const applyScoringContracts = useCallback((contracts: ScoringContract[]) => {
    setScoringContracts(contracts);
    setMetricsByRubricId(Object.fromEntries(
      contracts.map((contract) => [contract.rubric_id, {
        snapshot_id: contract.snapshot_id ?? selectedSnapshotId ?? 0,
        snapshot_name: contract.snapshot_name ?? null,
        created_at: contract.created_at ?? null,
        rubric_id: contract.rubric_id ?? null,
        rubric_name: contract.rubric_name ?? null,
        aggregated_score: contract.aggregated_score,
        total_answers: contract.total_answers,
        accurate_count: contract.accurate_count,
        inaccurate_count: contract.inaccurate_count,
        pending_count: contract.pending_count,
        edited_count: contract.edited_count,
        judge_alignment_range: contract.judge_alignment_range,
        aligned_judges: contract.aligned_judges,
      } satisfies SnapshotMetric])
    ));
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
    setMetricsLoading(true);
    try {
      const response = await metricsApi.getScoringContracts(snapshotId);
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      applyScoringContracts(response.data.rubrics ?? []);
    } catch (contractError) {
      if (requestId && requestId !== snapshotMetricsRequestRef.current) return;
      setScoringContracts([]);
      setMetricsByRubricId({});
      setError(getApiErrorMessage(contractError, "Failed to load scoring data."));
    } finally {
      if (!requestId || requestId === snapshotMetricsRequestRef.current) {
        setMetricsLoading(false);
      }
    }
  }, [applyScoringContracts]);

  const fetchScoringPendingCounts = useCallback(async (
    snapshotId: number,
    currentRubrics: TargetRubricResponse[],
    requestId?: number,
  ) => {
    try {
      if (currentRubrics.length === 0) {
        setQuestionsWithoutAnswers(0);
        setPendingCountsByRubricId({});
        return;
      }

      const responses = await Promise.all(
        currentRubrics.map((rubric) => metricsApi.getScoringPendingCounts(snapshotId, rubric.id))
      );
      if (requestId && requestId !== pendingCountsRequestRef.current) return;

      const unansweredQuestionCount = responses[0]?.data.unanswered_question_count ?? 0;
      const nextPendingCountsByRubricId = Object.fromEntries(
        responses.map(({ data }) => [
          data.rubric_id,
          Object.fromEntries(
            Object.entries(data.pending_counts).map(([judgeId, pendingCount]) => [Number(judgeId), pendingCount])
          ),
        ])
      );

      setQuestionsWithoutAnswers(unansweredQuestionCount);
      setPendingCountsByRubricId(nextPendingCountsByRubricId);
    } catch (pendingError) {
      if (requestId && requestId !== pendingCountsRequestRef.current) return;
      setQuestionsWithoutAnswers(0);
      setPendingCountsByRubricId({});
      setError(getApiErrorMessage(pendingError, "Failed to load scoring pending counts."));
    }
  }, []);

  const fetchScoringPendingCountsForRubric = useCallback(async (
    snapshotId: number,
    rubricId: number,
    requestId?: number,
  ) => {
    try {
      const response = await metricsApi.getScoringPendingCounts(snapshotId, rubricId);
      if (requestId && requestId !== pendingCountsRequestRef.current) return;

      const nextPendingCounts = Object.fromEntries(
        Object.entries(response.data.pending_counts).map(([judgeId, pendingCount]) => [Number(judgeId), pendingCount])
      );

      setQuestionsWithoutAnswers(response.data.unanswered_question_count ?? 0);
      setPendingCountsByRubricId((current) => ({
        ...current,
        [rubricId]: nextPendingCounts,
      }));
    } catch (pendingError) {
      if (requestId && requestId !== pendingCountsRequestRef.current) return;
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
    setScoringContracts([]);
    setMetricsByRubricId({});
    setPendingCountsByRubricId({});
    setError(null);
    if (selectedSnapshotId && rubrics.length > 0) {
      const requestId = ++pendingCountsRequestRef.current;
      void Promise.allSettled([
        checkAnnotationCompletion(selectedSnapshotId, requestId),
        fetchScoringPendingCounts(selectedSnapshotId, rubrics, requestId),
      ]);
    }
  }, [selectedSnapshotId, rubrics, checkAnnotationCompletion, fetchScoringPendingCounts]);

  useEffect(() => {
    if (selectedSnapshotId && annotationStatus?.is_complete) {
      const requestId = ++snapshotMetricsRequestRef.current;
      void fetchScoringContracts(selectedSnapshotId, requestId);
    }
  }, [selectedSnapshotId, annotationStatus, fetchScoringContracts]);

  useEffect(() => {
    const becameActive = isPageActive && !wasPageActiveRef.current;
    wasPageActiveRef.current = isPageActive;

    if (!becameActive || !selectedSnapshotId || rubrics.length === 0) {
      return;
    }

    const pendingRequestId = ++pendingCountsRequestRef.current;
    void Promise.allSettled([
      checkAnnotationCompletion(selectedSnapshotId, pendingRequestId),
      fetchScoringPendingCounts(selectedSnapshotId, rubrics, pendingRequestId),
    ]);

    if (annotationStatus?.is_complete) {
      const metricsRequestId = ++snapshotMetricsRequestRef.current;
      void fetchScoringContracts(selectedSnapshotId, metricsRequestId);
    }
  }, [
    annotationStatus,
    checkAnnotationCompletion,
    fetchScoringContracts,
    fetchScoringPendingCounts,
    isPageActive,
    rubrics,
    selectedSnapshotId,
  ]);

  useEffect(() => {
    if (!selectedSnapshotId || activeRubricId == null) {
      return;
    }

    const pendingRequestId = ++pendingCountsRequestRef.current;
    void fetchScoringPendingCountsForRubric(selectedSnapshotId, activeRubricId, pendingRequestId);

    if (annotationStatus?.is_complete) {
      const metricsRequestId = ++snapshotMetricsRequestRef.current;
      void fetchScoringContracts(selectedSnapshotId, metricsRequestId);
    }
  }, [
    activeMetricTab,
    annotationStatus,
    fetchScoringContracts,
    fetchScoringPendingCountsForRubric,
    selectedSnapshotId,
    activeRubricId,
  ]);

  const handleSnapshotSelect = (snapshotId: number | null) => updateSnapshotSelection(snapshotId);

  const handleJobStart = async (judgeId: number, rubricId: number): Promise<QAJob[] | null> => {
    if (!selectedSnapshotId) {
      setError("Select a snapshot to run judges.");
      return null;
    }
    try {
      const questionsResponse = await questionApi.listApprovedWithoutScores(selectedSnapshotId, judgeId, rubricId);
      const questionIdsToScore = questionsResponse.data.map((question) => question.id);
      if (questionIdsToScore.length === 0) {
        setError("All questions already scored for this judge.");
        return null;
      }
      const rubricSpecResponse = await targetApi.getRubricSpec(targetId, rubricId, judgeId);
      const response = await qaJobApi.start(selectedSnapshotId, {
        question_ids: questionIdsToScore,
        rubric_specs: [rubricSpecResponse.data],
      });
      const pendingRequestId = ++pendingCountsRequestRef.current;
      const metricsRequestId = ++snapshotMetricsRequestRef.current;
      void Promise.all([
        fetchScoringPendingCountsForRubric(selectedSnapshotId, rubricId, pendingRequestId),
        fetchScoringContracts(selectedSnapshotId, metricsRequestId),
      ]);
      return response.data;
    } catch (jobError) {
      setError(getApiErrorMessage(jobError, "Unable to start judge run."));
      return null;
    }
  };

  const handleJobComplete = useCallback(async (rubricId: number) => {
    if (!selectedSnapshotId) return;
    const pendingRequestId = ++pendingCountsRequestRef.current;
    const metricsRequestId = ++snapshotMetricsRequestRef.current;
    await Promise.all([
      fetchScoringPendingCountsForRubric(selectedSnapshotId, rubricId, pendingRequestId),
      fetchScoringContracts(selectedSnapshotId, metricsRequestId),
    ]);
  }, [
    selectedSnapshotId,
    fetchScoringPendingCountsForRubric,
    fetchScoringContracts,
  ]);

  const refreshJudgeMutationState = useCallback(async (rubricId: number | null | undefined) => {
    if (!selectedSnapshotId || rubricId == null) {
      return;
    }
    const pendingRequestId = ++pendingCountsRequestRef.current;
    await fetchScoringPendingCountsForRubric(selectedSnapshotId, rubricId, pendingRequestId);
  }, [selectedSnapshotId, fetchScoringPendingCountsForRubric]);

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
  }, [selectedSnapshotId, fetchScoringContracts]);

  const handleExportSnapshot = async () => {
    const activeRubricId = activeMetricSection?.rubric?.id;
    if (!selectedSnapshotId || !activeRubricId) return;
    try {
      const response = await metricsApi.exportJSON(selectedSnapshotId, activeRubricId);
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
    rubrics: orderedRubrics,
    scoringContracts,
    metricsByRubricId,
    getJudges,
    getBaselineJudge,
  });
  const activeMetricSection = metricSections[activeMetricTab] ?? metricSections[0] ?? null;

  if (snapshotsLoading || judgesLoading) {
    return <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}><CircularProgress /></Box>;
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
            onSnapshotDeleted={fetchSnapshots}
          />
        </Box>
        <Tooltip title="Download as JSON">
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
              startIcon={<IconDownload {...actionIconProps} />}
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
      ) : questionsWithoutAnswers > 0 ? (
        <Alert severity="warning">
          {questionsWithoutAnswers} new question{questionsWithoutAnswers > 1 ? "s" : ""} found. Run primary judge in the annotation tab before viewing scoring.
        </Alert>
      ) : (
        <Stack spacing={2}>
          <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
            <Tabs value={activeMetricTab} onChange={(_, value) => setActiveMetricTab(value)} sx={tabsSx}>
              {metricSections.map((section, index) => (
                <Tab
                  key={section.key}
                  label={section.title}
                  value={index}
                  sx={{
                    ...tabSx,
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
                loading={metricsLoading}
                questionsWithoutAnswers={questionsWithoutAnswers}
                pendingCountsByRubricId={pendingCountsByRubricId}
                onJobStart={handleJobStart}
                onJobComplete={handleJobComplete}
                onEditJudge={(judge, config) => openDialog("edit", config, judge)}
                onDuplicateJudge={(judge, config) => openDialog("duplicate", config, judge)}
                onDeleteJudge={handleDeleteJudge}
                onAddJudge={(config) => openDialog("create", config)}
              />

              <ResultsTable
                results={activeMetricSection.contract?.rows ?? []}
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
          await Promise.all([
            fetchJudgesForRubrics(rubrics),
            refreshJudgeMutationState(dialogConfig.rubricId),
          ]);
          setDialogOpen(false);
          setDialogJudge(null);
        }}
      />

      <ConfirmDeleteDialog
        open={judgeToDelete !== null}
        onClose={() => setJudgeToDelete(null)}
        onConfirm={async () => {
          if (!judgeToDelete) return;
          const rubricId = judgeToDelete.rubric_id;
          await judgeApi.delete(judgeToDelete.id);
          await Promise.all([
            fetchJudgesForRubrics(rubrics),
            refreshJudgeMutationState(rubricId),
          ]);
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
  metricsByRubricId,
  getJudges,
  getBaselineJudge,
}: {
  rubrics: TargetRubricResponse[];
  scoringContracts: ScoringContract[];
  metricsByRubricId: Record<number, SnapshotMetric>;
  getJudges: (rubricId: number | null | undefined) => JudgeConfig[];
  getBaselineJudge: (rubricId: number | null | undefined) => JudgeConfig | null;
}): MetricSectionConfig[] {
  const sections: MetricSectionConfig[] = [];
  for (const rubric of rubrics) {
    const sectionJudges = getJudges(rubric.id);
    const baselineJudge = getBaselineJudge(rubric.id);
    const contract = scoringContracts.find((metric) => metric.rubric_id === rubric.id) ?? null;
    sections.push({
      key: `rubric-${rubric.id}`,
      title: rubric.name,
      sourceGroup: rubric.group,
      rubric,
      contract,
      metric: metricsByRubricId[rubric.id] ?? null,
      judges: sectionJudges,
      emptyMessage: "Run judges to see results",
      gaugeLabel: `Share labeled ${contract?.best_option || rubric.best_option || rubric.options?.[0]?.option || rubric.name}`,
      defaultPromptTemplate: baselineJudge?.prompt_template || sectionJudges[0]?.prompt_template || "",
    });
  }

  return sections;
}

function MetricSection({
  section,
  snapshotId,
  loading,
  questionsWithoutAnswers,
  pendingCountsByRubricId,
  onJobStart,
  onJobComplete,
  onEditJudge,
  onDuplicateJudge,
  onDeleteJudge,
  onAddJudge,
}: {
  section: MetricSectionConfig;
  snapshotId: number;
  loading: boolean;
  questionsWithoutAnswers: number;
  pendingCountsByRubricId: Record<number, Record<number, number>>;
  onJobStart: (judgeId: number, rubricId: number) => Promise<QAJob[] | null>;
  onJobComplete: (rubricId: number) => Promise<void> | void;
  onEditJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDuplicateJudge: (judge: JudgeConfig, config: DialogConfig) => void;
  onDeleteJudge: (judge: JudgeConfig) => void;
  onAddJudge: (config: DialogConfig) => void;
}) {
  const dialogConfig: DialogConfig = {
    rubricId: section.rubric?.id ?? null,
    metricLabel: section.title,
    defaultPromptTemplate: section.defaultPromptTemplate,
  };

  return (
    <Stack>
      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", lg: "280px minmax(0, 1fr)" },
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
          questionsWithoutAnswers={questionsWithoutAnswers}
          pendingCountsByRubricId={pendingCountsByRubricId}
          onJobStart={onJobStart}
          onJobComplete={onJobComplete}
          onEditJudge={onEditJudge}
          onDuplicateJudge={onDuplicateJudge}
          onDeleteJudge={onDeleteJudge}
          onAddJudge={onAddJudge}
          dialogConfig={dialogConfig}
        />
      </Box>
    </Stack>
  );
}

function JudgeStrip({
  judges,
  section,
  snapshotId,
  questionsWithoutAnswers,
  pendingCountsByRubricId,
  onJobStart,
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
  questionsWithoutAnswers: number;
  pendingCountsByRubricId: Record<number, Record<number, number>>;
  onJobStart: (judgeId: number, rubricId: number) => Promise<QAJob[] | null>;
  onJobComplete: (rubricId: number) => Promise<void> | void;
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
        p: 1.5,
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 2,
          mb: 0.5,
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
          const pendingCount = section.rubric
            ? pendingCountsByRubricId[section.rubric.id]?.[judge.id] ?? null
            : null;

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
              <JudgeCard
                judge={judge}
                displayName={judge.name}
                summary={judgeSummary}
                snapshotId={snapshotId}
                rubricId={section.rubric?.id ?? judge.rubric_id ?? 0}
                pendingCount={pendingCount}
                scoreLabel={section.rubric?.best_option || section.rubric?.options?.[0]?.option || section.title}
                hasQuestionsWithoutAnswers={questionsWithoutAnswers > 0}
                onJobStart={(judgeId) => onJobStart(judgeId, section.rubric!.id)}
                onJobComplete={() => onJobComplete(section.rubric!.id)}
                onEdit={() => onEditJudge(judge, dialogConfig)}
                onDuplicate={() => onDuplicateJudge(judge, {
                  ...dialogConfig,
                  rubricId: judge.rubric_id ?? dialogConfig.rubricId,
                })}
                onDelete={() => onDeleteJudge(judge)}
                cardSx={{ width: "100%", height: "100%" }}
              />
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
      <ScoreGauge
        value={hasReliableJudges ? metric.aggregated_score : null}
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
