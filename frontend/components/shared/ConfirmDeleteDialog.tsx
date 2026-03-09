"use client";

import React, { useState } from "react";
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from "@mui/material";
import { Delete as DeleteIcon } from "@mui/icons-material";

interface ConfirmDeleteDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  title: string;
  itemName?: string;
  description?: string;
  destructive?: boolean;
}

export default function ConfirmDeleteDialog({
  open,
  onClose,
  onConfirm,
  title,
  itemName,
  description,
  destructive = false,
}: ConfirmDeleteDialogProps) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    setDeleting(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      console.error("Delete failed:", err);
      setError("Failed to delete. Please try again.");
    } finally {
      setDeleting(false);
    }
  };

  const handleClose = () => {
    if (!deleting) {
      setError(null);
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose}>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {destructive && (
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="subtitle2">
              Your data will be lost!
            </Typography>
          </Alert>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Typography variant="body1">
          Are you sure you want to delete
          {itemName ? <> <strong>{itemName}</strong></> : " this item"}?
          {" "}This action cannot be undone.
        </Typography>
        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            {description}
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={deleting}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          color="error"
          variant="contained"
          disabled={deleting}
          startIcon={deleting ? <CircularProgress size={20} /> : <DeleteIcon />}
        >
          {deleting ? "Deleting..." : "Delete"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
