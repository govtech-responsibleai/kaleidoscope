"use client";

import React from "react";
import {
  Typography,
  Box,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from "@mui/material";
import { ConfusionMatrix } from "@/lib/types";

interface ConfusionMatrixCardProps {
  data: ConfusionMatrix | null;
  loading: boolean;
}

export default function ConfusionMatrixCard({
  data,
  loading,
}: ConfusionMatrixCardProps) {
  if (loading) {
    return (
      <Box>
        <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
          Inaccurate Responses by Question Type
        </Typography>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="200px"
        >
          <CircularProgress />
        </Box>
      </Box>
    );
  }

  if (!data || data.total_inaccurate === 0) {
    return (
      <Box>
        <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
          Inaccurate Responses by Question Type
        </Typography>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="200px"
        >
          <Typography variant="body2" color="text.secondary">
            {data ? "No inaccurate responses found" : "No data available"}
          </Typography>
        </Box>
      </Box>
    );
  }

  const maxValue = Math.max(
    data.matrix.typical_in_kb,
    data.matrix.typical_out_kb,
    data.matrix.edge_in_kb,
    data.matrix.edge_out_kb
  );

  const getCellColor = (value: number) => {
    if (value === 0) return "transparent";
    const intensity = value / maxValue;
    return `rgba(244, 51,61, ${intensity * 0.8})`;
  };
  return (
    <Box>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 600, bgcolor: "grey.50" }}>
                Type / Scope
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 600, bgcolor: "grey.50" }}>
                In Knowledge Base
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 600, bgcolor: "grey.50" }}>
                Out of Knowledge Base
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>Typical</TableCell>
              <TableCell
                align="center"
                sx={{
                  bgcolor: getCellColor(data.matrix.typical_in_kb),
                  fontWeight: 500,
                }}
              >
                {data.matrix.typical_in_kb}
              </TableCell>
              <TableCell
                align="center"
                sx={{
                  bgcolor: getCellColor(data.matrix.typical_out_kb),
                  fontWeight: 500,
                }}
              >
                {data.matrix.typical_out_kb}
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>Edge Case</TableCell>
              <TableCell
                align="center"
                sx={{
                  bgcolor: getCellColor(data.matrix.edge_in_kb),
                  fontWeight: 500,
                }}
              >
                {data.matrix.edge_in_kb}
              </TableCell>
              <TableCell
                align="center"
                sx={{
                  bgcolor: getCellColor(data.matrix.edge_out_kb),
                  fontWeight: 500,
                }}
              >
                {data.matrix.edge_out_kb}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 2, textAlign: "center" }}>
        <Typography fontWeight={600}>
          Breakdown of Inaccurate Responses
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Total inaccurate responses: <strong>{data.total_inaccurate}</strong>
        </Typography>
      </Box>
    </Box>
  );
}
