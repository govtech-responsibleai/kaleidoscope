"use client";

import React, { useState, useMemo } from "react";
import {
  Box,
  Button,
  Checkbox,
  Chip,
  ChipProps,
  FormControlLabel,
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
} from "@mui/material";
import { Download as DownloadIcon } from "@mui/icons-material";
import { ResultRow } from "@/lib/types";
import { metricsApi } from "@/lib/api";

interface ResultsTableProps {
  results: ResultRow[];
  snapshotId: number;
}

const extractReliableLabels = (metadata: string[]) => {
  const labels: boolean[] = [];
  metadata.forEach((entry) => {
    const lower = entry.toLowerCase();
    if (lower.includes("excluded")) {
      return;
    }
    if (lower.includes("accurate")) {
      labels.push(true);
      return;
    }
    if (lower.includes("inaccurate")) {
      labels.push(false);
    }
  });
  return labels;
};

const truncate = (value: string, length: number) => {
  if (!value) return "";
  return value.length > length ? `${value.slice(0, length)}…` : value;
};

export default function ResultsTable({
  results,
  snapshotId,
}: ResultsTableProps) {
  const [page, setPage] = useState(0);
  const [showDisagreementsOnly, setShowDisagreementsOnly] = useState(false);
  const [exporting, setExporting] = useState(false);

  const rowsPerPage = 10;

  // Filter results for disagreements
  const filteredResults = useMemo(() => {
    if (!showDisagreementsOnly) {
      return results;
    }

    return results.filter((result) => {
      const metadata = result.aggregated_accuracy?.metadata ?? [];
      const labels = extractReliableLabels(metadata);
      const unique = new Set(labels);
      return unique.size > 1;
    });
  }, [results, showDisagreementsOnly]);

  const paginatedResults = useMemo(() => {
    return filteredResults.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
  }, [filteredResults, page]);

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
  
  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1.5 }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={showDisagreementsOnly}
              onChange={(event) => {
                setPage(0);
                setShowDisagreementsOnly(event.target.checked);
              }}
            />
          }
          label="Show only disagreements"
        />

        <Box sx={{ flexGrow: 1 }} />

        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleExport}
          disabled={exporting}
        >
          {exporting ? "Exporting..." : "Export CSV"}
        </Button>
      </Stack>

      <TableContainer component={Paper} sx={{ boxShadow: "none" }}>
        <Table size="small">

          <TableHead>
            <TableRow>
              <TableCell sx={{ width: "35%" }}>Question</TableCell>
              <TableCell sx={{ width: "35%" }}>Answer</TableCell>
              <TableCell sx={{ width: "10%" }}>Accuracy</TableCell>
              <TableCell sx={{ width: "20%" }}>Metadata</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {paginatedResults.map((result) => {
              const aggregatedAccuracy = result.aggregated_accuracy;
              const metadataEntries = aggregatedAccuracy?.metadata ?? [];

              let chipLabel = "No data";
              let chipColor: ChipProps["color"] = "default";
              let helperText: string | null = null;

              if (!aggregatedAccuracy) {
                chipLabel = "No data";
              } else {
                switch (aggregatedAccuracy.method) {
                  case "majority":
                    if (aggregatedAccuracy.label === null) {
                      chipLabel = "Pending";
                      chipColor = "default";
                    } else {
                      chipLabel = aggregatedAccuracy.label ? "Accurate" : "Inaccurate";
                      chipColor = aggregatedAccuracy.label ? "success" : "error";
                    }
                    break;
                  case "no_aligned_judge":
                    chipLabel = "No reliable judges";
                    chipColor = "warning";
                    helperText = "Please annotate more samples or swap out the judges.";
                    break;
                  case "majority_tied":
                    chipLabel = "Tie";
                    chipColor = "warning";
                    helperText = "Please annotate more samples or add more judges.";
                    break;
                  default:
                    chipLabel = "No data";
                }
              }

              return (
                <TableRow key={result.answer_id} hover>

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

                  <TableCell>
                    {metadataEntries.length === 0 ? (
                      <Typography variant="caption" color="text.secondary">
                        No metadata
                      </Typography>
                    ) : (
                      <Stack spacing={0.25}>
                        {metadataEntries.map((entry, idx) => (
                          <Typography
                            key={`${result.answer_id}-metadata-${idx}`}
                            variant="caption"
                          >
                            {entry}
                          </Typography>
                        ))}
                      </Stack>
                    )}
                  </TableCell>
                </TableRow>
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
