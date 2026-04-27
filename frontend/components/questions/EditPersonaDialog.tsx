"use client";

import {
  Box,
  MenuItem,
  Select,
  TextField,
  Typography,
} from "@mui/material";
import { FormDialog } from "@/components/shared";
import { personaApi } from "@/lib/api";
import { usePersonaEdit } from "@/hooks/usePersonaEdit";
import { PersonaResponse, Status } from "@/lib/types";
import { useEffect, useState } from "react";

interface EditPersonaDialogProps {
  open: boolean;
  persona: PersonaResponse | null;
  personas: PersonaResponse[];
  onClose: () => void;
  onSaved: () => void;
}

export default function EditPersonaDialog({
  open,
  persona,
  personas,
  onClose,
  onSaved,
}: EditPersonaDialogProps) {
  const [saveError, setSaveError] = useState<string | null>(null);

  const {
    cancelEdit,
    editedInfo,
    editedStyle,
    editedTitle,
    editedUseCase,
    saveEdit,
    saveError: hookSaveError,
    savingPersonaId,
    setEditedInfo,
    setEditedStyle,
    setEditedTitle,
    setEditedUseCase,
    startEdit,
  } = usePersonaEdit({
    onSaved: () => {
      setSaveError(null);
      onSaved();
      onClose();
    },
  });

  useEffect(() => {
    if (open && persona) {
      startEdit(persona);
      return;
    }
    if (!open) {
      cancelEdit();
    }
  }, [cancelEdit, open, persona, startEdit]);

  const isSaving = savingPersonaId !== null;
  const canSave = editedTitle.trim().length > 0 && !isSaving;

  const handleSave = () => {
    if (!persona) return;
    void saveEdit(persona.id, personas);
  };

  const handleClose = () => {
    cancelEdit();
    setSaveError(null);
    onClose();
  };

  return (
    <FormDialog
      open={open}
      title="Edit Persona"
      onClose={handleClose}
      onSubmit={handleSave}
      loading={isSaving}
      disabled={!canSave}
      error={saveError ?? hookSaveError}
    >
      <TextField
        label="Title"
        value={editedTitle}
        onChange={(e) => setEditedTitle(e.target.value)}
        size="small"
        fullWidth
        required
        error={editedTitle.trim().length === 0}
      />

      <TextField
        label="Background"
        value={editedInfo}
        onChange={(e) => setEditedInfo(e.target.value)}
        size="small"
        fullWidth
        multiline
        rows={3}
      />

      <TextField
        label="Style"
        value={editedStyle}
        onChange={(e) => setEditedStyle(e.target.value)}
        size="small"
        fullWidth
        multiline
        rows={2}
      />

      <TextField
        label="Use Case"
        value={editedUseCase}
        onChange={(e) => setEditedUseCase(e.target.value)}
        size="small"
        fullWidth
        multiline
        rows={2}
      />

      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: "block" }}>
          Status
        </Typography>
        {persona?.status === Status.APPROVED ? (
          <Typography variant="body2" sx={{ color: "success.main", fontWeight: 600, py: 0.5 }}>
            Approved
          </Typography>
        ) : (
          <Select
            value={persona?.status ?? "pending"}
            size="small"
            fullWidth
            onChange={async (e) => {
              if (!persona || (e.target.value as Status) !== Status.APPROVED) return;
              try {
                await personaApi.approve(persona.id);
                onSaved();
                onClose();
              } catch {
                setSaveError("Failed to approve persona. Please try again.");
              }
            }}
          >
            <MenuItem value="pending" disabled>Pending</MenuItem>
            <MenuItem value="rejected" disabled>Rejected</MenuItem>
            <MenuItem value="approved">Approve</MenuItem>
          </Select>
        )}
      </Box>
    </FormDialog>
  );
}
