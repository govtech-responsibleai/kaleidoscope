"use client";

import { useState, useEffect } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Box, Typography, CircularProgress, IconButton,
} from "@mui/material";
import { IconX } from "@tabler/icons-react";
import { personaApi, providerApi } from "@/lib/api";
import { ProviderModelOption } from "@/lib/types";
import { usePersonaGeneration } from "@/hooks/usePersonaGeneration";
import { usePersonaEdit } from "@/hooks/usePersonaEdit";
import PersonaGenerationPanel from "@/components/questions/PersonaGenerationPanel";
import { actionIconProps } from "@/lib/iconStyles";

interface AddPersonasModalProps {
  open: boolean;
  onClose: () => void;
  targetId: number;
  onPersonasAdded: () => void;
}

export default function AddPersonasModal({ open, onClose, targetId, onPersonasAdded }: AddPersonasModalProps) {
  const [rejectedIds, setRejectedIds] = useState<Set<number>>(new Set());
  const [availableModels, setAvailableModels] = useState<ProviderModelOption[]>([]);
  const [selectedModel, setSelectedModel] = useState("");

  const personaGen = usePersonaGeneration(targetId);
  const personaEdit = usePersonaEdit({
    onSaved: (id, updated) => personaGen.updatePersona(id, updated),
    onError: (msg) => personaGen.setError(msg),
  });

  useEffect(() => {
    if (!open) return;
    let isMounted = true;
    providerApi.getSetup()
      .then((r) => {
        if (!isMounted) return;
        setAvailableModels(r.data.valid_models);
        setSelectedModel((prev) => prev || r.data.valid_models[0]?.value || "");
      })
      .catch(() => {});
    return () => { isMounted = false; };
  }, [open]);

  const handleClose = () => {
    setRejectedIds(new Set());
    setAvailableModels([]);
    setSelectedModel("");
    personaGen.reset();
    personaEdit.reset();
    onClose();
  };

  const handleApprove = async () => {
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
    } catch {
      personaGen.setError("Failed to approve personas.");
    }
  };

  const selectedCount = personaGen.personas.length - rejectedIds.size;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ pb: 0 }}>
        <Box display="flex" justifyContent="flex-end">
          <IconButton onClick={handleClose} size="small"><IconX {...actionIconProps} /></IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box textAlign="center" sx={{ mb: 2, mt: 1 }}>
          <Typography variant="h6" fontWeight={700}>Add Personas</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Choose how you&apos;d like to add personas for this target.
          </Typography>
        </Box>
        <PersonaGenerationPanel
          availableModels={availableModels}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          personaGen={personaGen}
          personaEdit={personaEdit}
          rejectedIds={rejectedIds}
          onToggleReject={(id) => setRejectedIds((prev) => {
            const n = new Set(prev);
            if (n.has(id)) n.delete(id); else n.add(id);
            return n;
          })}
          onSetRejectedIds={setRejectedIds}
        />
      </DialogContent>
      {personaGen.personas.length > 0 && (
        <DialogActions>
          <Button onClick={handleClose} disabled={personaGen.loading}>Cancel</Button>
          <Button
            onClick={handleApprove}
            variant="contained"
            disabled={personaGen.loading || selectedCount === 0}
          >
            {personaGen.loading
              ? <CircularProgress size={20} />
              : `Approve ${selectedCount} Persona${selectedCount !== 1 ? "s" : ""}`}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
}
