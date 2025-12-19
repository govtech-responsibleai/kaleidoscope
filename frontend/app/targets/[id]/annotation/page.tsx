"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Alert, Box, CircularProgress, Typography, Button } from "@mui/material";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import CreateSnapshotDialog from "@/components/shared/CreateSnapshotDialog";
import QAJobControl from "@/components/annotation/QAJobControl";
import QAList from "@/components/annotation/QAList";
import { Snapshot, QAJob, QAMap } from "@/lib/types";
import { snapshotApi, judgeApi } from "@/lib/api";

export default function AnnotationPage() {
  const params = useParams();
  const router = useRouter();
  const targetId = Number(params.id);

  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(null);
  const [snapshotsLoading, setSnapshotsLoading] = useState(true);
  const [baselineJudgeId, setBaselineJudgeId] = useState<number | null>(null);
  const [qaJobs, setQaJobs] = useState<QAJob[]>([]);
  const [qaMap, setQaMap] = useState<QAMap>({});
  const [error, setError] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const fetchSnapshots = useCallback(async () => {
    setSnapshotsLoading(true);
    try {
      const response = await snapshotApi.list(targetId);
      setSnapshots(response.data);
      if (!selectedSnapshotId && response.data.length > 0) {
        // Select the most recent snapshot (sort by created_at descending)
        const mostRecent = [...response.data].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )[0];
        setSelectedSnapshotId(mostRecent.id);
      }
    } catch (err) {
      console.error("Failed to load snapshots:", err);
      setError("Failed to load snapshots.");
    } finally {
      setSnapshotsLoading(false);
    }
  }, [targetId]);

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
  }, [fetchSnapshots, fetchBaselineJudge]);

  const handleSnapshotSelect = useCallback((snapshotId: number) => {
    setSelectedSnapshotId(snapshotId);
    setQaJobs([]);
    setQaMap({});
  }, []);

  const handleSnapshotCreated = useCallback((snapshot: Snapshot) => {
    setSelectedSnapshotId(snapshot.id);
    fetchSnapshots();
    setCreateDialogOpen(false);
    router.refresh();
  }, [fetchSnapshots, router]);

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
      <SnapshotHeader
        targetId={targetId}
        snapshots={snapshots}
        selectedSnapshotId={selectedSnapshotId}
        onSelectSnapshot={handleSnapshotSelect}
        onSnapshotCreated={handleSnapshotCreated}
      />

      <QAJobControl
        snapshotId={selectedSnapshotId}
        baselineJudgeId={baselineJudgeId}
        qaJobs={qaJobs}
        setQaJobs={setQaJobs}
        qaMap={qaMap}
        setQaMap={setQaMap}
        onError={(message) => setError(message)}
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
      />
    </Box>
  );
}
