"use client";

import { useState } from "react";
import { Box, Button, CircularProgress, MenuItem, Select, Typography, Alert } from "@mui/material";
import { IconSparkles, IconUsersGroup } from "@tabler/icons-react";
import { ProviderModelOption } from "@/lib/types";
import { usePersonaGeneration } from "@/hooks/usePersonaGeneration";
import { usePersonaEdit } from "@/hooks/usePersonaEdit";
import PersonaSelect from "@/components/questions/PersonaSelect";
import PersonaReview from "@/components/questions/PersonaReview";
import PersonaManualAdd from "@/components/questions/PersonaManualAdd";
import { actionIconProps } from "@/lib/iconStyles";

interface PersonaGenerationPanelProps {
  availableModels: ProviderModelOption[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  personaGen: ReturnType<typeof usePersonaGeneration>;
  personaEdit: ReturnType<typeof usePersonaEdit>;
  rejectedIds: Set<number>;
  onToggleReject: (id: number) => void;
  onSetRejectedIds: (ids: Set<number>) => void;
  onManualPersonaAdded?: () => void;
}

export default function PersonaGenerationPanel({
  availableModels,
  selectedModel,
  onModelChange,
  personaGen,
  personaEdit,
  rejectedIds,
  onToggleReject,
  onSetRejectedIds,
  onManualPersonaAdded,
}: PersonaGenerationPanelProps) {
  const [manualMode, setManualMode] = useState(false);
  const showPersonaReview = personaGen.personas.length > 0;

  const modelPill = (
    <Box sx={{
      display: "inline-flex", alignItems: "center", gap: 1.5,
      px: 2, py: 0.75, borderRadius: 2,
      border: "1px solid", borderColor: "divider", bgcolor: "grey.50",
    }}>
      <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ whiteSpace: "nowrap" }}>
        AI model
      </Typography>
      <Select
        size="small"
        value={selectedModel}
        onChange={(e) => onModelChange(e.target.value as string)}
        displayEmpty
        sx={{ minWidth: 180, "& .MuiOutlinedInput-notchedOutline": { border: "none" }, fontSize: "0.8125rem" }}
      >
        {availableModels.length === 0
          ? <MenuItem value="" disabled>No valid models available</MenuItem>
          : availableModels.map((m) => (
            <MenuItem key={m.value} value={m.value}>{m.provider_name}: {m.label}</MenuItem>
          ))}
      </Select>
    </Box>
  );

  const resolvedModel = availableModels.find((m) => m.value === selectedModel);
  const modelInfoChip = (
    <Box sx={{
      display: "inline-flex", alignItems: "center", gap: 0.75,
      px: 1.5, py: 0.5, borderRadius: 2,
      border: "1px solid", borderColor: "divider", bgcolor: "grey.50",
    }}>
      <Typography variant="caption" color="text.secondary">AI model:</Typography>
      <Typography variant="caption" fontWeight={600}>
        {resolvedModel ? `${resolvedModel.provider_name}: ${resolvedModel.label}` : selectedModel || "—"}
      </Typography>
    </Box>
  );

  return (
    <Box>
      {personaGen.error && <Alert severity="error" sx={{ mb: 2 }}>{personaGen.error}</Alert>}

      {/* Initial: 3 cards + model pill */}
      {!manualMode && !showPersonaReview && !personaGen.loading && (
        <Box display="flex" flexDirection="column" alignItems="center" py={3} gap={3}>
          <PersonaSelect
            onGenerateAI={() => personaGen.generateWithAI(undefined, selectedModel || undefined)}
            onSampleRandom={() => personaGen.sampleNemotron()}
            onAddManual={() => setManualMode(true)}
          />
          {modelPill}
        </Box>
      )}

      {/* Loading */}
      {personaGen.loading && !showPersonaReview && !manualMode && (
        <Box display="flex" flexDirection="column" alignItems="center" py={4} gap={2}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary">
            {personaGen.source === "ai" ? "Generating personas with AI..." : "Sampling personas..."}
          </Typography>
        </Box>
      )}

      {/* Review */}
      {showPersonaReview && (
        <Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Review the personas below. Uncheck any that don&apos;t fit.
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap" alignItems="flex-end" mb={2}>
            {modelInfoChip}
            <Button
              startIcon={personaGen.loading && personaGen.source === "ai" ? <CircularProgress size={16} /> : <IconSparkles {...actionIconProps} />}
              onClick={() => personaGen.generateWithAI(undefined, selectedModel || undefined)}
              disabled={personaGen.loading} size="small" variant="outlined"
            >
              {personaGen.loading && personaGen.source === "ai" ? "Generating..." : "More (AI)"}
            </Button>
            <Button
              startIcon={personaGen.loading && personaGen.source === "general" ? <CircularProgress size={16} /> : <IconUsersGroup {...actionIconProps} />}
              onClick={() => personaGen.sampleNemotron()}
              disabled={personaGen.loading} size="small" variant="outlined"
            >
              {personaGen.loading && personaGen.source === "general" ? "Sampling..." : "More (Random)"}
            </Button>
            <Box sx={{ flex: 1 }} />
            <Button
              size="small"
              onClick={() => onSetRejectedIds(
                rejectedIds.size === 0
                  ? new Set(personaGen.personas.map((p) => p.id))
                  : new Set()
              )}
              sx={{ textTransform: "none", fontSize: "0.75rem", whiteSpace: "nowrap" }}
            >
              {rejectedIds.size === 0 ? "Deselect All" : "Select All"}
            </Button>
          </Box>
          <PersonaReview
            personas={personaGen.personas}
            rejectedIds={rejectedIds}
            onToggleReject={onToggleReject}
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
        </Box>
      )}

      {/* Manual add */}
      {manualMode && !showPersonaReview && (
        <Box py={2}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Define a persona that represents a type of user for your target application.
          </Typography>
          <PersonaManualAdd
            onSubmit={async (data) => {
              const result = await personaGen.addManualPersona(data);
              if (result) {
                if (onManualPersonaAdded) onManualPersonaAdded();
                else setManualMode(false);
              }
            }}
            onBack={() => setManualMode(false)}
            loading={personaGen.loading}
            size="medium"
          />
        </Box>
      )}
    </Box>
  );
}
