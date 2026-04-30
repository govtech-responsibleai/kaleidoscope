"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  ChipProps,
  Collapse,
  CircularProgress,
  IconButton,
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
  QuestionScope,
  QuestionType,
  ScoringResultsFilters,
  ScoringResultsResponse,
  ScoringRubricResponse,
} from "@/lib/types";
import { metricsApi } from "@/lib/api";
import ResultsTableExpandedRow from "./ResultsTableExpandedRow";
import LabelCell, { type LabelCellOption } from "./LabelCell";
import { QAFilter, JudgeFilter } from "./filters";
import { TESTIDS } from "@/tests/e2e/fixtures/testids";
import { TableHeaderFilter, type FilterOption } from "@/components/shared";
import { actionIconProps, compactActionIconProps } from "@/lib/styles";
import {
  compactChipSx,
  getTableBodyRowSx,
  tableContainerSx,
  tableHeaderCellSx,
  tableHeaderRowSx,
} from "@/lib/styles";

interface ResultsTableProps {
  resultsResponse: ScoringResultsResponse | null;
  activeRubric: ScoringRubricResponse | null;
  targetId: number;
  snapshotId: number;
  loading?: boolean;
  onLabelChange?: () => void;
  onQueryChange?: (query: ScoringResultsFilters & { page: number; page_size: number }) => void;
}

interface JudgeVerdictSummary {
  aggregateLabel: string;
  aggregateColor: ChipProps["color"];
  helperText: string | null;
  summaryLabel: string;
  summaryColor: ChipProps["color"];
}

const ROWS_PER_PAGE = 10;

const getRubricOptionColor = (
  value: string | null | undefined,
  rubric: ScoringRubricResponse | null,
): ChipProps["color"] => {
  if (!value || !rubric) {
    return "default";
  }
  if (value === rubric.best_option) {
    return "success";
  }
  return "error";
};

const truncate = (value: string, length: number) => {
  if (!value) return "";
  return value.length > length ? `${value.slice(0, length)}…` : value;
};

const summarizeRubricVotes = (
  optionCounts: Map<string, number>,
  missingCount: number,
  selectedJudgeCount: number,
  rubric: ScoringRubricResponse | null,
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
    aggregateColor: disagreementCount === 0 ? getRubricOptionColor(majorityOption, rubric) : "primary",
    helperText: null,
    summaryLabel: disagreementCount === 0
      ? `${majorityCount}/${labeledCount} agree${missingCount > 0 ? `, ${missingCount} missing` : ""}`
      : `${majorityCount} agree, ${disagreementCount} disagree${missingCount > 0 ? `, ${missingCount} missing` : ""}`,
    summaryColor: disagreementCount > 0 || missingCount > 0 ? "warning" : getRubricOptionColor(majorityOption, rubric),
  };
};

