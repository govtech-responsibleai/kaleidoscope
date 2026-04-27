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
  ScoringContract,
  ScoringRowResult,
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
import { actionIconProps, compactActionIconProps } from "@/lib/styles";
import {
  compactChipSx,
  getTableBodyRowSx,
  tableContainerSx,
  tableHeaderCellSx,
  tableHeaderRowSx,
} from "@/lib/styles";

interface ResultsTableProps {
  results: ScoringRowResult[];
  contract: ScoringContract | null;
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

const getRubricOptionColor = (
  value: string | null | undefined,
  rubric: TargetRubricResponse | null,
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

const getHumanSelectedOption = (row: ScoringRowResult | null): string | null =>
  row?.human_label ?? null;

const summarizeRubricVotes = (
  optionCounts: Map<string, number>,
  missingCount: number,
  selectedJudgeCount: number,
  rubric: TargetRubricResponse | null,
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
  results,
  contract,
  targetId,
  snapshotId,
  judges,
  rubrics,
  onLabelChange,
}: ResultsTableProps) {
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
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
    () => new Map(results.map((row) => [row.answer_id, row] as const)),
    [results]
  );
  const activeRubric = useMemo(
    () => rubrics.find((rubric) => rubric.id === contract?.rubric_id) ?? null,
    [contract?.rubric_id, rubrics],
  );
  const labelFilterOptions: FilterOption<string>[] = useMemo(() => (
    activeRubric?.options.map((option) => ({ value: option.option, label: option.option })) ?? []
  ), [activeRubric]);
  const rubricLabelOptions: LabelCellOption[] = useMemo(
    () =>
      activeRubric?.options.map((option) => ({
        value: option.option,
        label: option.option,
        color: getRubricOptionColor(option.option, activeRubric),
      })) ?? [],
    [activeRubric],
  );
  const rubricEditingEnabled = useMemo(
    () => Boolean(activeRubric) && rubricLabelOptions.length > 0,
    [activeRubric, rubricLabelOptions.length],
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
    () => judges.filter((judge) => reliableJudgeIds.has(judge.id)),
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
    setSelectedLabels(activeRubric?.options.map((option) => option.option) ?? []);
    setPage(0);
  }, [activeRubric]);

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
    if (activeRubric && selectedLabels.length > 0 && selectedLabels.length < activeRubric.options.length) {
      filtered = filtered.filter((result) => {
        const aggregatedValue = result.aggregated_result.value;
        return aggregatedValue ? selectedLabels.includes(aggregatedValue) : false;
      });
    }
    if (showDisagreementsOnly) {
      filtered = filtered.filter((result) => {
        const row = rowMap.get(result.answer_id);
        const selectedTableJudges = tableJudges.filter((judge) => selectedJudges.has(judge.id));
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
  }, [results, questionsMap, selectedTypes, selectedScopes, selectedPersonaIds, activeRubric, selectedLabels, showDisagreementsOnly, rowMap, tableJudges, selectedJudges]);

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
    if (!activeRubric) {
      return;
    }
    setExporting(true);
    try {
      const response = await metricsApi.exportCSV(snapshotId, activeRubric.id, "csv");
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
    <Box sx={tableContainerSx}>
      <Box sx={{ px: 2, pt: 2, pb: 1 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="subtitle1" fontWeight={700} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            Results
            <Chip label={filteredResults.length} size="small" sx={{ height: 18, fontSize: "0.65rem", "& .MuiChip-label": { px: 0.75 } }} />
          </Typography>
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

      <TableContainer>
        <Table>
          <TableHead>
            <TableRow sx={tableHeaderRowSx}>
              <TableCell sx={{ width: "5%" }} />
              <TableCell sx={{ ...tableHeaderCellSx, width: "5%" }}>ID</TableCell>
              <TableCell sx={{ ...tableHeaderCellSx, width: "20%" }}>Question</TableCell>
              <TableCell sx={{ ...tableHeaderCellSx, width: "36%" }}>Answer</TableCell>
              {activeRubric ? (
                <TableCell sx={{ ...tableHeaderCellSx, width: 140, minWidth: 140, maxWidth: 140 }}>
                  <TableHeaderFilter
                    label={activeRubric.name}
                    options={labelFilterOptions}
                    value={selectedLabels}
                    onChange={(labels) => { setSelectedLabels(labels); setPage(0); }}
                    allSelectedLabel={`All ${activeRubric.name} Labels`}
                  />
                </TableCell>
              ) : (
                <TableCell sx={{ ...tableHeaderCellSx, width: 140, minWidth: 140, maxWidth: 140 }}>
                  Label
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
              const activeRubricId = contract?.rubric_id ?? null;
              const humanSelectedOption = getHumanSelectedOption(row);
              const answerRubricLabels = humanSelectedOption && activeRubricId !== null
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
              const summary = rubricSummary;
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
                        href={`/targets/${targetId}/annotation?snapshot=${snapshotId}&question=${result.question_id}${activeRubric ? `&rubric=${activeRubric.id}` : ""}`}
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
                      {activeRubric ? (
                        <LabelCell
                          answerId={result.answer_id}
                          rubricId={contract?.rubric_id ?? 0}
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
                          isEditable={rubricEditingEnabled}
                          showEditedBadge={row?.aggregated_result.is_edited ?? false}
                          resetTooltip="Reset to aggregated label"
                          editTooltip="Edit rubric label"
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
