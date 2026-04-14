"use client";

import React from "react";
import {
  Box,
  Checkbox,
  Chip,
  CircularProgress,
  IconButton,
  TextField,
  Typography,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import {
  Edit as EditIcon,
  Save as SaveIcon,
  Close as CloseIcon,
} from "@mui/icons-material";
import { PersonaResponse } from "@/lib/types";
import { getSourceChip } from "@/lib/theme";

interface PersonaReviewProps {
  personas: PersonaResponse[];
  rejectedIds: Set<number>;
  onToggleReject: (personaId: number) => void;
  editingPersonaId: number | null;
  editedTitle: string;
  editedInfo: string;
  editedStyle: string;
  editedUseCase: string;
  savingPersonaId: number | null;
  onSetEditedTitle: (v: string) => void;
  onSetEditedInfo: (v: string) => void;
  onSetEditedStyle: (v: string) => void;
  onSetEditedUseCase: (v: string) => void;
  onStartEdit: (persona: PersonaResponse) => void;
  onCancelEdit: () => void;
  onSaveEdit: (personaId: number) => void;
  disabled?: boolean;
}

export default function PersonaReview({
  personas,
  rejectedIds,
  onToggleReject,
  editingPersonaId,
  editedTitle,
  editedInfo,
  editedStyle,
  editedUseCase,
  savingPersonaId,
  onSetEditedTitle,
  onSetEditedInfo,
  onSetEditedStyle,
  onSetEditedUseCase,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  disabled = false,
}: PersonaReviewProps) {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)" },
        gap: 1.5,
      }}
    >
      {personas.map((persona) => {
        const isSelected = !rejectedIds.has(persona.id);
        const isEditing = editingPersonaId === persona.id;
        const isSaving = savingPersonaId === persona.id;

        return (
          <Box
            key={persona.id}
            onClick={() => {
              if (!isEditing && !disabled) onToggleReject(persona.id);
            }}
            sx={{
              display: "flex",
              alignItems: "flex-start",
              gap: 1.5,
              p: 2,
              borderRadius: 2,
              border: "1px solid",
              borderColor: isSelected ? "primary.light" : "grey.200",
              bgcolor: isSelected ? alpha("#4861b6", 0.06) : "background.paper",
              opacity: isSelected ? 1 : 0.5,
              cursor: isEditing ? "default" : "pointer",
              transition: "all 0.15s",
              "&:hover": isEditing
                ? {}
                : { borderColor: "primary.light", bgcolor: alpha("#4861b6", 0.03) },
            }}
          >
            <Checkbox
              checked={isSelected}
              size="small"
              sx={{ mt: 0.25 }}
              disabled={disabled}
              onClick={(e) => e.stopPropagation()}
              onChange={() => onToggleReject(persona.id)}
            />
            <Box sx={{ flex: 1, minWidth: 0 }}>
              {isEditing ? (
                <Box display="flex" flexDirection="column" gap={1.5} onClick={(e) => e.stopPropagation()}>
                  <TextField label="Title" value={editedTitle} onChange={(e) => onSetEditedTitle(e.target.value)} fullWidth required size="small" />
                  <TextField label="Info" value={editedInfo} onChange={(e) => onSetEditedInfo(e.target.value)} fullWidth multiline rows={2} size="small" />
                  <Box display="flex" gap={1.5}>
                    <TextField label="Style" value={editedStyle} onChange={(e) => onSetEditedStyle(e.target.value)} fullWidth size="small" />
                    <TextField label="Use Case" value={editedUseCase} onChange={(e) => onSetEditedUseCase(e.target.value)} fullWidth size="small" />
                  </Box>
                  <Box display="flex" gap={1} justifyContent="flex-end">
                    <IconButton size="small" onClick={onCancelEdit} disabled={isSaving}>
                      <CloseIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="primary"
                      onClick={() => onSaveEdit(persona.id)}
                      disabled={isSaving || !editedTitle.trim()}
                    >
                      {isSaving ? <CircularProgress size={18} /> : <SaveIcon fontSize="small" />}
                    </IconButton>
                  </Box>
                </Box>
              ) : (
                <>
                  <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                    <Typography variant="body2" fontWeight={600}>{persona.title}</Typography>
                    <Chip
                      label={getSourceChip(persona.source).label}
                      size="small"
                      variant="outlined"
                      sx={{ height: 20, fontSize: 10, ...getSourceChip(persona.source) }}
                    />
                    <Box sx={{ flex: 1 }} />
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        onStartEdit(persona);
                      }}
                      disabled={disabled || savingPersonaId !== null}
                      sx={{ opacity: 0.4, "&:hover": { opacity: 1 } }}
                    >
                      <EditIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Box>
                  {persona.info && (
                    <Typography variant="body2" color="text.secondary" sx={{
                      display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", mb: 0.5,
                    }}>
                      {persona.info}
                    </Typography>
                  )}
                  <Box display="flex" gap={2}>
                    {persona.style && (
                      <Typography variant="caption" color="text.disabled">
                        <strong>Style:</strong> {persona.style}
                      </Typography>
                    )}
                    {persona.use_case && (
                      <Typography variant="caption" color="text.disabled">
                        <strong>Use case:</strong> {persona.use_case}
                      </Typography>
                    )}
                  </Box>
                </>
              )}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}
