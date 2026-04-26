"use client";

import React, { useState, useEffect } from "react";
import { TextField } from "@mui/material";
import { snapshotApi } from "@/lib/api";
import { Snapshot } from "@/lib/types";
import FormDialog from "./FormDialog";

interface CreateSnapshotDialogProps {
  open: boolean;
  targetId: number;
  existingSnapshots: Snapshot[];
  onClose: () => void;
  onSuccess: (snapshot: Snapshot) => void;
}

export default function CreateSnapshotDialog({
  open,
  targetId,
  existingSnapshots,
  onClose,
  onSuccess,
}: CreateSnapshotDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setName("");
      setDescription("");
      setError(null);
    }
  }, [open]);

  const handleSubmit = async () => {
    const trimmedName = name.trim();

    if (!trimmedName) {
      setError("Snapshot name is required");
      return;
    }

    const isDuplicate = existingSnapshots.some(
      (snapshot) => snapshot.name.toLowerCase() === trimmedName.toLowerCase()
    );

    if (isDuplicate) {
      setError("A snapshot with this name already exists. Please choose a different name.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await snapshotApi.create({
        target_id: targetId,
        name: trimmedName,
        description: description.trim() || undefined,
      });
      onSuccess(response.data);
    } catch (err) {
      console.error("Failed to create snapshot:", err);
      setError("Failed to create snapshot. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <FormDialog
      open={open}
      title="Create New Snapshot"
      onClose={handleClose}
      onSubmit={handleSubmit}
      submitLabel="Create"
      loading={loading}
      disabled={loading || !name.trim()}
      error={error}
    >
      <TextField
        label="Snapshot Name"
        required
        fullWidth
        value={name}
        onChange={(e) => setName(e.target.value)}
        disabled={loading}
        placeholder="e.g., Version 1.0"
      />

      <TextField
        label="Description"
        fullWidth
        multiline
        rows={3}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        disabled={loading}
        placeholder="Optional description of this snapshot"
      />
    </FormDialog>
  );
}
