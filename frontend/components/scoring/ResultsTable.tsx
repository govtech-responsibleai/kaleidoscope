"use client";

import React, { useState, useMemo } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  ChipProps,
  Collapse,
  Divider,
  FormControlLabel,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Paper,
  Select,
  SelectChangeEvent,
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
  FilterList as FilterListIcon,
} from "@mui/icons-material";
import { ResultRow, JudgeConfig } from "@/lib/types";
import { metricsApi } from "@/lib/api";
import ResultsTableExpandedRow from "./ResultsTableExpandedRow";

interface ResultsTableProps {
  results: ResultRow[];
  snapshotId: number;
  judges: JudgeConfig[];
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
}: ResultsTableProps) {
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const [labelFilter, setLabelFilter] = useState<"all" | "accurate" | "inaccurate">("all");
  const [labelFilterAnchor, setLabelFilterAnchor] = useState<HTMLElement | null>(null);
  const [showDisagreementsOnly, setShowDisagreementsOnly] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedJudges, setSelectedJudges] = useState<Set<number>>(new Set());

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

  // Filter results based on selected filters
  const filteredResults = useMemo(() => {
    let filtered = results;

    // Filter by label
    if (labelFilter !== "all") {
      filtered = filtered.filter((result) => {
        const metadata = result.aggregated_accuracy?.metadata ?? [];
        const labels = extractReliableLabels(metadata);
        const inaccurateCount = labels.filter((l) => l === false).length;
        const accurateCount = labels.filter((l) => l === true).length;

        if (labelFilter === "inaccurate") {
          return inaccurateCount > accurateCount;
        } else {
          return accurateCount > inaccurateCount;
        }
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
  }, [results, labelFilter, showDisagreementsOnly]);

  const paginatedResults = useMemo(() => {
    return filteredResults.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
  }, [filteredResults, page]);

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
      const response = await metricsApi.exportCSV(snapshotId);

      // Create download link
      const blob = new Blob([response.data], { type: "text/csv" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `snapshot_${snapshotId}_aggregated_results.csv`;
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

  const handleJudgeSelectionChange = (event: SelectChangeEvent<number[]>) => {
    const value = event.target.value;
    setSelectedJudges(new Set(typeof value === "string" ? [] : value));
  };

  // Get display text for selected judges
  const getSelectedJudgesDisplay = () => {
    return `Evaluators (${selectedJudges.size}/${reliableJudges.length})`;
  };

  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="h5">All Questions & Answers</Typography>

        <Box sx={{ flexGrow: 1 }} />

        <Box
          sx={{
            border: 1,
            borderColor: "rgba(0, 0, 0, 0.23)",
            borderRadius: 1,
            pr: 1.5,
            display: "flex",
            alignItems: "center",
          }}
        >
          <FormControlLabel
            control={
              <Checkbox
                size="small"
                checked={showDisagreementsOnly}
                onChange={(event) => {
                  setPage(0);
                  setShowDisagreementsOnly(event.target.checked);
                }}
              />
            }
            label={<Typography variant="body2">Show only disagreements</Typography>}
            sx={{ m: 0 }}
          />
        </Box>

        <Select
          multiple
          value={Array.from(selectedJudges)}
          onChange={handleJudgeSelectionChange}
          displayEmpty
          renderValue={() => getSelectedJudgesDisplay()}
          sx={{
            minWidth: 160,
          }}
          size="small"
        >
          {reliableJudges.map((judge) => (
            <MenuItem key={judge.id} value={judge.id}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={selectedJudges.has(judge.id)}
                    onChange={(event) => {
                      setSelectedJudges((prev) => {
                        const next = new Set(prev);
                        if (event.target.checked) {
                          next.add(judge.id);
                        } else {
                          next.delete(judge.id);
                        }
                        return next;
                      });
                    }}
                  />
                }
                label={judge.name}
              />
            </MenuItem>
          ))}
        </Select>

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
        <Table size="small" sx={{ tableLayout: "fixed" }}>

          <TableHead>
            <TableRow>
              <TableCell sx={{ width: "5%" }} />
              <TableCell sx={{ width: "35%" }}>Question</TableCell>
              <TableCell sx={{ width: "35%" }}>Answer</TableCell>
              <TableCell sx={{ width: "100px" }}>
                <Stack direction="row" alignItems="center" spacing={0.5}>
                  <Typography variant="body2" fontWeight={600}>
                    Label
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={(e) => setLabelFilterAnchor(e.currentTarget)}
                    sx={{
                      p: 0.25,
                      color: labelFilter !== "all" ? "primary.main" : "action.active",
                    }}
                  >
                    <FilterListIcon fontSize="small" />
                  </IconButton>
                </Stack>
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

              // Calculate majority vote based on selected judges
              let chipLabel = "No data";
              let chipColor: ChipProps["color"] = "default";
              let helperText: string | null = null;

              if (selectedJudges.size === 0) {
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

              const isQuestionTruncated = result.question_text.length > 160;
              const isAnswerTruncated = result.answer_content.length > 160;
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
                        {truncate(result.question_text, 160)}
                      </Typography>
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {truncate(result.answer_content, 160)}
                      </Typography>
                    </TableCell>

                    <TableCell>
                      <Stack spacing={0.5}>
                        <Chip label={chipLabel} color={chipColor} size="small" />
                        {helperText && (
                          <Typography variant="caption" color="text.secondary">
                            {helperText}
                          </Typography>
                        )}
                      </Stack>
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

      {/* Label filter menu */}
      <Menu
        anchorEl={labelFilterAnchor}
        open={Boolean(labelFilterAnchor)}
        onClose={() => setLabelFilterAnchor(null)}
      >
        <MenuItem
          selected={labelFilter === "all"}
          onClick={() => {
            setLabelFilter("all");
            setPage(0);
            setLabelFilterAnchor(null);
          }}
        >
          All
        </MenuItem>
        <MenuItem
          selected={labelFilter === "accurate"}
          onClick={() => {
            setLabelFilter("accurate");
            setPage(0);
            setLabelFilterAnchor(null);
          }}
        >
          <ListItemIcon>
            <CheckCircleIcon fontSize="small" color="success" />
          </ListItemIcon>
          Accurate
        </MenuItem>
        <MenuItem
          selected={labelFilter === "inaccurate"}
          onClick={() => {
            setLabelFilter("inaccurate");
            setPage(0);
            setLabelFilterAnchor(null);
          }}
        >
          <ListItemIcon>
            <CancelIcon fontSize="small" color="error" />
          </ListItemIcon>
          Inaccurate
        </MenuItem>
      </Menu>
    </Box>
  );
}
