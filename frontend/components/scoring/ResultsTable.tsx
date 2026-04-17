"use client";

import React, { useState, useMemo, useEffect } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  ChipProps,
  Collapse,
  Divider,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
  useTheme,
} from "@mui/material";
import {
  IconChevronDown,
  IconChevronUp,
  IconFileTypeCsv,
} from "@tabler/icons-react";
import {
  ResultRow,
  JudgeConfig,
  QuestionResponse,
  PersonaResponse,
  QuestionType,
  QuestionScope,
  TargetRubricResponse,
  RubricAnnotation,
  RubricAnswerScore,
} from "@/lib/types";
import { questionApi, personaApi, metricsApi, annotationApi, rubricScoreApi, judgeApi } from "@/lib/api";
import ResultsTableExpandedRow from "./ResultsTableExpandedRow";
import LabelCell from "./LabelCell";
import { QAFilter, JudgeFilter } from "./filters";
import { TableHeaderFilter, type FilterOption } from "@/components/shared";
import { actionIconProps, compactActionIconProps } from "@/lib/iconStyles";
import { sortJudges } from "@/lib/judgeOrdering";
import {
  compactChipSx,
  getTableBodyRowSx,
  tableContainerSx,
  tableHeaderCellSx,
  tableHeaderRowSx,
} from "@/lib/uiStyles";

interface ResultsTableProps {
  results: ResultRow[];
  targetId: number;
  snapshotId: number;
  judges: JudgeConfig[];
  rubrics: TargetRubricResponse[];
  onLabelChange?: () => void;
}

const extractReliableLabels = (metadata: string[]) => {
  const labels: boolean[] = [];
  metadata.forEach((entry) => {
    const lower = entry.toLowerCase();
    if (lower.includes("excluded")) return;
    if (lower.includes("inaccurate")) { labels.push(false); return; }
    if (lower.includes("accurate")) labels.push(true);
  });
  return labels;
};

interface EvaluatorData { name: string; label: boolean | null; }
interface JudgeVerdictSummary {
  aggregateLabel: string;
  aggregateColor: ChipProps["color"];
  helperText: string | null;
  summaryLabel: string;
  summaryColor: ChipProps["color"];
}

const parseEvaluatorData = (metadata: string[]): EvaluatorData[] => {
  return metadata.map((entry) => {
    const cleanEntry = entry.replace(/^-\s*/, "").trim();
    const parts = cleanEntry.split(":");
    if (parts.length < 2) return { name: cleanEntry, label: null };
    const name = parts[0].trim();
    const labelText = parts.slice(1).join(":").trim().toLowerCase();
    if (labelText.includes("excluded")) return { name, label: null };
    if (labelText === "inaccurate" || labelText.startsWith("inaccurate")) return { name, label: false };
    if (labelText === "accurate" || labelText.startsWith("accurate")) return { name, label: true };
    return { name, label: null };
  });
};

const truncate = (value: string, length: number) => {
  if (!value) return "";
  return value.length > length ? `${value.slice(0, length)}…` : value;
};

const summarizeAccuracyVotes = (
  accurateCount: number,
  inaccurateCount: number,
  missingCount: number,
  selectedJudgeCount: number,
): JudgeVerdictSummary => {
  const labeledCount = accurateCount + inaccurateCount;

  if (selectedJudgeCount === 0) {
    return {
      aggregateLabel: "No judges selected",
      aggregateColor: "warning",
      helperText: "Please select at least one judge.",
      summaryLabel: "No judges selected",
      summaryColor: "warning",
    };
  }

  if (labeledCount === 0) {
    return {
      aggregateLabel: "No data",
      aggregateColor: "default",
      helperText: null,
      summaryLabel: missingCount > 0 ? `${missingCount} missing` : "No judge outputs",
      summaryColor: "default",
    };
  }

  if (accurateCount === inaccurateCount) {
    return {
      aggregateLabel: "Tie",
      aggregateColor: "warning",
      helperText: "Equal votes.",
      summaryLabel: `${accurateCount} accurate, ${inaccurateCount} inaccurate${missingCount > 0 ? `, ${missingCount} missing` : ""}`,
      summaryColor: "warning",
    };
  }

  const winnerIsAccurate = accurateCount > inaccurateCount;
  const winnerCount = Math.max(accurateCount, inaccurateCount);
  const loserCount = Math.min(accurateCount, inaccurateCount);
  const summaryParts = loserCount === 0
    ? [`${winnerCount}/${labeledCount} ${winnerIsAccurate ? "accurate" : "inaccurate"}`]
    : [`${winnerCount} agree`, `${loserCount} disagree`];

  if (missingCount > 0) {
    summaryParts.push(`${missingCount} missing`);
  }

  return {
    aggregateLabel: winnerIsAccurate ? "Accurate" : "Inaccurate",
    aggregateColor: winnerIsAccurate ? "success" : "error",
    helperText: null,
    summaryLabel: summaryParts.join(", "),
    summaryColor: loserCount > 0 || missingCount > 0 ? "warning" : winnerIsAccurate ? "success" : "error",
  };
};

