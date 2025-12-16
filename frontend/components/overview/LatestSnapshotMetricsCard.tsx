"use client";

import React from "react";
import {
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Divider,
  Stack,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
} from "@mui/icons-material";
import { SnapshotMetric } from "@/lib/types";

interface LatestSnapshotMetricsCardProps {
  latestSnapshot: SnapshotMetric | null;
  loading: boolean;
}

export default function LatestSnapshotMetricsCard({
  latestSnapshot,
  loading,
}: LatestSnapshotMetricsCardProps) {
  if (loading) {
    return (
      <Card variant="outlined" sx={{ flex: "0 0 40%", height: "100%"  }}>
        <CardContent>
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            minHeight="150px"
          >
            <CircularProgress />
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (!latestSnapshot) {
    return (
      <Card variant="outlined" sx={{ height: "100%", flex: "0 0 40%" }}>
        <CardContent>
          <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
            Latest Snapshot
          </Typography>
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            minHeight="150px"
          >
            <Typography variant="body2" color="text.secondary">
              No snapshots yet
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const accuracyPercentage = (latestSnapshot.aggregated_accuracy * 100).toFixed(
    1
  );

  return (
    <Card variant="outlined" sx={{ width: "35%", height: "100%", minHeight: "150px" }}>
      <CardContent>
        <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
          Latest Snapshot
        </Typography>

        <Stack direction="row" gap={2} alignItems={"center"} justifyContent={"space-between"} >

          <Box>
            <Typography variant="h4" fontWeight={600} color="primary.main">
              {accuracyPercentage}%
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Accuracy on {latestSnapshot.total_answers} target responses
            </Typography>
          </Box>

            {!latestSnapshot.has_aligned_judges ? (
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  mt: 1,
                  px: 2.5,
                  py: 2,
                  border: "1px solid",
                  borderColor: "warning.main",
                  borderRadius: 2,
                }}
              >
                <WarningIcon color="warning" fontSize="small" />
                <Box>
                  <Typography variant="body2" fontWeight={500}>
                    Evaluation to be improved
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    No aligned judges found
                  </Typography>
                </Box>
              </Box>
            ) : latestSnapshot.judge_alignment_range ? (
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  mt: 1,
                  px: 2.5,
                  py: 2,
                  border: "1px solid",
                  borderColor: "success.main",
                  borderRadius: 2,
                }}
              >
                <CheckCircleIcon color="success" fontSize="small" />
                <Box>
                  <Typography variant="body2" fontWeight={500}>
                    {latestSnapshot.reliable_judge_count} reliable evaluator{latestSnapshot.reliable_judge_count !== 1 ? 's' : ''} found
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {(latestSnapshot.judge_alignment_range.min * 100).toFixed(0)}
                    % - {(latestSnapshot.judge_alignment_range.max * 100).toFixed(0)}
                    % reliability
                  </Typography>
                </Box>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                No judge alignment data
              </Typography>
            )}

        </Stack>
      </CardContent>
    </Card>
  );
}
