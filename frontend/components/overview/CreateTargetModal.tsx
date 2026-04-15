"use client";

import React, { useEffect, useState, useRef } from "react";
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
  MenuItem,
} from "@mui/material";
import {
  CloudUpload as UploadIcon,
  Delete as DeleteIcon,
  InsertDriveFile as FileIcon,
} from "@mui/icons-material";
import { targetApi, kbDocumentApi, webSearchApi } from "@/lib/api";
import { TargetCreate } from "@/lib/types";
import ConnectorConfigFields, { validateEndpointConfig } from "./ConnectorConfigFields";

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
  const [connectorTypes, setConnectorTypes] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const mountedRef = useRef(true);

  const [formData, setFormData] = useState<TargetCreate>({
    name: "",
    agency: "",
    purpose: "",
    target_users: "",
    api_endpoint: "",
    endpoint_type: "http",
    endpoint_config: {},
  });

  useEffect(() => {
    mountedRef.current = true;
    if (open) {
      targetApi.getConnectorTypes().then((res) => {
        if (!mountedRef.current) return;
        setConnectorTypes(res.data);
      }).catch(() => {
        if (!mountedRef.current) return;
        setConnectorTypes(["http"]);
      });
    }
    return () => { mountedRef.current = false; };
  }, [open]);

  const endpointType = formData.endpoint_type || "http";

  const handleChange = (field: keyof TargetCreate) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData({ ...formData, [field]: event.target.value });
  };

  const handleEndpointTypeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      endpoint_type: event.target.value,
      endpoint_config: {},
    });
    setShowAdvanced(false);
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const fileArray = Array.from(files);
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
    if (!formData.name) return;

    // Validate JSON config fields before submit
    const configError = validateEndpointConfig(endpointType, formData.endpoint_config || {});
    if (configError) {
      setError(configError);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const submitData: TargetCreate = {
        ...formData,
        endpoint_type: formData.api_endpoint ? formData.endpoint_type : undefined,
        endpoint_config: formData.api_endpoint ? formData.endpoint_config : undefined,
      };

      const targetResponse = await targetApi.create(submitData);
      const targetId = targetResponse.data.id;

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

      webSearchApi.trigger(targetId).catch((err) =>
        console.warn("Web search trigger failed:", err)
      );

      setFormData({
        name: "",
        agency: "",
        purpose: "",
        target_users: "",
        api_endpoint: "",
        endpoint_type: connectorTypes[0] || "http",
        endpoint_config: {},
      });
      setSelectedFiles([]);
      setUploadProgress(0);
      setUploadingFiles(false);
      setShowAdvanced(false);

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

  const config = formData.endpoint_config || {};
  const disabled = loading || uploadingFiles;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Create New Target Application</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <TextField
            label="Name"
            required
            fullWidth
            value={formData.name}
            onChange={handleChange("name")}
            disabled={disabled}
          />
          <TextField
            label="Agency"
            fullWidth
            value={formData.agency}
            onChange={handleChange("agency")}
            disabled={disabled}
          />
          <TextField
            label="Purpose"
            fullWidth
            multiline
            rows={2}
            value={formData.purpose}
            onChange={handleChange("purpose")}
            disabled={disabled}
          />
          <TextField
            label="Target Users"
            fullWidth
            value={formData.target_users}
            onChange={handleChange("target_users")}
            disabled={disabled}
          />

          <Paper variant="outlined" sx={{ p: 2, bgcolor: "grey.50", display: "flex", flexDirection: "column", gap: 2 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Endpoint Configuration
            </Typography>

            <TextField
              label="Endpoint Type"
              select
              fullWidth
              value={endpointType}
              onChange={handleEndpointTypeChange}
              disabled={disabled || connectorTypes.length <= 1}
              size="small"
            >
              {connectorTypes.map((t) => (
                <MenuItem key={t} value={t}>{t}</MenuItem>
              ))}
            </TextField>

            <TextField
              label="API Endpoint URL"
              fullWidth
              value={formData.api_endpoint}
              onChange={handleChange("api_endpoint")}
              disabled={disabled}
              placeholder="https://api.example.com/v1/chat/completions"
              size="small"
            />

            <ConnectorConfigFields
              endpointType={endpointType}
              config={config}
              apiEndpoint={formData.api_endpoint}
              onConfigField={(field, value) =>
                setFormData((prev) => ({
                  ...prev,
                  endpoint_config: { ...prev.endpoint_config, [field]: value },
                }))
              }
              onConfigReplace={(newConfig) =>
                setFormData((prev) => ({ ...prev, endpoint_config: newConfig }))
              }
              showAdvanced={showAdvanced}
              onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
              disabled={disabled}
              onJsonError={setError}
            />
          </Paper>

          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Knowledge Base Documents (Optional)
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Upload PDF, DOCX, or MD files
            </Typography>

            <Button
              component="label"
              variant="outlined"
              startIcon={<UploadIcon />}
              fullWidth
              sx={{ mt: 1, mb: 2 }}
              disabled={disabled}
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
                          disabled={disabled}
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
        <Button onClick={handleClose} disabled={disabled}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={disabled || !formData.name}
        >
          {disabled ? (
            <CircularProgress size={24} />
          ) : (
            "Create"
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
