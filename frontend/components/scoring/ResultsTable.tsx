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
import { ResultRow, JudgeConfig, QuestionResponse, PersonaResponse, QuestionType, QuestionScope } from "@/lib/types";
import { questionApi, personaApi, metricsApi } from "@/lib/api";
import ResultsTableExpandedRow from "./ResultsTableExpandedRow";
import LabelCell from "./LabelCell";
import { QAFilter, JudgeFilter } from "./filters";
import { TableHeaderFilter, type FilterOption } from "@/components/shared";

interface ResultsTableProps {
  results: ResultRow[];
  snapshotId: number;
  judges: JudgeConfig[];
  onLabelChange?: () => void;
}

const extractReliableLabels = (metadata: string[]) => {
  const labels: boolean[] = [];
  metadata.forEach((entry) => {
    const lower = entry.toLowerCase();
    if (lower.includes("excluded")) {
      return;
    }
    // Check "inaccurate" BEFORE "accurate" since "inaccurate" contains "accurate"
    if (lower.includes("inaccurate")) {
      labels.push(false);
      return;
    }
    if (lower.includes("accurate")) {
      labels.push(true);
    }
  });
  return labels;
};

// Parse metadata to extract evaluator names and their labels
interface EvaluatorData {
  name: string;
  label: boolean | null; // true = accurate, false = inaccurate, null = excluded
}

const parseEvaluatorData = (metadata: string[]): EvaluatorData[] => {
  return metadata.map((entry) => {
    // Format: "- Evaluator Name: Accurate" or "- Evaluator Name: Inaccurate" or "- Evaluator Name: excluded as not reliable"
    // Remove leading dash and whitespace that backend adds
    const cleanEntry = entry.replace(/^-\s*/, "").trim();
    const parts = cleanEntry.split(":");
    if (parts.length < 2) {
      return { name: cleanEntry, label: null };
    }

    const name = parts[0].trim();
    const labelText = parts.slice(1).join(":").trim().toLowerCase();

    // Check in order: excluded first, then inaccurate (before accurate to avoid substring match)
    if (labelText.includes("excluded")) {
      return { name, label: null };
    }
    if (labelText === "inaccurate" || labelText.startsWith("inaccurate")) {
      return { name, label: false };
    }
    if (labelText === "accurate" || labelText.startsWith("accurate")) {
      return { name, label: true };
    }

    return { name, label: null };
  });
};

const truncate = (value: string, length: number) => {
  if (!value) return "";
  return value.length > length ? `${value.slice(0, length)}…` : value;
};

