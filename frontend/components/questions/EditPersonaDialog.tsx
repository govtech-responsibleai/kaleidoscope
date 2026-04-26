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
import { PersonaResponse } from "@/lib/types";
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

  const personaEdit = usePersonaEdit({
    onSaved: () => {
      setSaveError(null);
      onSaved();
      onClose();
    },
    onError: (msg) => setSaveError(msg),
  });

  useEffect(() => {
    if (open && persona) {
      personaEdit.startEdit(persona);
      setSaveError(null);
    }
    if (!open) {
      personaEdit.cancelEdit();
      setSaveError(null);
    }
  }, [open, persona?.id]);

  const isSaving = personaEdit.savingPersonaId !== null;
  const canSave = personaEdit.editedTitle.trim().length > 0 && !isSaving;

  const handleSave = () => {
    if (!persona) return;
    personaEdit.saveEdit(persona.id, personas);
  };

  const handleClose = () => {
    personaEdit.cancelEdit();
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
      error={saveError}
    >
      <TextField
        label="Title"
        value={personaEdit.editedTitle}
        onChange={(e) => personaEdit.setEditedTitle(e.target.value)}
        size="small"
        fullWidth
        required
        error={personaEdit.editedTitle.trim().length === 0}
      />

      <TextField
        label="Background"
        value={personaEdit.editedInfo}
        onChange={(e) => personaEdit.setEditedInfo(e.target.value)}
        size="small"
        fullWidth
        multiline
        rows={3}
      />

      <TextField
        label="Style"
        value={personaEdit.editedStyle}
        onChange={(e) => personaEdit.setEditedStyle(e.target.value)}
        size="small"
        fullWidth
        multiline
        rows={2}
      />

      <TextField
        label="Use Case"
        value={personaEdit.editedUseCase}
        onChange={(e) => personaEdit.setEditedUseCase(e.target.value)}
        size="small"
        fullWidth
        multiline
        rows={2}
      />

      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: "block" }}>
          Status
        </Typography>
        {persona?.status === "approved" ? (
          <Typography variant="body2" sx={{ color: "success.main", fontWeight: 600, py: 0.5 }}>
            Approved
          </Typography>
        ) : (
          <Select
            value={persona?.status ?? "pending"}
            size="small"
            fullWidth
            onChange={async (e) => {
              if (!persona || e.target.value !== "approved") return;
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
