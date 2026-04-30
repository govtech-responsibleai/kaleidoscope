"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { IconDownload, IconPlus } from "@tabler/icons-react";
import { orderRubricsForDisplay } from "@/app/targets/[id]/rubrics";
import { tabSx, tabsSx } from "@/lib/styles";
import ScoreGauge from "@/components/shared/AccuracyGauge";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import JudgeCard from "@/components/scoring/JudgeCard";
import CreateJudgeDialog from "@/components/scoring/CreateJudgeDialog";
import ResultsTable from "@/components/scoring/ResultsTable";
import {
  JudgeConfig,
  QAJob,
  ScoringResultsFilters,
  ScoringResultsResponse,
  ScoringRubricResponse,
  ScoringStatusResponse,
  Snapshot,
  SnapshotMetric,
} from "@/lib/types";
import {
  getApiErrorMessage,
  judgeApi,
  metricsApi,
  qaJobApi,
  questionApi,
  snapshotApi,
  targetApi,
} from "@/lib/api";
import { actionIconProps, compactActionIconProps } from "@/lib/styles";
import { groupColors } from "@/lib/theme";
import { TESTIDS } from "@/tests/e2e/fixtures/testids";

type SourceGroup = "fixed" | "preset" | "custom";

interface MetricSectionConfig {
  key: string;
  title: string;
  sourceGroup: SourceGroup;
  rubric: ScoringRubricResponse | null;
  contract: ScoringResultsResponse | null;
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

interface TableQuery extends ScoringResultsFilters {
  page: number;
  page_size: number;
}

const DEFAULT_TABLE_QUERY: TableQuery = {
  labels: [],
  question_types: [],
  question_scopes: [],
  persona_ids: [],
  disagreements_only: false,
  judge_ids: [],
  page: 0,
  page_size: 10,
};

const getResultsCacheKey = (snapshotId: number, rubricId: number, query: TableQuery) =>
  JSON.stringify({ snapshotId, rubricId, query });

export default function ScoringPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const targetId = Number(params.id);

  const snapshotIdFromUrl = searchParams.get("snapshot");
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(
    snapshotIdFromUrl ? Number(snapshotIdFromUrl) : null,
  );
  const [snapshotsLoading, setSnapshotsLoading] = useState(true);

  const [rubrics, setRubrics] = useState<ScoringRubricResponse[]>([]);
  const [rubricsLoading, setRubricsLoading] = useState(true);
  const [scoringStatus, setScoringStatus] = useState<ScoringStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [resultsLoading, setResultsLoading] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit" | "duplicate">("create");
  const [dialogJudge, setDialogJudge] = useState<JudgeConfig | null>(null);
  const [dialogConfig, setDialogConfig] = useState<DialogConfig>({
    rubricId: null,
    metricLabel: "Score",
    defaultPromptTemplate: "",
  });
  const [judgeToDelete, setJudgeToDelete] = useState<JudgeConfig | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [activeMetricTab, setActiveMetricTab] = useState(0);
  const [tableQuery, setTableQuery] = useState<TableQuery>(DEFAULT_TABLE_QUERY);
  const resultsCacheRef = useRef<Record<string, ScoringResultsResponse>>({});
  const [latestResultsByRubricId, setLatestResultsByRubricId] = useState<Record<number, ScoringResultsResponse>>({});

  const statusRequestRef = useRef(0);
  const rubricsRequestRef = useRef(0);
  const resultsRequestRef = useRef(0);
  const orderedRubrics = useMemo(() => orderRubricsForDisplay(rubrics), [rubrics]);
  const activeRubric = orderedRubrics[activeMetricTab] ?? null;
  const activeRubricId = activeRubric?.id ?? null;
  const activeResults = activeRubricId != null ? latestResultsByRubricId[activeRubricId] ?? null : null;

  const getJudges = useCallback((rubricId: number | null | undefined) => {
    if (rubricId == null) {
      return [];
    }
    return orderedRubrics.find((rubric) => rubric.id === rubricId)?.judges ?? [];
  }, [orderedRubrics]);