export default function ResultsTable({
  results,
  snapshotId,
  judges,
  onLabelChange,
}: ResultsTableProps) {
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const [selectedLabels, setSelectedLabels] = useState<string[]>(["accurate", "inaccurate"]);
  const [showDisagreementsOnly, setShowDisagreementsOnly] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedJudges, setSelectedJudges] = useState<Set<number>>(new Set());

  // Question filter state
  const [questionsMap, setQuestionsMap] = useState<Map<number, QuestionResponse>>(new Map());
  const [personasMap, setPersonasMap] = useState<Map<number, PersonaResponse>>(new Map());
  const [selectedTypes, setSelectedTypes] = useState<QuestionType[]>([QuestionType.TYPICAL, QuestionType.EDGE]);
  const [selectedScopes, setSelectedScopes] = useState<QuestionScope[]>([QuestionScope.IN_KB, QuestionScope.OUT_KB]);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);

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

  // Fetch questions and personas for filtering
  useEffect(() => {
    const fetchQuestionsAndPersonas = async () => {
      if (results.length === 0) return;

      const uniqueQuestionIds = [...new Set(results.map((r) => r.question_id))];

      try {
        // Fetch all questions
        const questionPromises = uniqueQuestionIds.map((id) => questionApi.get(id));
        const questionResponses = await Promise.all(questionPromises);

        const newQuestionsMap = new Map<number, QuestionResponse>();
        const personaIdsToFetch = new Set<number>();

        questionResponses.forEach((res) => {
          newQuestionsMap.set(res.data.id, res.data);
          if (res.data.persona_id !== null) {
            personaIdsToFetch.add(res.data.persona_id);
          }
        });

        setQuestionsMap(newQuestionsMap);

        // Fetch all personas
        const personaPromises = [...personaIdsToFetch].map((id) => personaApi.get(id));
        const personaResponses = await Promise.all(personaPromises);

        const newPersonasMap = new Map<number, PersonaResponse>();
        personaResponses.forEach((res) => {
          newPersonasMap.set(res.data.id, res.data);
        });

        setPersonasMap(newPersonasMap);

        // Initialize selectedPersonaIds with all personas
        setSelectedPersonaIds([...personaIdsToFetch]);
      } catch (err) {
        console.error("Failed to fetch questions/personas:", err);
      }
    };

    fetchQuestionsAndPersonas();
  }, [results]);

  // Filter results based on selected filters
  const filteredResults = useMemo(() => {
    let filtered = results;

    // Filter by question type, scope, and persona
    if (questionsMap.size > 0) {
      filtered = filtered.filter((result) => {
        const question = questionsMap.get(result.question_id);
        if (!question) return true; // Keep if question not loaded yet

        const typeMatch = question.type ? selectedTypes.includes(question.type) : true;
        const scopeMatch = question.scope ? selectedScopes.includes(question.scope) : true;
        const personaMatch =
          question.persona_id === null ||
          selectedPersonaIds.length === 0 ||
          selectedPersonaIds.includes(question.persona_id);

        return typeMatch && scopeMatch && personaMatch;
      });
    }

    // Filter by label
    if (selectedLabels.length < 2) {
      filtered = filtered.filter((result) => {
        const aggregated = result.aggregated_accuracy;

        // If label was edited, use the override directly
        if (aggregated?.is_edited && aggregated.label !== null) {
          const isAccurate = aggregated.label === true;
          if (selectedLabels.includes("inaccurate") && !selectedLabels.includes("accurate")) {
            return !isAccurate;
          } else if (selectedLabels.includes("accurate") && !selectedLabels.includes("inaccurate")) {
            return isAccurate;
          }
          return true;
        }

        // Otherwise use evaluator majority vote
        const metadata = aggregated?.metadata ?? [];
        const labels = extractReliableLabels(metadata);
        const inaccurateCount = labels.filter((l) => l === false).length;
        const accurateCount = labels.filter((l) => l === true).length;

        if (selectedLabels.includes("inaccurate") && !selectedLabels.includes("accurate")) {
          return inaccurateCount > accurateCount;
        } else if (selectedLabels.includes("accurate") && !selectedLabels.includes("inaccurate")) {
          return accurateCount > inaccurateCount;
        }
        return true;
      });
    }

    // Filter for disagreements only
    if (showDisagreementsOnly) {
      filtered = filtered.filter((result) => {
        const metadata = result.aggregated_accuracy?.metadata ?? [];
        const labels = extractReliableLabels(metadata);
        const unique = new Set(labels);
        return unique.size > 1;
      });
    }

    return filtered;
  }, [results, selectedLabels, showDisagreementsOnly, questionsMap, selectedTypes, selectedScopes, selectedPersonaIds]);

  const paginatedResults = useMemo(() => {
    return filteredResults.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
  }, [filteredResults, page]);

  const labelFilterOptions: FilterOption<string>[] = useMemo(() => [
    { value: "accurate", label: "Accurate" },
    { value: "inaccurate", label: "Inaccurate" },
  ], []);

  // Extract all evaluators and determine which are reliable based on metadata
  const { reliableJudges, excludedJudges } = useMemo(() => {
    // If no results yet, show all judges
    if (results.length === 0) {
      return { reliableJudges: judges, excludedJudges: [] };
    }

    const judgeReliability = new Map<number, boolean>();

    results.forEach((result) => {
      const metadata = result.aggregated_accuracy?.metadata ?? [];
      const evaluators = parseEvaluatorData(metadata);

      evaluators.forEach((evaluator) => {
        // Match evaluator name to judge
        const judge = judges.find((j) => j.name === evaluator.name);
        if (judge) {
          const existing = judgeReliability.get(judge.id);
          // A judge is reliable if it has actual labels (not excluded) in all results
          const isReliable = evaluator.label !== null;
          judgeReliability.set(judge.id, existing === undefined ? isReliable : existing && isReliable);
        }
      });
    });

    const reliable: JudgeConfig[] = [];
    const excluded: JudgeConfig[] = [];

    judges.forEach((judge) => {
      const isReliable = judgeReliability.get(judge.id);
      if (isReliable === true) {
        reliable.push(judge);
      } else if (isReliable === false) {
        excluded.push(judge);
      }
    });

    return { reliableJudges: reliable, excludedJudges: excluded };
  }, [results, judges]);

  // Initialize selectedJudges with all reliable judges by default
  React.useEffect(() => {
    setSelectedJudges(new Set(reliableJudges.map((j) => j.id)));
  }, [reliableJudges]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await metricsApi.exportCSV(snapshotId, "csv");
      const blob = response.data;

      // Try to honor backend-provided filename if the header exists
      const disposition = response.headers?.["content-disposition"];
      let filename = `snapshot_${snapshotId}_results.csv`;
      if (disposition) {
        const match = disposition.match(/filename="?([^\";]+)"?/i);
        if (match?.[1]) {
          filename = match[1];
        }
      }

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to export results:", error);
      alert("Failed to export results. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="h5">All Questions & Answers</Typography>

        <Box sx={{ flexGrow: 1 }} />

        <QAFilter
          selectedTypes={selectedTypes}
          selectedScopes={selectedScopes}
          selectedPersonaIds={selectedPersonaIds}
          personas={[...personasMap.values()]}
          onTypesChange={(types) => {
            setSelectedTypes(types);
            setPage(0);
          }}
          onScopesChange={(scopes) => {
            setSelectedScopes(scopes);
            setPage(0);
          }}
          onPersonaIdsChange={(ids) => {
            setSelectedPersonaIds(ids);
            setPage(0);
          }}
        />

        <JudgeFilter
          reliableJudges={reliableJudges}
          selectedJudgeIds={selectedJudges}
          onSelectionChange={setSelectedJudges}
        />

        <Button
          variant="outlined"
          size="small"
          color="inherit"
          disableRipple
          sx={{ 
            pr: 1.5, 
            height: "40px", 
            fontWeight: 400, 
            borderColor: "rgba(0, 0, 0, 0.2)"
          }}
        >
          <Checkbox
            size="small"
            checked={showDisagreementsOnly}
            onChange={(event) => {
              setPage(0);
              setShowDisagreementsOnly(event.target.checked);
            }}

          />
          Show only disagreements
        </Button>
        
        <Divider orientation="vertical" flexItem />

        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleExport}
          disabled={exporting}
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
              <TableCell sx={{ width: "35%" }}>Question</TableCell>
              <TableCell sx={{ width: "35%" }}>Answer</TableCell>
              <TableCell sx={{ width: "100px" }}>
                <TableHeaderFilter
                  label="Label"
                  options={labelFilterOptions}
                  value={selectedLabels}
                  onChange={(labels) => {
                    setSelectedLabels(labels);
                    setPage(0);
                  }}
                  allSelectedLabel="All Labels"
                />
              </TableCell>
              {reliableJudges
                .filter((judge) => selectedJudges.has(judge.id))
                .map((judge) => (
                <TableCell
                  key={judge.id}
                  sx={{
                    width: "70px",
                    textAlign: "center",
                    whiteSpace: "normal",
                    wordBreak: "break-word",
                    padding: "8px 4px",
                    overflow: "hidden"
                  }}
                >
                  <Typography variant="body2" sx={{ lineHeight: 1.3, fontSize: "0.8rem" }}>
                    {judge.name}
                  </Typography>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>

          <TableBody>
            {paginatedResults.map((result) => {
              const aggregatedAccuracy = result.aggregated_accuracy;
              const metadataEntries = aggregatedAccuracy?.metadata ?? [];

              // Parse evaluator labels for this result
              const evaluatorLabels = parseEvaluatorData(metadataEntries);
              const evaluatorMap = new Map(
                evaluatorLabels.map((e) => [e.name, e.label])
              );

              // Determine chip label - use override if edited, otherwise calculate from evaluators
              let chipLabel = "No data";
              let chipColor: ChipProps["color"] = "default";
              let helperText: string | null = null;

              // If label was manually edited, use the aggregated label directly
              if (aggregatedAccuracy?.is_edited && aggregatedAccuracy.label !== null) {
                chipLabel = aggregatedAccuracy.label ? "Accurate" : "Inaccurate";
                chipColor = aggregatedAccuracy.label ? "success" : "error";
              } else if (selectedJudges.size === 0) {
                chipLabel = "No evaluators selected";
                chipColor = "warning";
                helperText = "Please select at least one evaluator.";
              } else {
                // Get labels from selected judges only
                const selectedLabels: boolean[] = [];
                reliableJudges.forEach((judge) => {
                  if (selectedJudges.has(judge.id)) {
                    const label = evaluatorMap.get(judge.name);
                    if (label !== null && label !== undefined) {
                      selectedLabels.push(label);
                    }
                  }
                });

                if (selectedLabels.length === 0) {
                  chipLabel = "No data";
                  chipColor = "default";
                } else {
                  // Count accurate vs inaccurate
                  const accurateCount = selectedLabels.filter((l) => l === true).length;
                  const inaccurateCount = selectedLabels.filter((l) => l === false).length;

                  if (accurateCount > inaccurateCount) {
                    chipLabel = "Accurate";
                    chipColor = "success";
                  } else if (inaccurateCount > accurateCount) {
                    chipLabel = "Inaccurate";
                    chipColor = "error";
                  } else {
                    // Tie
                    chipLabel = "Tie";
                    chipColor = "warning";
                    helperText = "Equal votes for accurate and inaccurate.";
                  }
                }
              }

              const isExpanded = expandedRows.has(result.answer_id);

              return (
                <React.Fragment key={result.answer_id}>
                  <TableRow hover>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => toggleRow(result.answer_id)}
                        aria-label="expand row"
                      >
                        {isExpanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                      </IconButton>
                    </TableCell>

                    <TableCell>
                      <Typography variant="subtitle2">
                        {truncate(result.question_text ?? "", 160)}
                      </Typography>
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {truncate(result.answer_content, 160)}
                      </Typography>
                    </TableCell>

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

                    {reliableJudges
                      .filter((judge) => selectedJudges.has(judge.id))
                      .map((judge) => {
                      const label = evaluatorMap.get(judge.name);

                      return (
                        <TableCell key={judge.id} align="center">
                          {label === true ? (
                            <CheckCircleIcon color="success" fontSize="small" />
                          ) : label === false ? (
                            <CancelIcon color="error" fontSize="small" />
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              --
                            </Typography>
                          )}
                        </TableCell>
                      );
                    })}
                  </TableRow>

                  <TableRow>
                    <TableCell style={{ padding: 0 }} colSpan={4 + selectedJudges.size}>
                      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                        <ResultsTableExpandedRow
                          result={result}
                          reliableJudges={reliableJudges}
                          selectedJudgeIds={Array.from(selectedJudges)}
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
