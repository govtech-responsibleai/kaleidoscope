"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Stack,
  TextField,
  Grid,
} from "@mui/material";
import {
  Edit as EditIcon,
  Person as PersonIcon,
  QuestionMark as QuestionMarkIcon,
  ScreenshotMonitor as ScreenshotMonitorIcon,
  SmartToy as SmartToyIcon,
  Download as DownloadIcon
} from "@mui/icons-material";
import { useParams } from "next/navigation";
import { targetApi, snapshotApi, judgeApi, metricsApi } from "@/lib/api";
import { TargetResponse, TargetStats, TargetUpdate, EndpointType, SnapshotMetric } from "@/lib/types";
import DocumentList from "@/components/overview/DocumentList";
import SnapshotAccuracyChart from "@/components/overview/SnapshotAccuracyChart";
import LatestSnapshotMetricsCard from "@/components/overview/LatestSnapshotMetricsCard";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

export default function TargetOverview() {
  const params = useParams();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [documentRefreshKey, setDocumentRefreshKey] = useState(0);
  const [editOpen, setEditOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editForm, setEditForm] = useState<TargetUpdate>({});
  const [snapshotCount, setSnapshotCount] = useState(0);
  const [judgeCount, setJudgeCount] = useState(0);
  const [snapshotMetrics, setSnapshotMetrics] = useState<SnapshotMetric[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

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
      setSnapshotCount(snapshotsRes.data.length);
      setJudgeCount(judgesRes.data.length);
      setSnapshotMetrics(metricsRes.data.snapshots);
    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
      setMetricsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetId]);

  const handleEditOpen = () => {
    if (target) {
      setEditForm({
        name: target.name,
        agency: target.agency || "",
        purpose: target.purpose || "",
        target_users: target.target_users || "",
        api_endpoint: target.api_endpoint || "",
        endpoint_type: target.endpoint_type || EndpointType.AIBOTS,
        endpoint_config: target.endpoint_config || { api_key: "" },
      });
      setEditOpen(true);
    }
  };

  const handleEditSave = async () => {
    setEditLoading(true);
    try {
      await targetApi.update(targetId, editForm);
      await fetchData();
      setEditOpen(false);
    } catch (error) {
      console.error("Failed to update target:", error);
    } finally {
      setEditLoading(false);
    }
  };

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

  const totalPersonas = Object.values(stats.personas).reduce((a, b) => a + b, 0);
  const totalQuestions = Object.values(stats.questions).reduce((a, b) => a + b, 0);

  return (
    <Box>
      {/* Header with Download Report Button */}
      <Box sx={{ display: "flex", justifyContent: "flex-end", alignItems: "center", mb: 3 }}>
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleDownloadReport}
          disabled={downloading || loading}
        >
          {downloading ? "Generating PDF..." : "Download Report"}
        </Button>
      </Box>

      {/* Report Content */}
      <Box id="report-content">
        {/* Target Details and Knowledge Base Documents - Side by Side */}
        <Box sx={{ display: "flex", gap: 3, mb: 3, flexDirection: { xs: "column", md: "row" } }}>
        <Card variant="outlined" sx={{ flex: { md: "0 0 55%" }, height: "300px" }}>
          <CardContent>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
              <Typography variant="h6" fontWeight={600}>
                Target Details
              </Typography>
              <IconButton size="small" onClick={handleEditOpen}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Box>
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

        <Card variant="outlined" sx={{ flex: { md: "0 0 calc(45% - 24px)" }, height: "300px", display: "flex", flexDirection: "column" }}>
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
      <Box
        sx={{
          display: "grid",
          gap: 3,
          mb: 3, 
          gridTemplateColumns: {
            xs: "repeat(1, minmax(0, 1fr))",
            sm: "repeat(2, minmax(0, 1fr))",
            md: "repeat(4, minmax(0, 1fr))",
          },
        }}
      >
        <Card variant="outlined">
          <CardContent>
            <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
              <PersonIcon fontSize="small" sx={{ opacity: 0.5 }}/>
              <Typography variant="subtitle2" color="text.secondary">
                Personas
              </Typography>
            </Stack>
            <Typography variant="h4" fontWeight={600}>
              {totalPersonas}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined">
          <CardContent>
            <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
              <QuestionMarkIcon fontSize="small" sx={{ opacity: 0.5 }}/>
              <Typography variant="subtitle2" color="text.secondary">
                Questions
              </Typography>
            </Stack>
            <Typography variant="h4" fontWeight={600}>
              {totalQuestions}
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
              {snapshotCount}
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

      {/* Snapshot Accuracy Chart and Metrics */}
      <Box 
        sx={{
          mb: 3,
        }}>
        <Stack direction="row" spacing={3}>
          <SnapshotAccuracyChart
            data={snapshotMetrics}
            loading={metricsLoading}
          />

          <LatestSnapshotMetricsCard
            latestSnapshot={snapshotMetrics[0] || null}
            loading={metricsLoading}
          />
        </Stack>
      </Box>
      </Box>

      {/* Edit Target Dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Target</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
            <TextField
              label="Name"
              fullWidth
              value={editForm.name || ""}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
            />
            <TextField
              label="Agency"
              fullWidth
              value={editForm.agency || ""}
              onChange={(e) => setEditForm({ ...editForm, agency: e.target.value })}
            />
            <TextField
              label="Purpose"
              fullWidth
              multiline
              rows={2}
              value={editForm.purpose || ""}
              onChange={(e) => setEditForm({ ...editForm, purpose: e.target.value })}
            />
            <TextField
              label="Target Users"
              fullWidth
              value={editForm.target_users || ""}
              onChange={(e) => setEditForm({ ...editForm, target_users: e.target.value })}
            />
            <TextField
              label="API Endpoint"
              fullWidth
              value={editForm.api_endpoint || ""}
              onChange={(e) => setEditForm({ ...editForm, api_endpoint: e.target.value })}
            />
            <TextField
              label="AIBots API Key"
              fullWidth
              value={editForm.endpoint_config?.api_key || ""}
              onChange={(e) => setEditForm({
                ...editForm,
                endpoint_config: { ...editForm.endpoint_config, api_key: e.target.value }
              })}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)} disabled={editLoading}>Cancel</Button>
          <Button onClick={handleEditSave} variant="contained" disabled={editLoading}>
            {editLoading ? <CircularProgress size={24} /> : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