  const getBaselineJudge = useCallback((rubricId: number | null | undefined) => (
    getJudges(rubricId).find((judge) => judge.is_baseline) ?? null
  ), [getJudges]);

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
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
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
  }, [selectedSnapshotId, targetId, updateSnapshotSelection]);

  const clearResultsCache = useCallback((rubricId?: number | null) => {
    resultsCacheRef.current = rubricId == null
      ? {}
      : Object.fromEntries(
          Object.entries(resultsCacheRef.current).filter(([key]) => !key.includes(`"rubricId":${rubricId},`)),
        );
    setLatestResultsByRubricId((current) => {
      if (rubricId == null) {
        return {};
      }
      const next = { ...current };
      delete next[rubricId];
      return next;
    });
  }, []);

  const fetchScoringStatus = useCallback(async (snapshotId: number, requestId?: number) => {
    setStatusLoading(true);
    try {
      const response = await metricsApi.getScoringStatus(snapshotId);
      if (requestId && requestId !== statusRequestRef.current) return;
      setScoringStatus(response.data);
    } catch (statusError) {
      if (requestId && requestId !== statusRequestRef.current) return;
      setScoringStatus(null);
      setError(getApiErrorMessage(statusError, "Failed to load scoring status."));
    } finally {
      if (!requestId || requestId === statusRequestRef.current) {
        setStatusLoading(false);
      }
    }
  }, []);

  const fetchScoringRubrics = useCallback(async (snapshotId: number, requestId?: number) => {
    setRubricsLoading(true);
    try {
      const response = await metricsApi.getScoringRubrics(snapshotId);
      if (requestId && requestId !== rubricsRequestRef.current) return;
      setRubrics(response.data.rubrics ?? []);
    } catch (rubricsError) {
      if (requestId && requestId !== rubricsRequestRef.current) return;
      setRubrics([]);
      setError(getApiErrorMessage(rubricsError, "Failed to load scoring rubrics."));
    } finally {
      if (!requestId || requestId === rubricsRequestRef.current) {
        setRubricsLoading(false);
      }
    }
  }, []);

  const fetchScoringResults = useCallback(async (
    snapshotId: number,
    rubricId: number,
    query: TableQuery,
    useCache = true,
  ) => {
    const cacheKey = getResultsCacheKey(snapshotId, rubricId, query);
    if (useCache && resultsCacheRef.current[cacheKey]) {
      const cached = resultsCacheRef.current[cacheKey];
      setLatestResultsByRubricId((current) => ({ ...current, [rubricId]: cached }));
      return cached;
    }

    const requestId = ++resultsRequestRef.current;
    setResultsLoading(true);
    try {
      const response = await metricsApi.getScoringResults(snapshotId, rubricId, query);
      if (requestId !== resultsRequestRef.current) {
        return null;
      }
      resultsCacheRef.current = { ...resultsCacheRef.current, [cacheKey]: response.data };
      setLatestResultsByRubricId((current) => ({ ...current, [rubricId]: response.data }));
      return response.data;
    } catch (resultsError) {
      if (requestId === resultsRequestRef.current) {
        setError(getApiErrorMessage(resultsError, "Failed to load scoring results."));
      }
      return null;
    } finally {
      if (requestId === resultsRequestRef.current) {
        setResultsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void fetchSnapshots();
  }, [fetchSnapshots]);

  useEffect(() => {
    setScoringStatus(null);
    setRubrics([]);
    setTableQuery(DEFAULT_TABLE_QUERY);
    setActiveMetricTab(0);
    clearResultsCache();
    setError(null);

    if (!selectedSnapshotId) {
      setStatusLoading(false);
      setRubricsLoading(false);
      return;
    }

    const nextStatusRequestId = ++statusRequestRef.current;
    const nextRubricsRequestId = ++rubricsRequestRef.current;
    void Promise.allSettled([
      fetchScoringStatus(selectedSnapshotId, nextStatusRequestId),
      fetchScoringRubrics(selectedSnapshotId, nextRubricsRequestId),
    ]);
  }, [clearResultsCache, fetchScoringRubrics, fetchScoringStatus, selectedSnapshotId]);

  useEffect(() => {
    setTableQuery(DEFAULT_TABLE_QUERY);
  }, [activeRubricId]);

  useEffect(() => {
    if (!selectedSnapshotId || !activeRubricId || !scoringStatus?.is_complete || scoringStatus.unanswered_question_count > 0) {
      return;
    }
    void fetchScoringResults(selectedSnapshotId, activeRubricId, tableQuery, true);
  }, [
    activeRubricId,
    fetchScoringResults,
    scoringStatus?.is_complete,
    scoringStatus?.unanswered_question_count,
    selectedSnapshotId,
    tableQuery,
  ]);

  const refreshActiveRubric = useCallback(async (rubricId: number | null | undefined) => {
    if (!selectedSnapshotId || rubricId == null) {
      return;
    }
    clearResultsCache(rubricId);
    const nextStatusRequestId = ++statusRequestRef.current;
    const nextRubricsRequestId = ++rubricsRequestRef.current;
    await Promise.allSettled([
      fetchScoringStatus(selectedSnapshotId, nextStatusRequestId),
      fetchScoringRubrics(selectedSnapshotId, nextRubricsRequestId),
    ]);
    await fetchScoringResults(selectedSnapshotId, rubricId, tableQuery, false);
  }, [
    clearResultsCache,
    fetchScoringResults,
    fetchScoringRubrics,
    fetchScoringStatus,
    selectedSnapshotId,
    tableQuery,
  ]);

  const refreshJudgeRunState = useCallback(async (rubricId: number | null | undefined) => {
    if (!selectedSnapshotId || rubricId == null) {
      return;
    }

    await fetchScoringResults(selectedSnapshotId, rubricId, tableQuery, false);
  }, [fetchScoringResults, selectedSnapshotId, tableQuery]);

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
      return response.data;
    } catch (jobError) {
      setError(getApiErrorMessage(jobError, "Unable to start judge run."));
      return null;
    }
  };

  const handleJobComplete = useCallback(async (rubricId: number) => {
    await refreshJudgeRunState(rubricId);
  }, [refreshJudgeRunState]);

  const refreshJudgeMutationState = useCallback(async (rubricId: number | null | undefined) => {
    await refreshActiveRubric(rubricId);
  }, [refreshActiveRubric]);

  const openDialog = (
    mode: "create" | "edit" | "duplicate",
    config: DialogConfig,
    judge?: JudgeConfig,
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
    await refreshActiveRubric(activeRubricId);
  }, [activeRubricId, refreshActiveRubric]);

  const handleExportSnapshot = async () => {
    if (!selectedSnapshotId || !activeRubricId) return;
    try {
      const response = await metricsApi.exportJSON(selectedSnapshotId, activeRubricId, {
        labels: tableQuery.labels,
        question_types: tableQuery.question_types,
        question_scopes: tableQuery.question_scopes,
        persona_ids: tableQuery.persona_ids,
        disagreements_only: tableQuery.disagreements_only,
        judge_ids: tableQuery.judge_ids,
      });
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
    resultsByRubricId: latestResultsByRubricId,
    getJudges,
    getBaselineJudge,
  });
  const activeMetricSection = metricSections[activeMetricTab] ?? metricSections[0] ?? null;

  if (snapshotsLoading || rubricsLoading) {
    return <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}><CircularProgress /></Box>;
  }

  console.log("Test 1")

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
              disabled={!selectedSnapshotId || !activeRubricId}
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
      ) : statusLoading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}><CircularProgress /></Box>
      ) : !scoringStatus?.is_complete ? (
        <Alert severity="info">
          {scoringStatus
            ? (() => {
                const totalSelected = scoringStatus.selected_ids.length;
                const totalAnnotated = scoringStatus.selected_and_annotated_ids.length;
                const annotatedSet = new Set(scoringStatus.selected_and_annotated_ids);
                const unannotatedIds = scoringStatus.selected_ids.filter((id) => !annotatedSet.has(id));
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
      ) : (scoringStatus.unanswered_question_count ?? 0) > 0 ? (
        <Alert severity="warning">
          {scoringStatus.unanswered_question_count} new question{scoringStatus.unanswered_question_count > 1 ? "s" : ""} found. Run primary judge in the annotation tab before viewing scoring.
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
                loading={resultsLoading && !activeMetricSection.contract}
                questionsWithoutAnswers={scoringStatus.unanswered_question_count}
                pendingCountsByRubricId={Object.fromEntries(
                  Object.entries(latestResultsByRubricId).map(([rubricId, response]) => [Number(rubricId), response.pending_counts]),
                )}
                onJobStart={handleJobStart}
                onJobComplete={handleJobComplete}
                onEditJudge={(judge, config) => openDialog("edit", config, judge)}
                onDuplicateJudge={(judge, config) => openDialog("duplicate", config, judge)}
                onDeleteJudge={handleDeleteJudge}
                onAddJudge={(config) => openDialog("create", config)}
              />

              <ResultsTable
                resultsResponse={activeResults}
                activeRubric={activeRubric}
                targetId={targetId}
                snapshotId={selectedSnapshotId}
                loading={resultsLoading}
                onLabelChange={handleLabelChange}
                onQueryChange={setTableQuery}
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
          await refreshJudgeMutationState(dialogConfig.rubricId);
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
          await refreshJudgeMutationState(rubricId);
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
  resultsByRubricId,
  getJudges,
  getBaselineJudge,
}: {
  rubrics: ScoringRubricResponse[];
  resultsByRubricId: Record<number, ScoringResultsResponse>;
  getJudges: (rubricId: number | null | undefined) => JudgeConfig[];
  getBaselineJudge: (rubricId: number | null | undefined) => JudgeConfig | null;
}): MetricSectionConfig[] {
  return rubrics.map((rubric) => {
    const sectionJudges = getJudges(rubric.id);
    const baselineJudge = getBaselineJudge(rubric.id);
    const contract = resultsByRubricId[rubric.id] ?? null;
    const metric = contract ? {
      snapshot_id: contract.snapshot_id ?? 0,
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
    } satisfies SnapshotMetric : null;

    return {
      key: `rubric-${rubric.id}`,
      title: rubric.name,
      sourceGroup: rubric.group,
      rubric,
      contract,
      metric,
      judges: sectionJudges,
      emptyMessage: "Open this rubric to load scoring data",
      gaugeLabel: `Share labeled ${contract?.best_option || rubric.best_option || rubric.options?.[0]?.option || rubric.name}`,
      defaultPromptTemplate: baselineJudge?.prompt_template || sectionJudges[0]?.prompt_template || "",
    };
  });
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
      data-testid={TESTIDS.JUDGE_LIST}
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
            data-testid={TESTIDS.JUDGE_ADD_BUTTON}
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
