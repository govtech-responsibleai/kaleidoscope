"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
} from "@mui/material";
import { ArrowBack as ArrowBackIcon, Delete as DeleteIcon, CloudUpload as UploadIcon } from "@mui/icons-material";
import { useRouter, useParams, usePathname } from "next/navigation";
import { targetApi, kbDocumentApi } from "@/lib/api";
import { TargetResponse, TargetStats } from "@/lib/types";

interface TargetLayoutProps {
  children: React.ReactNode;
}

export default function TargetLayout({ children }: TargetLayoutProps) {
  const router = useRouter();
  const params = useParams();
  const pathname = usePathname();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Determine active tab based on pathname
  const activeTab = pathname.includes("/questions") ? "questions" : "overview";

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

  const handleDeleteTarget = async () => {
    setDeleting(true);
    try {
      await targetApi.delete(targetId);
      router.push("/");
    } catch (error) {
      console.error("Failed to delete target:", error);
      alert("Failed to delete target. Please try again.");
      setDeleting(false);
      setDeleteDialogOpen(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        await kbDocumentApi.upload(targetId, files[i]);
      }
      fetchData(); // Refresh stats
    } catch (error) {
      console.error("Failed to upload documents:", error);
      alert("Failed to upload some documents. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: string) => {
    if (newValue === "overview") {
      router.push(`/targets/${targetId}`);
    } else if (newValue === "questions") {
      router.push(`/targets/${targetId}/questions`);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }

  if (!target || !stats) {
    return (
      <Box>
        <Typography variant="h6">Target not found</Typography>
        <Button onClick={() => router.push("/")}>Go Back</Button>
      </Box>
    );
  }

  const totalPersonas = Object.values(stats.personas).reduce((a, b) => a + b, 0);
  const totalQuestions = Object.values(stats.questions).reduce((a, b) => a + b, 0);

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => router.push("/")}
        >
          Back to Targets
        </Button>
        <Box display="flex" gap={2}>
          <Button
            component="label"
            variant="outlined"
            startIcon={<UploadIcon />}
            disabled={uploading}
          >
            {uploading ? "Uploading..." : "Upload Documents"}
            <input
              type="file"
              hidden
              multiple
              accept=".pdf,.docx,.txt,.md"
              onChange={handleFileUpload}
            />
          </Button>
          <Button
            variant="outlined"
            color="error"
            startIcon={<DeleteIcon />}
            onClick={() => setDeleteDialogOpen(true)}
          >
            Delete Target
          </Button>
        </Box>
      </Box>

      <Typography variant="h4" component="h1" fontWeight={600} gutterBottom>
        {target.name}
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Overview" value="overview" />
          <Tab label="Questions" value="questions" />
        </Tabs>
      </Box>

      {children}

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => !deleting && setDeleteDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Delete Target Application</DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              This action cannot be undone!
            </Typography>
          </Alert>
          <Typography variant="body1" gutterBottom>
            Are you sure you want to delete <strong>{target?.name}</strong>?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            This will permanently delete:
          </Typography>
          <Box component="ul" sx={{ mt: 1, pl: 2 }}>
            <li>
              <Typography variant="body2">All personas ({totalPersonas})</Typography>
            </li>
            <li>
              <Typography variant="body2">All questions ({totalQuestions})</Typography>
            </li>
            <li>
              <Typography variant="body2">All knowledge base documents</Typography>
            </li>
            <li>
              <Typography variant="body2">All generation jobs and statistics</Typography>
            </li>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button
            onClick={handleDeleteTarget}
            color="error"
            variant="contained"
            disabled={deleting}
            startIcon={deleting ? <CircularProgress size={20} /> : <DeleteIcon />}
          >
            {deleting ? "Deleting..." : "Delete Permanently"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