const summarizeRubricVotes = (
  optionCounts: Map<string, number>,
  missingCount: number,
  selectedJudgeCount: number,
): JudgeVerdictSummary => {
  if (selectedJudgeCount === 0) {
    return {
      aggregateLabel: "No judges selected",
      aggregateColor: "warning",
      helperText: "Please select at least one judge.",
      summaryLabel: "No judges selected",
      summaryColor: "warning",
    };
  }

  const sortedCounts = [...optionCounts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const labeledCount = sortedCounts.reduce((sum, [, count]) => sum + count, 0);

  if (labeledCount === 0) {
    return {
      aggregateLabel: "No data",
      aggregateColor: "default",
      helperText: null,
      summaryLabel: missingCount > 0 ? `${missingCount} missing` : "No judge outputs",
      summaryColor: "default",
    };
  }

  const [majorityOption, majorityCount] = sortedCounts[0];
  const secondCount = sortedCounts[1]?.[1] ?? 0;
  const disagreementCount = labeledCount - majorityCount;

  if (majorityCount === secondCount) {
    return {
      aggregateLabel: "Tie",
      aggregateColor: "warning",
      helperText: "Equal rubric votes.",
      summaryLabel: `${sortedCounts.length} options split${missingCount > 0 ? `, ${missingCount} missing` : ""}`,
      summaryColor: "warning",
    };
  }

  return {
    aggregateLabel: truncate(majorityOption, 18),
    aggregateColor: disagreementCount === 0 ? "success" : "primary",
    helperText: null,
    summaryLabel: disagreementCount === 0
      ? `${majorityCount}/${labeledCount} agree${missingCount > 0 ? `, ${missingCount} missing` : ""}`
      : `${majorityCount} agree, ${disagreementCount} disagree${missingCount > 0 ? `, ${missingCount} missing` : ""}`,
    summaryColor: disagreementCount > 0 || missingCount > 0 ? "warning" : "success",
  };
};

export default function ResultsTable({
  results, targetId, snapshotId, judges, rubrics, onLabelChange,
}: ResultsTableProps) {
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const [selectedLabels, setSelectedLabels] = useState<string[]>(["accurate", "inaccurate"]);
  const [showDisagreementsOnly, setShowDisagreementsOnly] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedJudges, setSelectedJudges] = useState<Set<number>>(new Set());
  // Which rubric tab is active in table header (null = Accuracy / main label column)
  const [activeRubricId, setActiveRubricId] = useState<number | null>(null);

  const [questionsMap, setQuestionsMap] = useState<Map<number, QuestionResponse>>(new Map());
  const [personasMap, setPersonasMap] = useState<Map<number, PersonaResponse>>(new Map());
  const [selectedTypes, setSelectedTypes] = useState<QuestionType[]>([QuestionType.TYPICAL, QuestionType.EDGE]);
  const [selectedScopes, setSelectedScopes] = useState<QuestionScope[]>([QuestionScope.IN_KB, QuestionScope.OUT_KB]);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);

  // Rubric labels: answerId -> rubricId -> option_value
  const [rubricLabelsMap, setRubricLabelsMap] = useState<Record<number, Record<number, string>>>({});

  // rubricJudgeScores: answerId -> judgeId -> option_chosen (for rubric tabs)
  const [rubricJudgeScoresMap, setRubricJudgeScoresMap] = useState<Record<number, Record<number, string>>>({});
  // judges for the active rubric tab
  const [activeRubricJudges, setActiveRubricJudges] = useState<JudgeConfig[]>([]);

  const rowsPerPage = 10;

  const toggleRow = (answerId: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(answerId)) {
        next.delete(answerId);
      } else {
        next.add(answerId);
      }
      return next;
    });
  };

  // Fetch questions and personas
  useEffect(() => {
    const fetchQuestionsAndPersonas = async () => {
      if (results.length === 0) return;
      const uniqueQuestionIds = [...new Set(results.map((r) => r.question_id))];
      try {
        const questionResponses = await Promise.all(uniqueQuestionIds.map((id) => questionApi.get(id)));
        const newQuestionsMap = new Map<number, QuestionResponse>();
        const personaIdsToFetch = new Set<number>();
        questionResponses.forEach((res) => {
          newQuestionsMap.set(res.data.id, res.data);
          if (res.data.persona_id !== null) personaIdsToFetch.add(res.data.persona_id);
        });
        setQuestionsMap(newQuestionsMap);
        const personaResponses = await Promise.all([...personaIdsToFetch].map((id) => personaApi.get(id)));
        const newPersonasMap = new Map<number, PersonaResponse>();
        personaResponses.forEach((res) => newPersonasMap.set(res.data.id, res.data));
        setPersonasMap(newPersonasMap);
        setSelectedPersonaIds([...personaIdsToFetch]);
      } catch (err) {
        console.error("Failed to fetch questions/personas:", err);
      }
    };
    fetchQuestionsAndPersonas();
  }, [results]);

  // Fetch rubric labels for all answers when rubrics exist
  useEffect(() => {
    if (rubrics.length === 0 || results.length === 0) return;
    const fetchRubricLabels = async () => {
      const answerIds = results.map((r) => r.answer_id);
      try {
        const responses = await Promise.all(
          answerIds.map((id) => annotationApi.getRubricAnnotations(id).then((r) => ({ answerId: id, labels: r.data })))
        );
        const map: Record<number, Record<number, string>> = {};
        responses.forEach(({ answerId, labels }) => {
          map[answerId] = {};
          (labels as RubricAnnotation[]).forEach((l) => {
            map[answerId][l.rubric_id] = l.option_value;
          });
        });
        setRubricLabelsMap(map);
      } catch (err) {
        console.error("Failed to fetch rubric labels:", err);
      }
    };
    fetchRubricLabels();
  }, [results, rubrics]);

  const filteredResults = useMemo(() => {
    let filtered = results;
    if (questionsMap.size > 0) {
      filtered = filtered.filter((result) => {
        const question = questionsMap.get(result.question_id);
        if (!question) return true;
        const typeMatch = question.type ? selectedTypes.includes(question.type) : true;
        const scopeMatch = question.scope ? selectedScopes.includes(question.scope) : true;
        const personaMatch = question.persona_id === null || selectedPersonaIds.length === 0 || selectedPersonaIds.includes(question.persona_id);
        return typeMatch && scopeMatch && personaMatch;
      });
    }
    if (selectedLabels.length < 2) {
      filtered = filtered.filter((result) => {
        const aggregated = result.aggregated_accuracy;
        if (aggregated?.is_edited && aggregated.label !== null) {
          const isAccurate = aggregated.label === true;
          if (selectedLabels.includes("inaccurate") && !selectedLabels.includes("accurate")) return !isAccurate;
          if (selectedLabels.includes("accurate") && !selectedLabels.includes("inaccurate")) return isAccurate;
          return true;
        }
        const metadata = aggregated?.metadata ?? [];
        const labels = extractReliableLabels(metadata);
        const inaccurateCount = labels.filter((l) => l === false).length;
        const accurateCount = labels.filter((l) => l === true).length;
        if (selectedLabels.includes("inaccurate") && !selectedLabels.includes("accurate")) return inaccurateCount > accurateCount;
        if (selectedLabels.includes("accurate") && !selectedLabels.includes("inaccurate")) return accurateCount > inaccurateCount;
        return true;
      });
    }
    if (showDisagreementsOnly) {
      filtered = filtered.filter((result) => {
        if (activeRubricId === null) {
          const metadata = result.aggregated_accuracy?.metadata ?? [];
          const evaluatorMap = new Map(parseEvaluatorData(metadata).map((entry) => [entry.name, entry.label]));
          const labels = Array.from(selectedJudges)
            .map((judgeId) => judges.find((judge) => judge.id === judgeId))
            .filter((judge): judge is JudgeConfig => Boolean(judge))
            .map((judge) => evaluatorMap.get(judge.name))
            .filter((label): label is boolean => typeof label === "boolean");
          return new Set(labels).size > 1;
        }

        const rubricLabels = rubricJudgeScoresMap[result.answer_id] ?? {};
        const selectedValues = Array.from(selectedJudges)
          .map((judgeId) => rubricLabels[judgeId])
          .filter((value): value is string => Boolean(value));

        return new Set(selectedValues).size > 1;
      });
    }
    return filtered;
  }, [results, selectedLabels, showDisagreementsOnly, questionsMap, selectedTypes, selectedScopes, selectedPersonaIds, activeRubricId, selectedJudges, rubricJudgeScoresMap, judges]);

  const paginatedResults = useMemo(
    () => filteredResults.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [filteredResults, page]
  );

  const labelFilterOptions: FilterOption<string>[] = useMemo(() => [
    { value: "accurate", label: "Accurate" },
    { value: "inaccurate", label: "Inaccurate" },
  ], []);

  const { reliableJudges, excludedJudges } = useMemo(() => {
    if (results.length === 0) return { reliableJudges: judges, excludedJudges: [] };
    const judgeReliability = new Map<number, boolean>();
    results.forEach((result) => {
      const evaluators = parseEvaluatorData(result.aggregated_accuracy?.metadata ?? []);
      evaluators.forEach((evaluator) => {
        const judge = judges.find((j) => j.name === evaluator.name);
        if (judge) {
          const existing = judgeReliability.get(judge.id);
          const isReliable = evaluator.label !== null;
          judgeReliability.set(judge.id, existing === undefined ? isReliable : existing && isReliable);
        }
      });
    });
    const reliable: JudgeConfig[] = [];
    const excluded: JudgeConfig[] = [];
    judges.forEach((judge) => {
      const r = judgeReliability.get(judge.id);
      if (r === true) reliable.push(judge);
      else if (r === false) excluded.push(judge);
    });
    return { reliableJudges: reliable, excludedJudges: excluded };
  }, [results, judges]);

  const accuracyJudges = useMemo(
    () => sortJudges(reliableJudges.filter((j) => j.judge_type === "claim_based")),
    [reliableJudges]
  );

  const tableJudges = useMemo(
    () => activeRubricId === null ? accuracyJudges : sortJudges(activeRubricJudges),
    [activeRubricId, accuracyJudges, activeRubricJudges]
  );

  const activeJudgeSummary = useMemo(() => {
    const selected = tableJudges.filter((judge) => selectedJudges.has(judge.id));
    if (selected.length === 0) {
      return [];
    }
    return selected.map((judge) => judge.name);
  }, [tableJudges, selectedJudges]);

  React.useEffect(() => {
    setSelectedJudges((prev) => {
      const availableIds = new Set(tableJudges.map((judge) => judge.id));
      const retained = [...prev].filter((judgeId) => availableIds.has(judgeId));
      return retained.length > 0 || tableJudges.length === 0
        ? new Set(retained)
        : new Set(tableJudges.map((judge) => judge.id));
    });
  }, [tableJudges]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await metricsApi.exportCSV(snapshotId, "csv");
      const blob = response.data;
      const disposition = response.headers?.["content-disposition"];
      let filename = `snapshot_${snapshotId}_results.csv`;
      if (disposition) {
        const match = disposition.match(/filename="?([^\";]+)"?/i);
        if (match?.[1]) filename = match[1];
      }
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = filename;
      document.body.appendChild(link); link.click();
      document.body.removeChild(link); window.URL.revokeObjectURL(url);
    } catch {
      alert("Failed to export results.");
    } finally {
      setExporting(false);
    }
  };

  // Fetch rubric judge scores and judges when a custom rubric tab is active
  useEffect(() => {
    if (activeRubricId === null || results.length === 0) {
      setRubricJudgeScoresMap({});
      setActiveRubricJudges([]);
      return;
    }
    const activeRubric = rubrics.find((r) => r.id === activeRubricId);
    if (!activeRubric) return;

    // Fetch response-level judges and rubric scores together, then filter judges
    const answerIds = results.map((r) => r.answer_id);
    Promise.all([
      judgeApi.getByCategory(
        activeRubric.category,
        targetId,
        activeRubric.template_key ? undefined : activeRubric.id
      ).catch(() => ({ data: [] as JudgeConfig[] })),
      Promise.all(
        answerIds.map((id) =>
          rubricScoreApi.getForAnswer(id, activeRubricId)
            .then((res) => ({ answerId: id, scores: res.data as RubricAnswerScore[] }))
            .catch(() => ({ answerId: id, scores: [] as RubricAnswerScore[] }))
        )
      ),
    ]).then(([judgesRes, entries]) => {
      const map: Record<number, Record<number, string>> = {};
      entries.forEach(({ answerId, scores }) => {
        map[answerId] = {};
        scores.forEach((s) => {
          map[answerId][s.judge_id] = s.option_chosen;
        });
      });
      setRubricJudgeScoresMap(map);
      const rubricScopedJudges = judgesRes.data.filter((j) => j.judge_type === "response_level");
      setActiveRubricJudges(sortJudges(Array.from(new Map(rubricScopedJudges.map((j) => [j.id, j])).values())));
    });
  }, [activeRubricId, results, rubrics, targetId]);

  return (
    <Box>
      {/* Rubric pill toggles */}
      {rubrics.length > 0 && (
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Chip
            label="Accuracy"
            onClick={() => setActiveRubricId(null)}
            variant={activeRubricId === null ? "filled" : "outlined"}
            color={activeRubricId === null ? "primary" : "default"}
            sx={{ fontWeight: 600, fontSize: "0.85rem", height: 36, px: 1 }}
          />
          {rubrics.map((r) => (
            <Chip
              key={r.id}
              label={r.name}
              onClick={() => setActiveRubricId(r.id)}
              variant={activeRubricId === r.id ? "filled" : "outlined"}
              color={activeRubricId === r.id ? "primary" : "default"}
              sx={{ fontWeight: 600, fontSize: "0.85rem", height: 36, px: 1 }}
            />
          ))}
        </Stack>
      )}

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="h5">All Questions & Answers</Typography>
        <Box sx={{ flexGrow: 1 }} />

        <QAFilter
          selectedTypes={selectedTypes}
          selectedScopes={selectedScopes}
          selectedPersonaIds={selectedPersonaIds}
          personas={[...personasMap.values()]}
          onTypesChange={(types) => { setSelectedTypes(types); setPage(0); }}
          onScopesChange={(scopes) => { setSelectedScopes(scopes); setPage(0); }}
          onPersonaIdsChange={(ids) => { setSelectedPersonaIds(ids); setPage(0); }}
        />

        <JudgeFilter
          judges={tableJudges}
          selectedJudgeIds={selectedJudges}
          onSelectionChange={setSelectedJudges}
        />

        <Button
          variant="outlined" size="small" color="inherit" disableRipple
          sx={{ pr: 1.5, height: "40px", fontWeight: 400, borderColor: "rgba(0,0,0,0.2)" }}
        >
          <Checkbox
            size="small" checked={showDisagreementsOnly}
            onChange={(e) => { setPage(0); setShowDisagreementsOnly(e.target.checked); }}
          />
          Show only disagreements
        </Button>

        <Divider orientation="vertical" flexItem />

        <Button
          variant="contained" startIcon={<IconFileTypeCsv {...actionIconProps} />}
          onClick={handleExport} disabled={exporting}
          sx={{ bgcolor: theme.palette.secondary.main }}
        >
          {exporting ? "Exporting..." : "Export CSV"}
        </Button>
      </Stack>

      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Active judges:
        </Typography>
        {activeJudgeSummary.length > 0 ? (
          <>
            {activeJudgeSummary.map((judgeName) => (
              <Chip
                key={judgeName}
                label={judgeName}
                size="small"
                variant="outlined"
                sx={{
                  ...compactChipSx,
                  height: "auto",
                  "& .MuiChip-label": {
                    display: "block",
                    whiteSpace: "normal",
                    lineHeight: 1.3,
                    py: 0.5,
                  },
                }}
              />
            ))}
          </>
        ) : (
          <Typography variant="body2" color="warning.main">
            No judges selected
          </Typography>
        )}
      </Stack>

      {excludedJudges.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Excluded judges (not reliable): {excludedJudges.map(j => j.name).join(", ")}
        </Alert>
      )}

      <TableContainer component={Paper} sx={tableContainerSx}>
        <Table size="small">
          <TableHead>
            <TableRow sx={tableHeaderRowSx}>
              <TableCell sx={{ width: "5%" }} />
              <TableCell sx={{ ...tableHeaderCellSx, width: "5%" }}>ID</TableCell>
              <TableCell sx={{ ...tableHeaderCellSx, width: "28%" }}>Question</TableCell>
              <TableCell sx={{ ...tableHeaderCellSx, width: "28%" }}>Answer</TableCell>
              {/* Accuracy label column (Accuracy tab) */}
              {activeRubricId === null && (
                <TableCell sx={{ ...tableHeaderCellSx, width: "110px" }}>
                  <TableHeaderFilter
                    label="Accuracy"
                    options={labelFilterOptions}
                    value={selectedLabels}
                    onChange={(labels) => { setSelectedLabels(labels); setPage(0); }}
                    allSelectedLabel="All Labels"
                  />
                </TableCell>
              )}
              {/* Human label column (custom rubric tab) */}
              {activeRubricId !== null && (() => {
                const activeRubric = rubrics.find((r) => r.id === activeRubricId);
                return activeRubric ? (
                  <TableCell
                    sx={{ ...tableHeaderCellSx, width: "90px", textAlign: "center", whiteSpace: "normal", wordBreak: "break-word", px: 0.5 }}
                  >
                    <Typography variant="body2" sx={{ lineHeight: 1.3, fontSize: "0.8rem", fontWeight: 700 }}>
                      {activeRubric.name}
                    </Typography>
                  </TableCell>
                ) : null;
              })()}
              <TableCell sx={{ ...tableHeaderCellSx, width: "130px" }}>
                Judge Summary
              </TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {paginatedResults.map((result) => {
              const aggregatedAccuracy = result.aggregated_accuracy;
              const metadataEntries = aggregatedAccuracy?.metadata ?? [];
              const evaluatorLabels = parseEvaluatorData(metadataEntries);
              const evaluatorMap = new Map(evaluatorLabels.map((e) => [e.name, e.label]));

              const isExpanded = expandedRows.has(result.answer_id);
              const answerRubricLabels = rubricLabelsMap[result.answer_id] ?? {};
              const rubricJudgeLabels = rubricJudgeScoresMap[result.answer_id] ?? {};
              const selectedTableJudges = tableJudges.filter((judge) => selectedJudges.has(judge.id));

              const accuracyVoteCounts = selectedTableJudges.reduce(
                (counts, judge) => {
                  const label = evaluatorMap.get(judge.name);
                  if (label === true) counts.accurate += 1;
                  else if (label === false) counts.inaccurate += 1;
                  else counts.missing += 1;
                  return counts;
                },
                { accurate: 0, inaccurate: 0, missing: 0 }
              );

              const rubricVoteCounts = selectedTableJudges.reduce((counts, judge) => {
                const value = rubricJudgeLabels[judge.id];
                if (value) {
                  counts.options.set(value, (counts.options.get(value) ?? 0) + 1);
                } else {
                  counts.missing += 1;
                }
                return counts;
              }, { options: new Map<string, number>(), missing: 0 });

              const accuracySummary = summarizeAccuracyVotes(
                accuracyVoteCounts.accurate,
                accuracyVoteCounts.inaccurate,
                accuracyVoteCounts.missing,
                selectedTableJudges.length,
              );
              const rubricSummary = summarizeRubricVotes(
                rubricVoteCounts.options,
                rubricVoteCounts.missing,
                selectedTableJudges.length,
              );
              const summary = activeRubricId === null ? accuracySummary : rubricSummary;
              const totalColSpan = 6;

              return (
                <React.Fragment key={result.answer_id}>
                  <TableRow hover sx={getTableBodyRowSx(theme)}>
                    <TableCell>
                      <IconButton size="small" onClick={() => toggleRow(result.answer_id)}>
                        {isExpanded ? <IconChevronUp {...compactActionIconProps} /> : <IconChevronDown {...compactActionIconProps} />}
                      </IconButton>
                    </TableCell>

                    <TableCell>
                      <Typography
                        variant="body2"
                        component="a"
                        href={`/targets/${targetId}/annotation?snapshot=${snapshotId}&question=${result.question_id}`}
                        sx={{
                          color: "primary.main",
                          cursor: "pointer",
                          textDecoration: "none",
                          "&:hover": { textDecoration: "underline" },
                        }}
                      >
                        Q{result.question_id}
                      </Typography>
                    </TableCell>

                    <TableCell>
                      <Typography variant="subtitle2">{truncate(result.question_text ?? "", 160)}</Typography>
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2" color="text.secondary">{truncate(result.answer_content, 160)}</Typography>
                    </TableCell>

                    {/* Accuracy label (Accuracy tab) */}
                    {activeRubricId === null && (
                      <TableCell>
                        <LabelCell
                          answerId={result.answer_id}
                          aggregatedAccuracy={aggregatedAccuracy}
                          chipLabel={accuracySummary.aggregateLabel}
                          chipColor={accuracySummary.aggregateColor}
                          helperText={accuracySummary.helperText}
                          onLabelChange={onLabelChange}
                        />
                      </TableCell>
                    )}

                    {/* Rubric consensus label (custom rubric tab) */}
                    {activeRubricId !== null && (() => {
                      return (
                        <TableCell align="center">
                          <Chip
                            label={rubricSummary.aggregateLabel}
                            size="small"
                            color={rubricSummary.aggregateColor}
                            sx={{ ...compactChipSx, fontSize: "0.7rem", height: 20, maxWidth: 140 }}
                          />
                        </TableCell>
                      );
                    })()}

                    <TableCell>
                      <Stack spacing={0.5}>
                        <Chip
                          label={summary.summaryLabel}
                          size="small"
                          color={summary.summaryColor}
                          variant={summary.summaryColor === "default" ? "outlined" : "filled"}
                          sx={{ ...compactChipSx, maxWidth: 150, width: "fit-content" }}
                        />
                        {activeRubricId !== null && answerRubricLabels[activeRubricId] && (
                          <Typography variant="caption" color="text.secondary">
                            Human label: {answerRubricLabels[activeRubricId]}
                          </Typography>
                        )}
                      </Stack>
                    </TableCell>
                  </TableRow>

                  <TableRow>
                    <TableCell style={{ padding: 0 }} colSpan={totalColSpan}>
                      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                        <ResultsTableExpandedRow
                          result={result}
                          targetId={targetId}
                          tableJudges={tableJudges}
                          selectedJudgeIds={Array.from(selectedJudges)}
                          rubrics={rubrics}
                          activeRubricId={activeRubricId}
                          answerRubricLabels={answerRubricLabels}
                        />
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        rowsPerPageOptions={[rowsPerPage]}
        rowsPerPage={rowsPerPage}
        count={filteredResults.length}
        page={page}
        onPageChange={(_event, newPage) => setPage(newPage)}
      />
    </Box>
  );
}
