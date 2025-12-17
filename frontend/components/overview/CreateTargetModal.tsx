"use client";

import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  CircularProgress,
  Typography,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Paper,
  LinearProgress,
  Alert,
} from "@mui/material";
import {
  CloudUpload as UploadIcon,
  Delete as DeleteIcon,
  InsertDriveFile as FileIcon,
} from "@mui/icons-material";
import { targetApi, kbDocumentApi, judgeApi } from "@/lib/api";
import { TargetCreate, EndpointType } from "@/lib/types";

interface CreateTargetModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateTargetModal({
  open,
  onClose,
  onSuccess,
}: CreateTargetModalProps) {
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<TargetCreate>({
    name: "",
    agency: "",
    purpose: "",
    target_users: "",
    api_endpoint: "",
    endpoint_type: EndpointType.AIBOTS,
    endpoint_config: { api_key: "" },
  });

  const handleChange = (field: keyof TargetCreate) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData({ ...formData, [field]: event.target.value });
  };

  const handleConfigChange = (field: "api_key") => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData({
      ...formData,
      endpoint_config: { ...formData.endpoint_config, [field]: event.target.value },
    });
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const fileArray = Array.from(files);
      // Filter for supported file types
      const supportedFiles = fileArray.filter((file) => {
        const ext = file.name.split(".").pop()?.toLowerCase();
        return ["pdf", "docx", "txt", "md"].includes(ext || "");
      });

      if (supportedFiles.length < fileArray.length) {
        setError("Some files were skipped. Only PDF, DOCX, TXT, and MD files are supported.");
      } else {
        setError(null);
      }

      setSelectedFiles((prev) => [...prev, ...supportedFiles]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async () => {
    if (!formData.name) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Create the target first
      const targetResponse = await targetApi.create(formData);
      const targetId = targetResponse.data.id;

      try {
        await judgeApi.seedDefaults();
      } catch (seedError) {
        // Seeding is idempotent and not critical to blocking target creation
        console.error("Failed to seed default judges:", seedError);
      }

      // Upload documents if any
      if (selectedFiles.length > 0) {
        setUploadingFiles(true);
        const totalFiles = selectedFiles.length;

        for (let i = 0; i < totalFiles; i++) {
          try {
            await kbDocumentApi.upload(targetId, selectedFiles[i]);
            setUploadProgress(((i + 1) / totalFiles) * 100);
          } catch (uploadError) {
            console.error(`Failed to upload ${selectedFiles[i].name}:`, uploadError);
            setError(`Failed to upload ${selectedFiles[i].name}. Other files uploaded successfully.`);
          }
        }
      }

      // Reset form
      setFormData({
        name: "",
        agency: "",
        purpose: "",
        target_users: "",
        api_endpoint: "",
        endpoint_type: EndpointType.AIBOTS,
        endpoint_config: { api_key: "" },
      });
      setSelectedFiles([]);
      setUploadProgress(0);
      setUploadingFiles(false);

      onSuccess();
      onClose();
    } catch (error) {
      console.error("Failed to create target:", error);
      setError("Failed to create target. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading && !uploadingFiles) {
      setSelectedFiles([]);
      setError(null);
      setUploadProgress(0);
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Create New Target Application</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}>
          {error && (
            <Alert severity="warning" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <TextField
            label="Name"
            required
            fullWidth
            value={formData.name}
            onChange={handleChange("name")}
            disabled={loading || uploadingFiles}
          />
          <TextField
            label="Agency"
            fullWidth
            value={formData.agency}
            onChange={handleChange("agency")}
            disabled={loading || uploadingFiles}
          />
          <TextField
            label="Purpose"
            fullWidth
            multiline
            rows={2}
            value={formData.purpose}
            onChange={handleChange("purpose")}
            disabled={loading || uploadingFiles}
          />
          <TextField
            label="Target Users"
            fullWidth
            value={formData.target_users}
            onChange={handleChange("target_users")}
            disabled={loading || uploadingFiles}
          />
          <TextField
            label="API Endpoint"
            fullWidth
            value={formData.api_endpoint}
            onChange={handleChange("api_endpoint")}
            disabled={loading || uploadingFiles}
          />
          <TextField
            label="AIBots API Key"
            fullWidth
            value={formData.endpoint_config?.api_key || ""}
            onChange={handleConfigChange("api_key")}
            disabled={loading || uploadingFiles}
          />

          {/* File Upload Section */}
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Knowledge Base Documents (Optional)
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Upload PDF, DOCX, TXT, or MD files
            </Typography>

            <Button
              component="label"
              variant="outlined"
              startIcon={<UploadIcon />}
              fullWidth
              sx={{ mt: 1, mb: 2 }}
              disabled={loading || uploadingFiles}
            >
              Select Files
              <input
                type="file"
                hidden
                multiple
                accept=".pdf,.docx,.txt,.md"
                onChange={handleFileSelect}
              />
            </Button>

            {selectedFiles.length > 0 && (
              <Paper variant="outlined" sx={{ maxHeight: 200, overflow: "auto" }}>
                <List dense>
                  {selectedFiles.map((file, index) => (
                    <ListItem key={index}>
                      <FileIcon sx={{ mr: 1, color: "text.secondary" }} />
                      <ListItemText
                        primary={file.name}
                        secondary={formatFileSize(file.size)}
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          edge="end"
                          onClick={() => handleRemoveFile(index)}
                          disabled={loading || uploadingFiles}
                          size="small"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </Paper>
            )}

            {uploadingFiles && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Uploading documents... {Math.round(uploadProgress)}%
                </Typography>
                <LinearProgress variant="determinate" value={uploadProgress} />
              </Box>
            )}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading || uploadingFiles}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || uploadingFiles || !formData.name}
        >
          {loading || uploadingFiles ? (
            <CircularProgress size={24} />
          ) : (
            "Create"
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
