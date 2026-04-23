"use client";

import React from "react";
import {
  IconFile,
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import {
  Box,
  Button,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  Paper,
  Typography,
} from "@mui/material";
import { actionIconProps } from "@/lib/iconStyles";

interface PendingDocumentsPanelProps {
  selectedFiles: File[];
  disabled?: boolean;
  uploadingFiles?: boolean;
  uploadProgress?: number;
  onFileSelect: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveFile: (index: number) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function PendingDocumentsPanel({
  selectedFiles,
  disabled = false,
  uploadingFiles = false,
  uploadProgress = 0,
  onFileSelect,
  onRemoveFile,
}: PendingDocumentsPanelProps) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Box>
          <Typography variant="h6" fontWeight={600}>
            Knowledge Base Documents
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ my: 0.5 }}>
            <i>Upload documents now. They will be attached after you create the target.</i>
          </Typography>
          {selectedFiles.length > 0 && (
            <Typography variant="body2" color="text.secondary">
              {selectedFiles.length} file{selectedFiles.length !== 1 ? "s" : ""} selected
            </Typography>
          )}
        </Box>
        <Button
          component="label"
          variant="outlined"
          startIcon={<IconUpload {...actionIconProps} />}
          disabled={disabled}
          sx={{ whiteSpace: "nowrap", flexShrink: 0 }}
        >
          Select Files
          <input
            type="file"
            hidden
            multiple
            accept=".pdf,.docx,.txt,.md"
            onChange={onFileSelect}
          />
        </Button>
      </Box>

      <Box sx={{ flexGrow: 1, overflow: "auto", minHeight: 0 }}>
        {selectedFiles.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
            <Box sx={{ color: "text.secondary", mb: 2 }}>
              <IconFile size={48} stroke={1.75} />
            </Box>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
              No documents selected yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Add PDF, DOCX, TXT, or MD files to upload after target creation
            </Typography>
          </Paper>
        ) : (
          <Paper variant="outlined">
            <List>
              {selectedFiles.map((file, index) => (
                <ListItem key={`${file.name}-${index}`} divider={index < selectedFiles.length - 1}>
                  <Box sx={{ mr: 2 }}>
                    <IconFile {...actionIconProps} color="currentColor" />
                  </Box>
                  <ListItemText
                    primary={file.name}
                    secondary={formatFileSize(file.size)}
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      onClick={() => onRemoveFile(index)}
                      disabled={disabled}
                      size="small"
                    >
                      <IconTrash {...actionIconProps} />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </Paper>
        )}
      </Box>

      {uploadingFiles && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Uploading documents... {Math.round(uploadProgress)}%
          </Typography>
          <LinearProgress variant="determinate" value={uploadProgress} />
        </Box>
      )}
    </Box>
  );
}
