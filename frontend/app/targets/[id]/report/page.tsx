"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Divider,
  Typography,
  CircularProgress,
  Button,
  Stack,
  Select,
  MenuItem,
  useTheme,
} from "@mui/material";
import {
  Person as PersonIcon,
  QuestionMark as QuestionMarkIcon,
  ScreenshotMonitor as ScreenshotMonitorIcon,
  SmartToy as SmartToyIcon,
  Download as DownloadIcon
} from "@mui/icons-material";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { targetApi, snapshotApi, judgeApi, metricsApi } from "@/lib/api";
import { TargetResponse, TargetStats, SnapshotMetric, ConfusionMatrix, Snapshot } from "@/lib/types";
import SnapshotAccuracyChart from "@/components/overview/SnapshotAccuracyChart";
import SelectedSnapshotMetricsCard from "@/components/overview/SelectedSnapshotMetricsCard";
import ConfusionMatrixCard from "@/components/overview/ConfusionMatrixCard";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

export default function TargetReport() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const theme = useTheme();
  const targetId = parseInt(params.id as string);
  const [metric, setMetric] = useState<string>("accuracy");

  // Initialize from URL if available
  const snapshotIdFromUrl = searchParams.get("snapshot");
  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(
    snapshotIdFromUrl ? Number(snapshotIdFromUrl) : null
  );
  const [judgeCount, setJudgeCount] = useState(0);
  const [snapshotMetrics, setSnapshotMetrics] = useState<SnapshotMetric[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [confusionMatrix, setConfusionMatrix] = useState<ConfusionMatrix | null>(null);
  const [confusionMatrixLoading, setConfusionMatrixLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [targetRes, statsRes, snapshotsRes, judgesRes, metricsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
        snapshotApi.list(targetId),
        judgeApi.list(targetId),
        metricsApi.getSnapshotMetrics(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
      setSnapshots(snapshotsRes.data);
      setJudgeCount(judgesRes.data.length);
      setSnapshotMetrics(metricsRes.data.snapshots);

      // Select the most recent snapshot if none selected
      if (!selectedSnapshotId && snapshotsRes.data.length > 0) {
        const mostRecent = [...snapshotsRes.data].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )[0];
        setSelectedSnapshotId(mostRecent.id);
        // Update URL with default selection
        const newSearchParams = new URLSearchParams(searchParams.toString());
        newSearchParams.set("snapshot", mostRecent.id.toString());
        router.push(`/targets/${targetId}/report?${newSearchParams.toString()}`, { scroll: false });
      }
    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
      setMetricsLoading(false);
    }
  };

  const fetchConfusionMatrix = async (snapshotId?: number) => {
    setConfusionMatrixLoading(true);
    try {
      const res = await metricsApi.getConfusionMatrix(targetId, snapshotId);
      setConfusionMatrix(res.data);
    } catch (error) {
      console.error("Failed to fetch confusion matrix:", error);
      setConfusionMatrix(null);
    } finally {
      setConfusionMatrixLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetId]);

  useEffect(() => {
    if (selectedSnapshotId) {
      fetchConfusionMatrix(selectedSnapshotId);
    }
  }, [selectedSnapshotId]);

  const handleSelectSnapshot = (snapshotId: number) => {
    setSelectedSnapshotId(snapshotId);
    // Update URL to persist selection across tab switches
    const newSearchParams = new URLSearchParams(searchParams.toString());
    newSearchParams.set("snapshot", snapshotId.toString());
    router.push(`/targets/${targetId}/report?${newSearchParams.toString()}`, { scroll: false });
  };

  const handleSnapshotCreated = async () => {
    await fetchData();
  };

  // Get the metric for the selected snapshot
  const selectedSnapshotMetric = snapshotMetrics.find(
    (m) => m.snapshot_id === selectedSnapshotId
  ) || null;

  const handleDownloadReport = async () => {
    setDownloading(true);
    try {
      const element = document.getElementById('report-content');
      if (!element) throw new Error('Report content not found');

      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
      });

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');

      // Define margins (in mm)
      const margin = 10;
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const contentWidth = pageWidth - (margin * 2);
      const contentHeight = (canvas.height * contentWidth) / canvas.width;

      // Handle multi-page if needed
      let heightLeft = contentHeight;
      let position = margin;

      pdf.addImage(imgData, 'PNG', margin, position, contentWidth, contentHeight);
      heightLeft -= (pageHeight - margin * 2);

      while (heightLeft > 0) {
        position = -(contentHeight - heightLeft) + margin;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', margin, position, contentWidth, contentHeight);
        heightLeft -= (pageHeight - margin * 2);
      }

      pdf.save(`${target?.name || 'target'}_report_${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (error) {
      console.error('Failed to generate report:', error);
      alert('Failed to generate report. Please try again.');
    } finally {
      setDownloading(false);
    }
  };


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

  const approvedPersonas = stats.personas.approved || 0;
  const approvedQuestions = stats.questions.approved || 0;

  return (
    <Box>
      {/* Header with Download Report Button */}
      <Box sx={{ display: "flex", justifyContent: "flex-end", alignItems: "center", mb: 3 }}>
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleDownloadReport}
          disabled={downloading || loading}
          sx={{ bgcolor: theme.palette.secondary.main }}
        >
          {downloading ? "Generating PDF..." : "Download Report"}
        </Button>
      </Box>

      {/* Report Content */}
      <Box id="report-content">
        {/* Stats Cards (2x2) and Target Details Side by Side */}
        <Box sx={{ display: "flex", gap: 3, mb: 3, flexDirection: { xs: "column", md: "row" } }}>
          {/* Target Details */}
          <Card variant="outlined" sx={{ flex: { md: "0 0 calc(45% - 24px)" }, height: "300px" }}>
            <CardContent>
              <Box sx={{ mb: 2 }}>
                <Typography variant="h6" fontWeight={600}>
                  Target Details
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                  Last updated: {new Date(target.updated_at).toLocaleDateString()}
                </Typography>
              </Box>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ minWidth: "100px" }}>
                    Agency:
                  </Typography>
                  <Typography variant="body2">{target.agency || "N/A"}</Typography>
                </Box>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ minWidth: "100px" }}>
                    Purpose:
                  </Typography>
                  <Typography variant="body2">{target.purpose || "N/A"}</Typography>
                </Box>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ minWidth: "100px" }}>
                    Target Users:
                  </Typography>
                  <Typography variant="body2">{target.target_users || "N/A"}</Typography>
                </Box>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ minWidth: "100px" }}>
                    API Endpoint:
                  </Typography>
                  <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                    {target.api_endpoint || "N/A"}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Statistics Cards - 2x2 Grid */}
          <Box
            sx={{
              display: "grid",
              gap: 2,
              gridTemplateColumns: "repeat(2, 1fr)",
              flex: { md: "0 0 55%" },
            }}
          >
            <Card variant="outlined">
              <CardContent>
                <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                  <PersonIcon fontSize="small" sx={{ opacity: 0.5 }}/>
                  <Typography variant="subtitle2" color="text.secondary">
                    Approved Personas
                  </Typography>
                </Stack>
                <Typography variant="h4" fontWeight={600}>
                  {approvedPersonas}
                </Typography>
              </CardContent>
            </Card>

            <Card variant="outlined">
              <CardContent>
                <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                  <QuestionMarkIcon fontSize="small" sx={{ opacity: 0.5 }}/>
                  <Typography variant="subtitle2" color="text.secondary">
                    Approved Questions
                  </Typography>
                </Stack>
                <Typography variant="h4" fontWeight={600}>
                  {approvedQuestions}
                </Typography>
              </CardContent>
            </Card>

            <Card variant="outlined">
              <CardContent>
                <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                  <ScreenshotMonitorIcon fontSize="small" sx={{ opacity: 0.5 }}/>
                  <Typography variant="subtitle2" color="text.secondary">
                    Snapshots
                  </Typography>
                </Stack>
                <Typography variant="h4" fontWeight={600}>
                  {snapshots.length}
                </Typography>
              </CardContent>
            </Card>

            <Card variant="outlined">
              <CardContent>
                <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                  <SmartToyIcon fontSize="small" sx={{ opacity: 0.5 }}/>
                  <Typography variant="subtitle2" color="text.secondary">
                    Judges
                  </Typography>
                </Stack>
                <Typography variant="h4" fontWeight={600}>
                  {judgeCount}
                </Typography>
              </CardContent>
            </Card>
          </Box>

        </Box>

        <Select
          value={metric}
          onChange={(e) => {
            setMetric(e.target.value);
          }}
          size="small"
          disabled={snapshotMetrics.length === 0}
          sx={{ mb: 1, minWidth: 200 }}
        >
          <MenuItem value={"accuracy"}>Accuracy</MenuItem>
        </Select>

        {/* Snapshot Accuracy Chart and Snapshot Details */}
        <Box sx={{ mb: 3 }}>
          <Stack direction="row" spacing={3} alignItems="stretch">
            <SnapshotAccuracyChart
              data={snapshotMetrics}
              loading={metricsLoading}
            />

            {/* Snapshot Details Section */}
            <Card variant="outlined" sx={{ width: "35%" }}>
              <CardContent>
                {/* Snapshot Selection Header */}
                <Stack direction={"row"} gap={2}>
                  <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
                    Snapshot:
                  </Typography>
                  <Box sx={{ flexGrow: 1 }}>
                    <SnapshotHeader
                      targetId={targetId}
                      snapshots={snapshots}
                      selectedSnapshotId={selectedSnapshotId}
                      onSelectSnapshot={handleSelectSnapshot}
                      onSnapshotCreated={handleSnapshotCreated}
                      loading={loading}
                    />
                  </Box>
                </Stack>

                {/* Snapshot Metrics Card */}
                {metricsLoading ? (
                  <Card variant="outlined" sx={{ flex: 1 }}>
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
                ) : !selectedSnapshotMetric ? (
                  <Card variant="outlined" sx={{ flex: 1 }}>
                    <CardContent>
                      <Box
                        display="flex"
                        justifyContent="center"
                        alignItems="center"
                        minHeight="150px"
                      >
                        <Typography variant="body2" color="text.secondary">
                          No snapshot data available
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                ) : (
                  <SelectedSnapshotMetricsCard
                    latestSnapshot={selectedSnapshotMetric}
                    loading={false}
                  />
                )}

                <Divider sx={{ my: 3 }} />

                {/* Confusion Matrix Card */}
                <ConfusionMatrixCard
                  data={confusionMatrix}
                  loading={confusionMatrixLoading}
                />
                
              </CardContent>
            </Card>
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}
