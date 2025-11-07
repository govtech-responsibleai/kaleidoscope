"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  CircularProgress,
} from "@mui/material";
import { useParams } from "next/navigation";
import { targetApi } from "@/lib/api";
import { TargetResponse, TargetStats } from "@/lib/types";
import DocumentList from "@/components/DocumentList";

export default function TargetOverview() {
  const params = useParams();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [documentRefreshKey, setDocumentRefreshKey] = useState(0);

  const fetchData = async () => {
    try {
      const [targetRes, statsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetId]);

  const mockAccuracy = stats ? 85.3 : 0;

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="30vh">
        <CircularProgress />
      </Box>
    );
  }

  if (!target || !stats) {
    return null;
  }

  const totalPersonas = Object.values(stats.personas).reduce((a, b) => a + b, 0);
  const totalQuestions = Object.values(stats.questions).reduce((a, b) => a + b, 0);

  return (
    <Box>
      {/* Target Details and Knowledge Base Documents - Side by Side */}
      <Box sx={{ display: "flex", gap: 3, mb: 3, flexDirection: { xs: "column", md: "row" } }}>
        <Card sx={{ flex: { md: "0 0 55%" }, height: "350px" }}>
          <CardContent>
            <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
              Target Details
            </Typography>
            <Box sx={{ display: "flex", gap: 2 }}>
              <Box sx={{ flex: 1 }}>
                <Box mb={2}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Purpose
                  </Typography>
                  <Typography variant="body2">{target.purpose || "N/A"}</Typography>
                </Box>
                <Box mb={2}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Target Users
                  </Typography>
                  <Typography variant="body2">{target.target_users || "N/A"}</Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">
                    API Endpoint
                  </Typography>
                  <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                    {target.api_endpoint || "N/A"}
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ flex: 1, textAlign: "right" }}>
                <Box mb={2}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Agency
                  </Typography>
                  <Typography variant="body2">{target.agency || "N/A"}</Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">
                    Created At
                  </Typography>
                  <Typography variant="body2">
                    {new Date(target.created_at).toLocaleDateString()}
                  </Typography>
                </Box>
              </Box>
            </Box>
          </CardContent>
        </Card>
        <Card sx={{ flex: { md: "0 0 calc(45% - 24px)" }, height: "350px", display: "flex", flexDirection: "column" }}>
          <CardContent sx={{ flexGrow: 1, display: "flex", flexDirection: "column", overflow: "hidden", pb: 2 }}>
            <DocumentList
              key={documentRefreshKey}
              targetId={targetId}
              hideUploadButton={true}
              maxHeight="260px"
            />
          </CardContent>
        </Card>
      </Box>

      {/* Statistics Cards */}
      <Box sx={{ display: "flex", gap: 3, flexDirection: { xs: "column", sm: "row" } }}>
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Accuracy
            </Typography>
            <Typography variant="h4" fontWeight={600}>
              {mockAccuracy}%
            </Typography>
            <Typography variant="caption" color="text.secondary">
              (Mocked)
            </Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Personas
            </Typography>
            <Typography variant="h4" fontWeight={600}>
              {totalPersonas}
            </Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Questions
            </Typography>
            <Typography variant="h4" fontWeight={600}>
              {totalQuestions}
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
