"use client";

import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
} from "@mui/material";
import React from "react";

interface FormDialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  onSubmit: () => void;
  submitLabel?: string;
  loading?: boolean;
  disabled?: boolean;
  error?: string | null;
  children: React.ReactNode;
}

export default function FormDialog({
  open,
  title,
  onClose,
  onSubmit,
  submitLabel = "Save",
  loading = false,
  disabled = false,
  error,
  children,
}: FormDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingTop: 8 }}>
          {error && <Alert severity="error">{error}</Alert>}
          {children}
        </div>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={onSubmit}
          disabled={disabled || loading}
          startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {loading ? "Saving..." : submitLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
