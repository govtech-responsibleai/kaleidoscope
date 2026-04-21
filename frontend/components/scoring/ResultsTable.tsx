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
  MetricScoringContract,
  MetricAggregatedResult,
  ResultRow,
  JudgeConfig,
  QuestionResponse,
  PersonaResponse,
  QuestionType,
  QuestionScope,
  TargetRubricResponse,
} from "@/lib/types";
import { questionApi, personaApi, metricsApi } from "@/lib/api";
import ResultsTableExpandedRow from "./ResultsTableExpandedRow";
import LabelCell, { type LabelCellOption } from "./LabelCell";
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
  contract: MetricScoringContract | null;
  targetId: number;
  snapshotId: number;
  judges: JudgeConfig[];
  rubrics: TargetRubricResponse[];
  onLabelChange?: () => void;
}
interface JudgeVerdictSummary {
  aggregateLabel: string;
  aggregateColor: ChipProps["color"];
  helperText: string | null;
  summaryLabel: string;
  summaryColor: ChipProps["color"];
}

const getAccuracyAggregatePresentation = (
  aggregate: MetricAggregatedResult | undefined,
): Pick<JudgeVerdictSummary, "aggregateLabel" | "aggregateColor" | "helperText"> => {
  if (!aggregate) {
    return { aggregateLabel: "No data", aggregateColor: "default", helperText: null };
  }

  if (aggregate.method === "pending") {
    return { aggregateLabel: "Pending", aggregateColor: "default", helperText: null };
  }

  if (aggregate.method === "majority_tied") {
    return { aggregateLabel: "Tie", aggregateColor: "warning", helperText: "Equal votes." };
  }

  if (aggregate.method === "no_aligned_judge") {
    return {
      aggregateLabel: "No reliable judges",
      aggregateColor: "warning",
      helperText: "Add or run reliable judges to score this row.",
    };
  }

  if (aggregate.value === "accurate") {
    return { aggregateLabel: "Accurate", aggregateColor: "success", helperText: null };
  }

  if (aggregate.value === "inaccurate") {
    return { aggregateLabel: "Inaccurate", aggregateColor: "error", helperText: null };
  }

  return { aggregateLabel: "No data", aggregateColor: "default", helperText: null };
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
  results,
  contract,
  targetId,
  snapshotId,
  judges,
  rubrics,
  onLabelChange,
}: ResultsTableProps) {
  const theme = useTheme();
  const isAccuracy = contract?.group === "fixed";
  const [page, setPage] = useState(0);
  const [selectedLabels, setSelectedLabels] = useState<string[]>(["accurate", "inaccurate"]);
  const [showDisagreementsOnly, setShowDisagreementsOnly] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedJudges, setSelectedJudges] = useState<Set<number>>(new Set());
  const [questionsMap, setQuestionsMap] = useState<Map<number, QuestionResponse>>(new Map());
  const [personasMap, setPersonasMap] = useState<Map<number, PersonaResponse>>(new Map());
  const [selectedTypes, setSelectedTypes] = useState<QuestionType[]>([QuestionType.TYPICAL, QuestionType.EDGE]);
  const [selectedScopes, setSelectedScopes] = useState<QuestionScope[]>([QuestionScope.IN_KB, QuestionScope.OUT_KB]);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);

  const rowsPerPage = 10;
  const rowMap = useMemo(
    () => new Map((contract?.rows ?? []).map((row) => [row.answer_id, row] as const)),
    [contract]
  );
  const activeRubric = useMemo(
    () => rubrics.find((rubric) => rubric.id === contract?.rubric_id) ?? null,
    [contract?.rubric_id, rubrics],
  );
  const labelFilterOptions: FilterOption<string>[] = useMemo(() => [
    { value: "accurate", label: "Accurate" },
    { value: "inaccurate", label: "Inaccurate" },
  ], []);
  const accuracyLabelOptions: LabelCellOption[] = useMemo(
    () => [
      { value: "accurate", label: "Accurate", color: "success" },
      { value: "inaccurate", label: "Inaccurate", color: "error" },
    ],
    [],
  );
  const rubricLabelOptions: LabelCellOption[] = useMemo(
    () =>
      activeRubric?.options.map((option) => ({
        value: option.option,
        label: option.option,
        color:
          option.option === activeRubric.best_option
            ? "success"
            : activeRubric.options.length <= 2
            ? "error"
            : "primary",
      })) ?? [],
    [activeRubric?.id, activeRubric?.options, activeRubric?.best_option],
  );
  const rubricEditingEnabled = useMemo(
    () => !isAccuracy && (contract?.aligned_judges.length ?? 0) > 0,
    [isAccuracy, contract?.aligned_judges.length],
  );

  const reliableJudgeIds = useMemo(
    () => new Set(contract?.aligned_judges.map((judge) => judge.judge_id) ?? []),
    [contract]
  );
  const excludedJudges = useMemo(
    () => judges.filter((judge) => (contract?.judge_summaries ?? []).some(
      (summary) => summary.judge_id === judge.id && summary.reliability != null && summary.reliability < 0.5
    )),
    [contract, judges]
  );
  const tableJudges = useMemo(
    () => sortJudges(judges.filter((judge) => reliableJudgeIds.has(judge.id))),
    [judges, reliableJudgeIds]
  );

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
    if (isAccuracy && selectedLabels.length < 2) {
      filtered = filtered.filter((result) => {
        const aggregated = result.aggregated_accuracy;
        const isAccurate = aggregated?.label === "accurate";
        if (selectedLabels.includes("inaccurate") && !selectedLabels.includes("accurate")) return aggregated?.label === "inaccurate";
        if (selectedLabels.includes("accurate") && !selectedLabels.includes("inaccurate")) return isAccurate;
        return true;
      });
    }
    if (showDisagreementsOnly) {
      filtered = filtered.filter((result) => {
        const row = rowMap.get(result.answer_id);
        const selectedTableJudges = tableJudges.filter((judge) => selectedJudges.has(judge.id));
        if (isAccuracy) {
          const labels = row
            ? row.judge_results
                .filter((judgeResult) => selectedTableJudges.some((judge) => judge.id === judgeResult.judge_id))
                .map((judgeResult) => judgeResult.value)
                .filter((label): label is string => typeof label === "string")
            : [];
          return new Set(labels).size > 1;
        }

        const selectedValues = row
          ? row.judge_results
              .filter((judgeResult) => selectedTableJudges.some((judge) => judge.id === judgeResult.judge_id))
              .map((judgeResult) => judgeResult.value)
              .filter((value): value is string => Boolean(value))
          : [];
        return new Set(selectedValues).size > 1;
      });
    }
    return filtered;
  }, [results, questionsMap, selectedTypes, selectedScopes, selectedPersonaIds, isAccuracy, selectedLabels, showDisagreementsOnly, rowMap, tableJudges, selectedJudges]);

  const paginatedResults = useMemo(
    () => filteredResults.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [filteredResults, page]
  );

  useEffect(() => {
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
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      alert("Failed to export results.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="h5">Error analysis table</Typography>
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
          variant="outlined"
          size="small"
          color="inherit"
          disableRipple
          sx={{ pr: 1.5, height: "40px", fontWeight: 400, borderColor: "rgba(0,0,0,0.2)" }}
        >
          <Checkbox
            size="small"
            checked={showDisagreementsOnly}
            onChange={(e) => { setPage(0); setShowDisagreementsOnly(e.target.checked); }}
          />
          Show only disagreements
        </Button>

        <Divider orientation="vertical" flexItem />

        <Button
          variant="contained"
          startIcon={<IconFileTypeCsv {...actionIconProps} />}
          onClick={handleExport}
          disabled={exporting}
          sx={{ bgcolor: theme.palette.secondary.main }}
        >
          {exporting ? "Exporting..." : "Export CSV"}
        </Button>
      </Stack>

      {excludedJudges.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Excluded judges (not reliable): {excludedJudges.map((judge) => judge.name).join(", ")}
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
              {isAccuracy ? (
                <TableCell sx={{ ...tableHeaderCellSx, width: "110px" }}>
                  <TableHeaderFilter
                    label="Accuracy"
                    options={labelFilterOptions}
                    value={selectedLabels}
                    onChange={(labels) => { setSelectedLabels(labels); setPage(0); }}
                    allSelectedLabel="All Labels"
                  />
                </TableCell>
              ) : (
                <TableCell sx={{ ...tableHeaderCellSx, width: "90px", textAlign: "center", whiteSpace: "normal", wordBreak: "break-word", px: 0.5 }}>
                  <Typography variant="body2" sx={{ lineHeight: 1.3, fontSize: "0.8rem", fontWeight: 700 }}>
                    Label
                  </Typography>
                </TableCell>
              )}
              <TableCell sx={{ ...tableHeaderCellSx, width: "130px" }}>
                Judge Summary
              </TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {paginatedResults.map((result) => {
              const row = rowMap.get(result.answer_id) ?? null;
              const isExpanded = expandedRows.has(result.answer_id);
              const selectedTableJudges = tableJudges.filter((judge) => selectedJudges.has(judge.id));
        const activeRubricId = !isAccuracy ? contract?.rubric_id ?? null : null;
              const answerRubricLabels = !isAccuracy && row?.human_option && activeRubricId !== null
                ? ({ [activeRubricId]: row.human_option } as Record<number, string>)
                : {};

              const accuracyVoteCounts = selectedTableJudges.reduce(
                (counts, judge) => {
                  const label = row?.judge_results.find((judgeResult) => judgeResult.judge_id === judge.id)?.value;
                  if (label === "accurate") counts.accurate += 1;
                  else if (label === "inaccurate") counts.inaccurate += 1;
                  else counts.missing += 1;
                  return counts;
                },
                { accurate: 0, inaccurate: 0, missing: 0 }
              );

              const rubricVoteCounts = selectedTableJudges.reduce((counts, judge) => {
                const value = row?.judge_results.find((judgeResult) => judgeResult.judge_id === judge.id)?.value;
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
              const effectiveAccuracyAggregate = getAccuracyAggregatePresentation(row?.aggregated_result);
              const summary = isAccuracy ? accuracySummary : rubricSummary;
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

                    <TableCell>
                      {isAccuracy || activeRubric ? (
                        <LabelCell
                          answerId={result.answer_id}
                          rubricId={contract?.rubric_id ?? 0}
                          value={row?.aggregated_result.value}
                          baselineValue={row?.aggregated_result.baseline_value}
                          displayLabel={isAccuracy ? effectiveAccuracyAggregate.aggregateLabel : (row?.aggregated_result.value ?? "Pending")}
                          chipColor={isAccuracy ? effectiveAccuracyAggregate.aggregateColor : rubricSummary.aggregateColor}
                          helperText={
                            isAccuracy
                              ? effectiveAccuracyAggregate.helperText
                              : row?.aggregated_result.is_edited && row?.aggregated_result.baseline_value
                              ? `Baseline: ${row.aggregated_result.baseline_value}`
                              : null
                          }
                          options={isAccuracy ? accuracyLabelOptions : rubricLabelOptions}
                          isEditable={
                            !isAccuracy
                              ? rubricEditingEnabled &&
                                (row?.aggregated_result.method === "majority" ||
                                  row?.aggregated_result.method === "override")
                              : undefined
                          }
                          showEditedBadge={row?.aggregated_result.is_edited ?? false}
                          resetTooltip={!isAccuracy ? "Reset to aggregated label" : undefined}
                          editTooltip={!isAccuracy ? "Edit rubric label" : undefined}
                          onLabelChange={onLabelChange}
                        />
                      ) : (
                        <Chip
                          label={rubricSummary.aggregateLabel}
                          size="small"
                          color={rubricSummary.aggregateColor}
                          sx={{ ...compactChipSx, fontSize: "0.7rem", height: 20, maxWidth: 140 }}
                        />
                      )}
                    </TableCell>

                    <TableCell>
                      <Stack spacing={0.5}>
                        <Chip
                          label={summary.summaryLabel}
                          size="small"
                          color={summary.summaryColor}
                          variant={summary.summaryColor === "default" ? "outlined" : "filled"}
                          sx={{ ...compactChipSx, maxWidth: 150, width: "fit-content" }}
                        />
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