export default function ResultsTable({
  resultsResponse,
  activeRubric,
  targetId,
  snapshotId,
  loading = false,
  onLabelChange,
  onQueryChange,
}: ResultsTableProps) {
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
  const [showDisagreementsOnly, setShowDisagreementsOnly] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedJudges, setSelectedJudges] = useState<Set<number>>(new Set());
  const [selectedTypes, setSelectedTypes] = useState<QuestionType[]>([QuestionType.TYPICAL, QuestionType.EDGE]);
  const [selectedScopes, setSelectedScopes] = useState<QuestionScope[]>([QuestionScope.IN_KB, QuestionScope.OUT_KB]);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);

  const rowMap = useMemo(
    () => new Map((resultsResponse?.rows ?? []).map((row) => [row.answer_id, row] as const)),
    [resultsResponse?.rows],
  );
  const visibleJudgeIds = useMemo(
    () => new Set(resultsResponse?.aligned_judges.map((judge) => judge.judge_id) ?? []),
    [resultsResponse],
  );
  const tableJudges = useMemo(
    () => (activeRubric?.judges ?? []).filter((judge) => visibleJudgeIds.has(judge.id)),
    [activeRubric, visibleJudgeIds],
  );
  const excludedJudgeIds = useMemo(
    () => new Set(
      (resultsResponse?.judge_summaries ?? [])
        .filter((summary) => summary.reliability != null && summary.reliability < 0.5)
        .map((summary) => summary.judge_id),
    ),
    [resultsResponse],
  );
  const excludedJudges = useMemo(
    () => (activeRubric?.judges ?? []).filter((judge) => excludedJudgeIds.has(judge.id)),
    [activeRubric, excludedJudgeIds],
  );
  const personas = useMemo(
    () => (resultsResponse?.persona_options ?? []).map((option) => ({
      id: option.id,
      title: option.title,
    })),
    [resultsResponse],
  );
  const labelFilterOptions: FilterOption<string>[] = useMemo(() => (
    activeRubric?.options.map((option) => ({ value: option.option, label: option.option })) ?? []
  ), [activeRubric]);
  const activeRubricOptions = useMemo(
    () => activeRubric?.options ?? [],
    [activeRubric],
  );
  const rubricLabelOptions: LabelCellOption[] = useMemo(
    () =>
      activeRubric?.options.map((option) => ({
        value: option.option,
        label: option.option,
        color: getRubricOptionColor(option.option, activeRubric),
      })) ?? [],
    [activeRubric],
  );

  useEffect(() => {
    setSelectedLabels(activeRubricOptions.map((option) => option.option));
    setSelectedPersonaIds([]);
    setPage(0);
    setExpandedRows(new Set());
  }, [activeRubric?.id, activeRubricOptions]);

  useEffect(() => {
    const nextVisibleJudgeIds = tableJudges.map((judge) => judge.id);
    setSelectedJudges((current) => {
      const retained = [...current].filter((judgeId) => nextVisibleJudgeIds.includes(judgeId));
      return retained.length > 0 || nextVisibleJudgeIds.length === 0
        ? new Set(retained)
        : new Set(nextVisibleJudgeIds);
    });
  }, [tableJudges]);

  useEffect(() => {
    if (!onQueryChange) {
      return;
    }

    const allLabelsSelected = selectedLabels.length === 0
      || selectedLabels.length === (activeRubric?.options.length ?? 0);

    onQueryChange({
      labels: allLabelsSelected ? [] : selectedLabels,
      question_types: selectedTypes,
      question_scopes: selectedScopes,
      persona_ids: selectedPersonaIds,
      disagreements_only: showDisagreementsOnly,
      judge_ids: Array.from(selectedJudges),
      page,
      page_size: ROWS_PER_PAGE,
    });
  }, [
    activeRubric?.options.length,
    onQueryChange,
    page,
    selectedJudges,
    selectedLabels,
    selectedPersonaIds,
    selectedScopes,
    selectedTypes,
    showDisagreementsOnly,
  ]);

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

  const handleExport = async () => {
    if (!activeRubric) {
      return;
    }
    setExporting(true);
    try {
      const allLabelsSelected = selectedLabels.length === 0
        || selectedLabels.length === activeRubric.options.length;
      const response = await metricsApi.exportCSV(snapshotId, activeRubric.id, "csv", {
        labels: allLabelsSelected ? [] : selectedLabels,
        question_types: selectedTypes,
        question_scopes: selectedScopes,
        persona_ids: selectedPersonaIds,
        disagreements_only: showDisagreementsOnly,
        judge_ids: Array.from(selectedJudges),
      });
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

  if (!activeRubric) {
    return null;
  }

  return (
    <Box data-testid={TESTIDS.RESULTS_TABLE} sx={tableContainerSx}>
      <Box sx={{ px: 2, pt: 2, pb: 1 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="subtitle1" fontWeight={700} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            Results
            <Chip label={resultsResponse?.total_count ?? 0} size="small" sx={{ height: 18, fontSize: "0.65rem", "& .MuiChip-label": { px: 0.75 } }} />
          </Typography>
          <Box sx={{ flexGrow: 1 }} />

          <QAFilter
            selectedTypes={selectedTypes}
            selectedScopes={selectedScopes}
            selectedPersonaIds={selectedPersonaIds}
            personas={personas}
            onTypesChange={(types) => { setSelectedTypes(types); setPage(0); }}
            onScopesChange={(scopes) => { setSelectedScopes(scopes); setPage(0); }}
            onPersonaIdsChange={(ids) => { setSelectedPersonaIds(ids); setPage(0); }}
          />

          <JudgeFilter
            judges={tableJudges}
            selectedJudgeIds={selectedJudges}
            onSelectionChange={(ids) => { setSelectedJudges(ids); setPage(0); }}
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
      </Box>

      {excludedJudges.length > 0 && (
        <Alert severity="warning" sx={{ mx: 2, mb: 1 }}>
          Excluded judges (not reliable): {excludedJudges.map((judge) => judge.name).join(", ")}
        </Alert>
      )}

      {loading && !resultsResponse ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow sx={tableHeaderRowSx}>
                  <TableCell sx={{ width: "5%" }} />
                  <TableCell sx={{ ...tableHeaderCellSx, width: "5%" }}>ID</TableCell>
                  <TableCell sx={{ ...tableHeaderCellSx, width: "20%" }}>Question</TableCell>
                  <TableCell sx={{ ...tableHeaderCellSx, width: "36%" }}>Answer</TableCell>
                  <TableCell sx={{ ...tableHeaderCellSx, width: 140, minWidth: 140, maxWidth: 140 }}>
                    <TableHeaderFilter
                      label={activeRubric.name}
                      options={labelFilterOptions}
                      value={selectedLabels}
                      onChange={(labels) => { setSelectedLabels(labels); setPage(0); }}
                      allSelectedLabel={`All ${activeRubric.name} Labels`}
                    />
                  </TableCell>
                  <TableCell sx={{ ...tableHeaderCellSx, width: "130px" }}>
                    Judge Summary
                  </TableCell>
                </TableRow>
              </TableHead>

              <TableBody>
                {(resultsResponse?.rows ?? []).map((result) => {
                  const row = rowMap.get(result.answer_id) ?? null;
                  const isExpanded = expandedRows.has(result.answer_id);
                  const selectedTableJudges = tableJudges.filter((judge) => selectedJudges.has(judge.id));
                  const activeRubricId = activeRubric.id;
                  const humanSelectedOption = row?.human_label ?? null;
                  const answerRubricLabels = humanSelectedOption
                    ? ({ [activeRubricId]: humanSelectedOption } as Record<number, string>)
                    : {};

                  const rubricVoteCounts = selectedTableJudges.reduce((counts, judge) => {
                    const value = row?.judge_results.find((judgeResult) => judgeResult.judge_id === judge.id)?.value;
                    if (value) {
                      counts.options.set(value, (counts.options.get(value) ?? 0) + 1);
                    } else {
                      counts.missing += 1;
                    }
                    return counts;
                  }, { options: new Map<string, number>(), missing: 0 });

                  const rubricSummary = summarizeRubricVotes(
                    rubricVoteCounts.options,
                    rubricVoteCounts.missing,
                    selectedTableJudges.length,
                    activeRubric,
                  );
                  const totalColSpan = 6;

                  return (
                    <React.Fragment key={result.answer_id}>
                      <TableRow hover sx={getTableBodyRowSx(theme)}>
                        <TableCell>
                          <IconButton
                            size="small"
                            data-testid={TESTIDS.RESULTS_TABLE_ROW_TOGGLE}
                            onClick={() => toggleRow(result.answer_id)}
                          >
                            {isExpanded ? <IconChevronUp {...compactActionIconProps} /> : <IconChevronDown {...compactActionIconProps} />}
                          </IconButton>
                        </TableCell>

                        <TableCell>
                          <Typography
                            variant="body2"
                            component="a"
                            href={`/targets/${targetId}/annotation?snapshot=${snapshotId}&question=${result.question_id}&rubric=${activeRubric.id}`}
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
                          <Typography variant="body2" color="text.secondary" sx={{ display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{result.answer_content}</Typography>
                        </TableCell>

                        <TableCell sx={{ width: 140, minWidth: 140, maxWidth: 140 }}>
                          <LabelCell
                            answerId={result.answer_id}
                            rubricId={activeRubric.id}
                            value={row?.aggregated_result.value}
                            baselineValue={row?.aggregated_result.baseline_value}
                            displayLabel={rubricSummary.aggregateLabel}
                            chipColor={rubricSummary.aggregateColor}
                            helperText={
                              rubricSummary.helperText ??
                                (row?.aggregated_result.is_edited && row?.aggregated_result.baseline_value
                                ? `Baseline: ${row.aggregated_result.baseline_value}`
                                : null)
                            }
                            options={rubricLabelOptions}
                            isEditable={rubricLabelOptions.length > 0}
                            showEditedBadge={row?.aggregated_result.is_edited ?? false}
                            resetTooltip="Reset to aggregated label"
                            editTooltip="Edit rubric label"
                            onLabelChange={onLabelChange}
                          />
                        </TableCell>

                        <TableCell>
                          <Stack spacing={0.5}>
                            <Chip
                              label={rubricSummary.summaryLabel}
                              size="small"
                              color={rubricSummary.summaryColor}
                              variant={rubricSummary.summaryColor === "default" ? "outlined" : "filled"}
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
                              rubrics={[activeRubric]}
                              activeRubricId={activeRubric.id}
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
            rowsPerPageOptions={[ROWS_PER_PAGE]}
            rowsPerPage={ROWS_PER_PAGE}
            count={resultsResponse?.total_count ?? 0}
            page={page}
            onPageChange={(_event, newPage) => setPage(newPage)}
          />
        </>
      )}
    </Box>
  );
}
