"use client";

import { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  CircularProgress,
  IconButton,
  Alert,
} from "@mui/material";
import {
  Close as CloseIcon,
  AutoAwesome as AutoAwesomeIcon,
  Groups as GroupsIcon,
} from "@mui/icons-material";
import { personaApi } from "@/lib/api";
import { usePersonaGeneration } from "@/hooks/usePersonaGeneration";
import { usePersonaEdit } from "@/hooks/usePersonaEdit";
import PersonaSelect from "@/components/questions/PersonaSelect";
import PersonaReview from "@/components/questions/PersonaReview";
import PersonaManualAdd from "@/components/questions/PersonaManualAdd";

type AddMode = "manual" | null;

interface AddPersonasDialogProps {
  open: boolean;
  onClose: () => void;
  targetId: number;
  onPersonasAdded: () => void;
}

export default function AddPersonasDialog({
  open,
  onClose,
  targetId,
  onPersonasAdded,
}: AddPersonasDialogProps) {
  const [mode, setMode] = useState<AddMode>(null);
  const [rejectedIds, setRejectedIds] = useState<Set<number>>(new Set());

  const personaGen = usePersonaGeneration(targetId);

  const personaEdit = usePersonaEdit({
    onSaved: (personaId, updated) => personaGen.updatePersona(personaId, updated),
    onError: (msg) => personaGen.setError(msg),
  });

  const handleClose = () => {
    setMode(null);
    setRejectedIds(new Set());
    personaGen.reset();
    personaEdit.reset();
    onClose();
  };

  const handleToggleReject = (personaId: number) => {
    setRejectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(personaId)) next.delete(personaId);
      else next.add(personaId);
      return next;
    });
  };

  const handleApprovePersonas = async () => {
    const selectedIds = personaGen.personas
      .filter((p) => !rejectedIds.has(p.id))
      .map((p) => p.id);

    if (selectedIds.length === 0) {
      personaGen.setError("Please select at least one persona.");
      return;
    }

    try {
      await personaApi.bulkApprove(selectedIds);
      if (rejectedIds.size > 0) {
        await Promise.all([...rejectedIds].map((id) => personaApi.reject(id)));
      }
      onPersonasAdded();
      handleClose();
    } catch (err) {
      console.error("Failed to approve personas:", err);
      personaGen.setError("Failed to approve personas.");
    }
  };

  const selectedCount = personaGen.personas.length - rejectedIds.size;
  const showPersonaReview = personaGen.personas.length > 0;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Add Personas</Typography>
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        {personaGen.error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {personaGen.error}
          </Alert>
        )}

        {mode !== "manual" && !showPersonaReview && !personaGen.loading && (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            py={3}
            gap={3}
          >
            <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ maxWidth: 500 }}>
              Choose how you'd like to add personas for this target.
            </Typography>
            <PersonaSelect
              onGenerateAI={() => personaGen.generateWithAI()}
              onSampleRandom={() => personaGen.sampleNemotron()}
              onAddManual={() => setMode("manual")}
            />
          </Box>
        )}

        {personaGen.loading && !showPersonaReview && mode !== "manual" && (
          <Box display="flex" flexDirection="column" alignItems="center" py={4} gap={2}>
            <CircularProgress />
            <Typography variant="body2" color="text.secondary">
              {personaGen.source === "ai" ? "Generating personas with AI..." : "Sampling personas..."}
            </Typography>
          </Box>
        )}

        {showPersonaReview && (
          <>
            <Box mb={2}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Review the personas below. Reject any that don't fit, then approve.
              </Typography>
              <Box display="flex" gap={1}>
                <Button
                  startIcon={personaGen.loading && personaGen.source === "ai" ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
                  onClick={() => personaGen.generateWithAI()}
                  disabled={personaGen.loading}
                  size="small"
                  variant="outlined"
                >
                  {personaGen.loading && personaGen.source === "ai" ? "Generating..." : "More (AI)"}
                </Button>
                <Button
                  startIcon={personaGen.loading && personaGen.source === "general" ? <CircularProgress size={16} /> : <GroupsIcon />}
                  onClick={() => personaGen.sampleNemotron()}
                  disabled={personaGen.loading}
                  size="small"
                  variant="outlined"
                >
                  {personaGen.loading && personaGen.source === "general" ? "Sampling..." : "More (Random)"}
                </Button>
              </Box>
            </Box>

            <PersonaReview
              personas={personaGen.personas}
              rejectedIds={rejectedIds}
              onToggleReject={handleToggleReject}
              editingPersonaId={personaEdit.editingPersonaId}
              editedTitle={personaEdit.editedTitle}
              editedInfo={personaEdit.editedInfo}
              editedStyle={personaEdit.editedStyle}
              editedUseCase={personaEdit.editedUseCase}
              savingPersonaId={personaEdit.savingPersonaId}
              onSetEditedTitle={personaEdit.setEditedTitle}
              onSetEditedInfo={personaEdit.setEditedInfo}
              onSetEditedStyle={personaEdit.setEditedStyle}
              onSetEditedUseCase={personaEdit.setEditedUseCase}
              onStartEdit={personaEdit.startEdit}
              onCancelEdit={personaEdit.cancelEdit}
              onSaveEdit={(id) => personaEdit.saveEdit(id, personaGen.personas)}
              disabled={personaGen.loading}
            />
          </>
        )}

        {mode === "manual" && !showPersonaReview && (
          <Box py={2}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Define a persona that represents a type of user for your target application.
            </Typography>
            <PersonaManualAdd
              onSubmit={async (data) => {
                const result = await personaGen.addManualPersona(data);
                if (result) {
                  onPersonasAdded();
                  handleClose();
                }
              }}
              onBack={() => setMode(null)}
              loading={personaGen.loading}
              size="medium"
            />
          </Box>
        )}
      </DialogContent>

      {showPersonaReview && (
        <DialogActions>
          <Button onClick={handleClose} disabled={personaGen.loading}>Cancel</Button>
          <Button
            onClick={handleApprovePersonas}
            variant="contained"
            disabled={personaGen.loading || selectedCount === 0}
          >
            {personaGen.loading ? <CircularProgress size={20} /> : `Approve ${selectedCount} Persona${selectedCount !== 1 ? "s" : ""}`}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
}
