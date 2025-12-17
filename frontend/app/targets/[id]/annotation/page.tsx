"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Alert, Box, CircularProgress } from "@mui/material";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
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

  const fetchSnapshots = useCallback(async () => {
    setSnapshotsLoading(true);
    try {
      const response = await snapshotApi.list(targetId);
      setSnapshots(response.data);
      if (!selectedSnapshotId && response.data.length > 0) {
        setSelectedSnapshotId(response.data[0].id);
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
    router.refresh();
  }, [fetchSnapshots, router]);

  if (snapshotsLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
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
