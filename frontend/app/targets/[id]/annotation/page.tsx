"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Alert, Box, CircularProgress, IconButton, Tooltip, Typography, Button } from "@mui/material";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import CreateSnapshotDialog from "@/components/shared/CreateSnapshotDialog";
import QAJobControl from "@/components/annotation/QAJobControl";
import QAList from "@/components/annotation/QAList";
import { Snapshot, QAJob, QAMap, TargetRubricResponse } from "@/lib/types";
import { Download as DownloadIcon } from "@mui/icons-material";
import { snapshotApi, judgeApi, metricsApi, targetRubricApi } from "@/lib/api";

export default function AnnotationPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const targetId = Number(params.id);

  // Initialize from URL if available
  const snapshotIdFromUrl = searchParams.get("snapshot");
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(
    snapshotIdFromUrl ? Number(snapshotIdFromUrl) : null
  );
  const [snapshotsLoading, setSnapshotsLoading] = useState(true);
  const [baselineJudgeId, setBaselineJudgeId] = useState<number | null>(null);
  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);
  const [qaJobs, setQaJobs] = useState<QAJob[]>([]);
  const [qaMap, setQaMap] = useState<QAMap>({});
  const [error, setError] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [rubricJobsComplete, setRubricJobsComplete] = useState(false);
  const [rubricPendingQuestions, setRubricPendingQuestions] = useState<Set<number>>(new Set());

  const updateSnapshotSelection = useCallback((snapshotId: number | null) => {
    setSelectedSnapshotId(snapshotId);
    const newSearchParams = new URLSearchParams(searchParams.toString());
    if (snapshotId === null) {
      newSearchParams.delete("snapshot");
    } else {
      newSearchParams.set("snapshot", snapshotId.toString());
    }
    const query = newSearchParams.toString();
    router.push(`/targets/${targetId}/annotation${query ? `?${query}` : ""}`, { scroll: false });
  }, [searchParams, router, targetId]);

  const fetchSnapshots = useCallback(async () => {
    setSnapshotsLoading(true);
    try {
      const response = await snapshotApi.list(targetId);
      setSnapshots(response.data);
      const hasSelectedSnapshot = selectedSnapshotId !== null && response.data.some(
        (snapshot) => snapshot.id === selectedSnapshotId
      );
      if (!hasSelectedSnapshot) {
        if (response.data.length > 0) {
          const mostRecent = [...response.data].sort((a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          )[0];
          updateSnapshotSelection(mostRecent.id);
        } else if (selectedSnapshotId !== null) {
          updateSnapshotSelection(null);
        }
      }
    } catch (err) {
      console.error("Failed to load snapshots:", err);
      setError("Failed to load snapshots.");
    } finally {
      setSnapshotsLoading(false);
    }
  }, [targetId, selectedSnapshotId, updateSnapshotSelection]);

  const fetchBaselineJudge = useCallback(async () => {
    try {
      const response = await judgeApi.getBaseline();
      setBaselineJudgeId(response.data.id);
    } catch (err) {
      console.error("Failed to load baseline judge:", err);
      setError("Failed to load judge configuration.");
    }
  }, []);

  useEffect(() => {
    fetchSnapshots();
    fetchBaselineJudge();
    targetRubricApi.list(targetId).then((res) => setRubrics(res.data)).catch(() => {});
  }, [fetchSnapshots, fetchBaselineJudge]);

  const handleSnapshotSelect = useCallback((snapshotId: number | null) => {
    updateSnapshotSelection(snapshotId);
    setQaJobs([]);
    setQaMap({});
  }, [updateSnapshotSelection]);

  const handleSnapshotCreated = useCallback((snapshot: Snapshot) => {
    updateSnapshotSelection(snapshot.id);
    fetchSnapshots();
    setCreateDialogOpen(false);
  }, [fetchSnapshots, updateSnapshotSelection]);

  const handleExportSnapshot = async () => {
    if (!selectedSnapshotId) return;
    try {
      const response = await metricsApi.exportJSON(selectedSnapshotId);
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `snapshot_${selectedSnapshotId}_results.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to export snapshot:", error);
      alert("Failed to export snapshot. Please try again.");
    }
  };

  if (snapshotsLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show empty state if no snapshots exist
  if (snapshots.length === 0) {
    return (
      <Box>
        <Box
          display="flex"
          flexDirection="column"
          alignItems="center"
          justifyContent="center"
          minHeight="40vh"
          gap={2}
          sx={{ maxWidth: 600, mx: "auto", textAlign: "center" }}
        >
          <Typography variant="h5" fontWeight={600}>
            Generate a snapshot of answers for review
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
            A snapshot captures your chatbot's answers to a set of questions at a specific point in time.
            Create one to begin the annotation process and review your chatbot's responses.
          </Typography>
          <Button
            variant="contained"
            size="large"
            onClick={() => setCreateDialogOpen(true)}
          >
            Create Snapshot
          </Button>
        </Box>

        <CreateSnapshotDialog
          open={createDialogOpen}
          targetId={targetId}
          existingSnapshots={snapshots}
          onClose={() => setCreateDialogOpen(false)}
          onSuccess={handleSnapshotCreated}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 1 }}>
        <Box sx={{ flex: 1 }}>
          <SnapshotHeader
            targetId={targetId}
            snapshots={snapshots}
            selectedSnapshotId={selectedSnapshotId}
            onSelectSnapshot={handleSnapshotSelect}
            onSnapshotCreated={handleSnapshotCreated}
            onSnapshotDeleted={fetchSnapshots}
          />
        </Box>
        <Tooltip title="Download data for this snapshot">
          <span>
            <IconButton
              onClick={handleExportSnapshot}
              disabled={!selectedSnapshotId}
              sx={{
                bgcolor: "secondary.main",
                color: "white",
                borderRadius: 1,
                "&:hover": { bgcolor: "secondary.dark" },
                "&.Mui-disabled": { bgcolor: "action.disabledBackground", color: "action.disabled" },
              }}
            >
              <DownloadIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <QAJobControl
        snapshotId={selectedSnapshotId}
        baselineJudgeId={baselineJudgeId}
        qaJobs={qaJobs}
        setQaJobs={setQaJobs}
        qaMap={qaMap}
        setQaMap={setQaMap}
        rubrics={rubrics}
        onError={(message) => setError(message)}
        onRubricJobsCompleteChange={setRubricJobsComplete}
        onRubricPendingQuestionsChange={setRubricPendingQuestions}
      />

      {error && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      <QAList
        targetId={targetId}
        snapshotId={selectedSnapshotId}
        qaJobs={qaJobs}
        qaMap={qaMap}
        setQaMap={setQaMap}
        rubrics={rubrics}
        rubricPendingQuestions={rubricPendingQuestions}
      />
    </Box>
  );
}
