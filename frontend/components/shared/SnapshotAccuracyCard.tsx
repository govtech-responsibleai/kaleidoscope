"use client";

import {
  Box,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import { IconAlertTriangle } from "@tabler/icons-react";
import { SnapshotMetric } from "@/lib/types";
import AccuracyGauge from "@/components/shared/AccuracyGauge";
import { statusIconProps } from "@/lib/iconStyles";

interface SnapshotAccuracyCardProps {
  snapshotMetric: SnapshotMetric | null;
  loading: boolean;
  emptyMessage?: string;
  showExplanatoryText?: boolean;
  showWarningBox?: boolean;
  title?: string;
  gaugeLabel?: string;
}

export default function SnapshotAccuracyCard({
  snapshotMetric,
  loading,
  emptyMessage = "No data available",
  showExplanatoryText = false,
  showWarningBox = false,
  title = "Overall Accuracy",
  gaugeLabel = "Aggregated Accuracy Score",
}: SnapshotAccuracyCardProps) {
  if (loading) {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
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
      <Box sx={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
        <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
          {title}
        </Typography>
        <Typography variant="h2" fontWeight={700} color="text.disabled">
          --%
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {emptyMessage}
        </Typography>
      </Box>
    );
  }

  const hasReliableJudges = snapshotMetric.aligned_judges.length > 0;
  const reliableJudgeCount = snapshotMetric.aligned_judges.length;
  const alignmentRange = snapshotMetric.judge_alignment_range;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        {title}
      </Typography>

      <AccuracyGauge
        value={hasReliableJudges ? snapshotMetric.aggregated_accuracy : null}
        size={300}
        label={gaugeLabel}
      />

      <Stack spacing={0.5} alignItems="center" sx={{ mt: 1 }}>
        {hasReliableJudges && alignmentRange ? (
          <Typography variant="body2" color="text.secondary" textAlign="center">
            from {reliableJudgeCount} judge{reliableJudgeCount !== 1 ? "s" : ""}{" "}
            <Box
              component="span"
              sx={{ color: "success.main", fontWeight: 500 }}
            >
              ({(alignmentRange.min * 100).toFixed(0)}%-{(alignmentRange.max * 100).toFixed(0)}% reliability)
            </Box>
          </Typography>
        ) : showWarningBox ? (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              px: 2,
              py: 1,
              border: "1px solid",
              borderColor: "warning.main",
              borderRadius: 2,
            }}
          >
            <IconAlertTriangle {...statusIconProps} color="currentColor" />
            <Box>
              <Typography variant="body2" fontWeight={500}>
                Evaluation to be improved
              </Typography>
              <Typography variant="caption" color="text.secondary">
                No aligned judges found
              </Typography>
            </Box>
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No reliable judges yet
          </Typography>
        )}

        {snapshotMetric.edited_count > 0 && (
          <Typography color="info.main" sx={{ fontStyle: "italic", fontSize: "0.7rem" }}>
            ({snapshotMetric.edited_count} of {snapshotMetric.total_answers} labels manually edited)
          </Typography>
        )}
      </Stack>

      {showExplanatoryText && (
        <Typography
          variant="caption"
          color="text.secondary"
          textAlign="center"
          sx={{ mt: 2, maxWidth: 350 }}
        >
          Accuracy is calculated from the labels in the results table below. Labels are aggregated across reliable judges but can be manually edited.
        </Typography>
      )}
    </Box>
  );
}
