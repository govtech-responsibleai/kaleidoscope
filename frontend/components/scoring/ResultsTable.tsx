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
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Download as DownloadIcon,
  KeyboardArrowDown as KeyboardArrowDownIcon,
  KeyboardArrowUp as KeyboardArrowUpIcon,
} from "@mui/icons-material";
import {
  ResultRow,
  JudgeConfig,
  QuestionResponse,
  PersonaResponse,
  QuestionType,
  QuestionScope,
  TargetRubricResponse,
  AnswerRubricLabel,
} from "@/lib/types";
import { questionApi, personaApi, metricsApi, annotationApi } from "@/lib/api";
import ResultsTableExpandedRow from "./ResultsTableExpandedRow";
import LabelCell from "./LabelCell";
import { QAFilter, JudgeFilter } from "./filters";
import { TableHeaderFilter, type FilterOption } from "@/components/shared";

interface ResultsTableProps {
  results: ResultRow[];
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

export default function ResultsTable({
  results, snapshotId, judges, rubrics, onLabelChange,
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

  const rowsPerPage = 10;

  const toggleRow = (answerId: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(answerId) ? next.delete(answerId) : next.add(answerId);
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
          answerIds.map((id) => annotationApi.getRubricLabels(id).then((r) => ({ answerId: id, labels: r.data })))
        );
        const map: Record<number, Record<number, string>> = {};
        responses.forEach(({ answerId, labels }) => {
          map[answerId] = {};
          (labels as AnswerRubricLabel[]).forEach((l) => {
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
        const metadata = result.aggregated_accuracy?.metadata ?? [];
        const labels = extractReliableLabels(metadata);
        return new Set(labels).size > 1;
      });
    }
    return filtered;
  }, [results, selectedLabels, showDisagreementsOnly, questionsMap, selectedTypes, selectedScopes, selectedPersonaIds]);

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

  React.useEffect(() => {
    setSelectedJudges(new Set(reliableJudges.map((j) => j.id)));
  }, [reliableJudges]);

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

  // Rubric tab strip (Accuracy + custom rubrics)
  const rubricTabValue = activeRubricId === null ? 0 : rubrics.findIndex((r) => r.id === activeRubricId) + 1;

  return (
    <Box>
      {/* Rubric tabs strip */}
      {rubrics.length > 0 && (
        <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}>
          <Tabs
            value={rubricTabValue}
            onChange={(_, v) => setActiveRubricId(v === 0 ? null : rubrics[v - 1].id)}
            sx={{ "& .MuiTab-root": { fontSize: "0.8rem", textTransform: "none", fontWeight: 500, minHeight: 40, py: 0 } }}
          >
            <Tab label="Accuracy" />
            {rubrics.map((r) => <Tab key={r.id} label={r.name} />)}
          </Tabs>
        </Box>
      )}

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1.5 }}>
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
          reliableJudges={reliableJudges}
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
          variant="contained" startIcon={<DownloadIcon />}
          onClick={handleExport} disabled={exporting}
          sx={{ bgcolor: theme.palette.secondary.main }}
        >
          {exporting ? "Exporting..." : "Export CSV"}
        </Button>
      </Stack>

      {excludedJudges.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Excluded evaluators (not reliable): {excludedJudges.map(j => j.name).join(", ")}
        </Alert>
      )}

      <TableContainer component={Paper} sx={{ boxShadow: "none" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: "5%" }} />
              <TableCell sx={{ width: "30%" }}>Question</TableCell>
              <TableCell sx={{ width: "30%" }}>Answer</TableCell>
              {/* Accuracy label column */}
              <TableCell sx={{ width: "100px" }}>
                <TableHeaderFilter
                  label="Accuracy"
                  options={labelFilterOptions}
                  value={selectedLabels}
                  onChange={(labels) => { setSelectedLabels(labels); setPage(0); }}
                  allSelectedLabel="All Labels"
                />
              </TableCell>
              {/* Custom rubric columns */}
              {rubrics.map((rubric) => (
                <TableCell
                  key={rubric.id}
                  sx={{
                    width: "90px", textAlign: "center", whiteSpace: "normal",
                    wordBreak: "break-word", padding: "8px 4px",
                    cursor: "pointer",
                    bgcolor: activeRubricId === rubric.id ? "action.selected" : "transparent",
                    fontWeight: activeRubricId === rubric.id ? 700 : 400,
                  }}
                  onClick={() => setActiveRubricId(activeRubricId === rubric.id ? null : rubric.id)}
                >
                  <Typography variant="body2" sx={{ lineHeight: 1.3, fontSize: "0.8rem", fontWeight: "inherit" }}>
                    {rubric.name}
                  </Typography>
                </TableCell>
              ))}
              {/* Judge columns (only for Accuracy tab) */}
              {activeRubricId === null && reliableJudges
                .filter((judge) => selectedJudges.has(judge.id))
                .map((judge) => (
                  <TableCell
                    key={judge.id}
                    sx={{ width: "70px", textAlign: "center", whiteSpace: "normal", wordBreak: "break-word", padding: "8px 4px" }}
                  >
                    <Typography variant="body2" sx={{ lineHeight: 1.3, fontSize: "0.8rem" }}>{judge.name}</Typography>
                  </TableCell>
                ))}
            </TableRow>
          </TableHead>

          <TableBody>
            {paginatedResults.map((result) => {
              const aggregatedAccuracy = result.aggregated_accuracy;
              const metadataEntries = aggregatedAccuracy?.metadata ?? [];
              const evaluatorLabels = parseEvaluatorData(metadataEntries);
              const evaluatorMap = new Map(evaluatorLabels.map((e) => [e.name, e.label]));

              // Accuracy chip
              let chipLabel = "No data";
              let chipColor: ChipProps["color"] = "default";
              let helperText: string | null = null;

              if (aggregatedAccuracy?.is_edited && aggregatedAccuracy.label !== null) {
                chipLabel = aggregatedAccuracy.label ? "Accurate" : "Inaccurate";
                chipColor = aggregatedAccuracy.label ? "success" : "error";
              } else if (selectedJudges.size === 0) {
                chipLabel = "No evaluators selected"; chipColor = "warning";
                helperText = "Please select at least one evaluator.";
              } else {
                const selLabels: boolean[] = [];
                reliableJudges.forEach((judge) => {
                  if (selectedJudges.has(judge.id)) {
                    const label = evaluatorMap.get(judge.name);
                    if (label !== null && label !== undefined) selLabels.push(label);
                  }
                });
                if (selLabels.length === 0) {
                  chipLabel = "No data"; chipColor = "default";
                } else {
                  const accurateCount = selLabels.filter((l) => l).length;
                  const inaccurateCount = selLabels.filter((l) => !l).length;
                  if (accurateCount > inaccurateCount) { chipLabel = "Accurate"; chipColor = "success"; }
                  else if (inaccurateCount > accurateCount) { chipLabel = "Inaccurate"; chipColor = "error"; }
                  else { chipLabel = "Tie"; chipColor = "warning"; helperText = "Equal votes."; }
                }
              }

              const isExpanded = expandedRows.has(result.answer_id);
              const answerRubricLabels = rubricLabelsMap[result.answer_id] ?? {};
              const totalColSpan = 4 + rubrics.length + (activeRubricId === null ? selectedJudges.size : 0);

              return (
                <React.Fragment key={result.answer_id}>
                  <TableRow hover>
                    <TableCell>
                      <IconButton size="small" onClick={() => toggleRow(result.answer_id)}>
                        {isExpanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                      </IconButton>
                    </TableCell>

                    <TableCell>
                      <Typography variant="subtitle2">{truncate(result.question_text ?? "", 160)}</Typography>
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2" color="text.secondary">{truncate(result.answer_content, 160)}</Typography>
                    </TableCell>

                    {/* Accuracy label */}
                    <TableCell>
                      <LabelCell
                        answerId={result.answer_id}
                        aggregatedAccuracy={aggregatedAccuracy}
                        chipLabel={chipLabel}
                        chipColor={chipColor}
                        helperText={helperText}
                        onLabelChange={onLabelChange}
                      />
                    </TableCell>

                    {/* Custom rubric label cells */}
                    {rubrics.map((rubric) => {
                      const val = answerRubricLabels[rubric.id];
                      return (
                        <TableCell key={rubric.id} align="center">
                          {val ? (
                            <Chip label={val} size="small" variant="outlined" sx={{ fontSize: "0.7rem", height: 20 }} />
                          ) : (
                            <Typography variant="caption" color="text.disabled">—</Typography>
                          )}
                        </TableCell>
                      );
                    })}

                    {/* Judge columns (Accuracy tab only) */}
                    {activeRubricId === null && reliableJudges
                      .filter((judge) => selectedJudges.has(judge.id))
                      .map((judge) => {
                        const label = evaluatorMap.get(judge.name);
                        return (
                          <TableCell key={judge.id} align="center">
                            {label === true ? <CheckCircleIcon color="success" fontSize="small" /> :
                             label === false ? <CancelIcon color="error" fontSize="small" /> :
                             <Typography variant="caption" color="text.secondary">--</Typography>}
                          </TableCell>
                        );
                      })}
                  </TableRow>

                  <TableRow>
                    <TableCell style={{ padding: 0 }} colSpan={totalColSpan}>
                      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                        <ResultsTableExpandedRow
                          result={result}
                          reliableJudges={reliableJudges}
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
