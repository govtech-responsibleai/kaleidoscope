"use client";

import React, { useEffect, useState } from "react";
import {
  IconFile,
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Button,
  CircularProgress,
} from "@mui/material";
import { kbDocumentApi } from "@/lib/api";
import { KBDocumentResponse } from "@/lib/types";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import { actionIconProps, sectionIconProps } from "@/lib/iconStyles";

interface DocumentListProps {
  targetId: number;
  hideUploadButton?: boolean;
  onUploadStart?: () => void;
  onUploadEnd?: () => void;
}

export default function DocumentList({
  targetId,
  hideUploadButton = false,
  onUploadStart,
  onUploadEnd,
}: DocumentListProps) {
  const [documents, setDocuments] = useState<KBDocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [totalSize, setTotalSize] = useState(0);
  const [documentToDelete, setDocumentToDelete] = useState<number | null>(null);

  const fetchDocuments = async () => {
    try {
      const response = await kbDocumentApi.list(targetId);
      setDocuments(response.data.documents);
      setTotalSize(response.data.total_size_bytes);
    } catch (error) {
      console.error("Failed to fetch documents:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [targetId]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    onUploadStart?.();
    try {
      for (let i = 0; i < files.length; i++) {
        await kbDocumentApi.upload(targetId, files[i]);
      }
      await fetchDocuments();
    } catch (error) {
      console.error("Failed to upload documents:", error);
      alert("Failed to upload some documents. Please try again.");
    } finally {
      setUploading(false);
      onUploadEnd?.();
    }
  };

  const handleDeleteClick = (documentId: number) => {
    setDocumentToDelete(documentId);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase();
    return <IconFile {...sectionIconProps} color={ext === "pdf" ? "#d32f2f" : "currentColor"} />;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" py={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} sx={{ gap: 1 }}>
        <Box>
          <Typography variant="h6" fontWeight={600}>
            Knowledge Base Documents
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ my: 0.5 }}>
            <i> Used to inform question generation. For best results, upload documents that cover the scope of your target application.</i>
          </Typography>
          {documents.length > 0 && (
            <Typography variant="body2" color="text.secondary">
              {documents.length} document{documents.length !== 1 ? "s" : ""} · {formatFileSize(totalSize)}
            </Typography>
          )}
        </Box>
        {!hideUploadButton && (
          <Button
            component="label"
            variant="outlined"
            startIcon={<IconUpload {...actionIconProps} />}
            disabled={uploading}
            sx={{ whiteSpace: "nowrap", flexShrink: 0 }}
          >
            {uploading ? "Uploading..." : "Upload"}
            <input
              type="file"
              hidden
              multiple
              accept=".pdf,.docx,.txt,.md"
              onChange={handleFileUpload}
            />
          </Button>
        )}
      </Box>

      <Box sx={{ flexGrow: 1, overflow: "auto", minHeight: 0 }}>
        {documents.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
            <Box sx={{ color: "text.secondary", mb: 2 }}>
              <IconFile size={48} stroke={1.75} />
            </Box>
            <Typography variant="body1" color="text.secondary"  sx={{ mb: 1 }}>
              No documents uploaded yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Upload PDF, DOCX, TXT, or MD files to build your knowledge base
            </Typography>
          </Paper>
        ) : (
          <Paper variant="outlined">
            <List>
              {documents.map((doc, index) => (
                <ListItem
                  key={doc.id}
                  divider={index < documents.length - 1}
                >
                  <Box sx={{ mr: 2 }}>{getFileIcon(doc.filename)}</Box>
                  <ListItemText
                    primary={doc.filename}
                    secondary={
                      <Box component="span" display="flex" gap={1} alignItems="center">
                        <span>{formatFileSize(doc.file_size)}</span>
                        {doc.page_count && (
                          <>
                            <span>•</span>
                            <span>{doc.page_count} page{doc.page_count !== 1 ? "s" : ""}</span>
                          </>
                        )}
                        <span>•</span>
                        <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      onClick={() => handleDeleteClick(doc.id)}
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

      <ConfirmDeleteDialog
        open={documentToDelete !== null}
        onClose={() => setDocumentToDelete(null)}
        onConfirm={async () => {
          if (!documentToDelete) return;
          await kbDocumentApi.delete(documentToDelete);
          await fetchDocuments();
          setDocumentToDelete(null);
        }}
        title="Delete Document"
      />
    </Box>
  );
}
