"use client";

import React from "react";
import {
  Box,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import { SnapshotMetric } from "@/lib/types";
import AccuracyGauge from "@/components/shared/AccuracyGauge";

interface AggregatedAccuracyCardProps {
  snapshotMetric: SnapshotMetric | null;
  loading: boolean;
}

export default function AggregatedAccuracyCard({
  snapshotMetric,
  loading,
}: AggregatedAccuracyCardProps) {
  if (loading) {
    return (
      <Box sx={{ minWidth: 400, p: 2, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="160px"
        >
          <CircularProgress />
        </Box>
      </Box>
    );
  }

  if (!snapshotMetric) {
    return (
      <Box sx={{ minWidth: 400, p: 2, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
        <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
          Overall Accuracy
        </Typography>
        <Typography variant="h2" fontWeight={700} color="text.disabled">
          --%
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Run evaluators to see results
        </Typography>
      </Box>
    );
  }

  const hasReliableJudges = snapshotMetric.has_aligned_judges;
  const reliableJudgeCount = snapshotMetric.reliable_judge_count;
  const alignmentRange = snapshotMetric.judge_alignment_range;

  return (
    <Box sx={{ minWidth: 400, p: 2, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        Overall Accuracy
      </Typography>

      <AccuracyGauge
        value={snapshotMetric.aggregated_accuracy}
        size={300}
        label="Aggregated Accuracy Score"
      />

      <Stack spacing={0.5} alignItems="center" sx={{ mt: 1 }}>
        {hasReliableJudges && alignmentRange ? (
          <Typography variant="body2" color="text.secondary" textAlign="center">
            from {reliableJudgeCount} evaluator{reliableJudgeCount !== 1 ? "s" : ""}{" "}
            <Box
              component="span"
              sx={{ color: "success.main", fontWeight: 500 }}
            >
              ({(alignmentRange.min * 100).toFixed(0)}%-{(alignmentRange.max * 100).toFixed(0)}% reliability)
            </Box>
          </Typography>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No reliable evaluators yet
          </Typography>
        )}
      </Stack>
    </Box>
  );
}
