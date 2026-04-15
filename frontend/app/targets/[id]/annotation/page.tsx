"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Alert, Box, CircularProgress, IconButton, Tooltip, Typography } from "@mui/material";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import QAJobControl from "@/components/annotation/QAJobControl";
import QAList from "@/components/annotation/QAList";
import { Snapshot, QAJob, QAMap, TargetRubricResponse, QuestionResponse, Status } from "@/lib/types";
import { Download as DownloadIcon } from "@mui/icons-material";
import { snapshotApi, judgeApi, metricsApi, targetRubricApi, questionApi } from "@/lib/api";

export default function AnnotationPage() {
  return (
    <Suspense
      fallback={
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      }
    >
      <AnnotationPageContent />
    </Suspense>
  );
}

function AnnotationPageContent() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const targetId = Number(params.id);

  // Initialize from URL if available
  const snapshotIdFromUrl = searchParams.get("snapshot");
  const questionIdFromUrl = searchParams.get("question");
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
  const [approvedQuestions, setApprovedQuestions] = useState<QuestionResponse[]>([]);
  const [approvedQuestionsLoading, setApprovedQuestionsLoading] = useState(true);
  const [approvedQuestionsError, setApprovedQuestionsError] = useState<string | null>(null);
  const autoCreateAttempted = useRef(false);
  const approvedQuestionIds = useMemo(
    () => approvedQuestions.map((question) => question.id),
    [approvedQuestions]
  );

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

      if (response.data.length === 0 && !autoCreateAttempted.current) {
        autoCreateAttempted.current = true;
        try {
          const createResponse = await snapshotApi.create({
            target_id: targetId,
            name: "Snapshot 1",
          });
          setSnapshots([createResponse.data]);
          updateSnapshotSelection(createResponse.data.id);
        } catch (err) {
          console.error("Failed to auto-create snapshot:", err);
          setError("Failed to create initial snapshot.");
        }
        return;
      }

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

  const fetchApprovedQuestions = useCallback(async () => {
    setApprovedQuestionsLoading(true);
    try {
      const questions = await questionApi.listAllByTarget(targetId, {
        status_filter: Status.APPROVED,
      });
      setApprovedQuestions(questions);
      setApprovedQuestionsError(null);
    } catch (err) {
      console.error("Failed to load approved questions:", err);
      setApprovedQuestions([]);
      setApprovedQuestionsError("Failed to load approved questions.");
    } finally {
      setApprovedQuestionsLoading(false);
    }
  }, [targetId]);

  useEffect(() => {
    fetchSnapshots();
    fetchBaselineJudge();
    fetchApprovedQuestions();
    targetRubricApi.list(targetId).then((res) => setRubrics(res.data)).catch(() => {});
  }, [fetchSnapshots, fetchBaselineJudge, fetchApprovedQuestions, targetId]);

  const handleSnapshotSelect = useCallback((snapshotId: number | null) => {
    updateSnapshotSelection(snapshotId);
    setQaJobs([]);
    setQaMap({});
  }, [updateSnapshotSelection]);

  const handleSnapshotCreated = useCallback((snapshot: Snapshot) => {
    updateSnapshotSelection(snapshot.id);
    fetchSnapshots();
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

  // Show loading state while auto-creating first snapshot
  if (snapshots.length === 0) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "40vh", flexDirection: "column", gap: 2 }}>
        <CircularProgress />
        <Typography variant="body1" color="text.secondary">
          Setting up your first snapshot...
        </Typography>
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
        targetId={targetId}
        snapshotId={selectedSnapshotId}
        baselineJudgeId={baselineJudgeId}
        approvedQuestionIds={approvedQuestionIds}
        qaJobs={qaJobs}
        setQaJobs={setQaJobs}
        qaMap={qaMap}
        setQaMap={setQaMap}
        rubrics={rubrics}
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
        approvedQuestions={approvedQuestions}
        questionsLoading={approvedQuestionsLoading}
        questionError={approvedQuestionsError}
        qaJobs={qaJobs}
        qaMap={qaMap}
        setQaMap={setQaMap}
        rubrics={rubrics}
        initialQuestionId={questionIdFromUrl ? Number(questionIdFromUrl) : null}
      />
    </Box>
  );
}
