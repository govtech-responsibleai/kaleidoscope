"use client";

import React from "react";
import {
  Box,
  Card,
  CardContent,
  CardActions,
  Typography,
  TextField,
  Button,
  Chip,
  CircularProgress,
} from "@mui/material";
import {
  Edit as EditIcon,
  Save as SaveIcon,
} from "@mui/icons-material";
import { PersonaResponse } from "@/lib/types";

interface PersonaReviewProps {
  personas: PersonaResponse[];
  rejectedIds: Set<number>;
  onToggleReject: (personaId: number) => void;
  // Edit state (from usePersonaEdit)
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
        gap: 2,
      }}
    >
      {personas.map((persona) => {
        const isRejected = rejectedIds.has(persona.id);
        const isEditing = editingPersonaId === persona.id;
        return (
          <Card
            key={persona.id}
            sx={{
              display: "flex",
              flexDirection: "column",
              border: "2px solid",
              borderColor: isRejected ? "error.main" : "success.main",
              opacity: isRejected ? 0.5 : 1,
              transition: "all 0.2s",
            }}
          >
            <CardContent sx={{ flex: 1 }}>
              {isEditing ? (
                <Box display="flex" flexDirection="column" gap={2}>
                  <TextField label="Title" value={editedTitle} onChange={(e) => onSetEditedTitle(e.target.value)} fullWidth required size="small" />
                  <TextField label="Info" value={editedInfo} onChange={(e) => onSetEditedInfo(e.target.value)} fullWidth multiline rows={2} size="small" />
                  <TextField label="Style" value={editedStyle} onChange={(e) => onSetEditedStyle(e.target.value)} fullWidth size="small" />
                  <TextField label="Use Case" value={editedUseCase} onChange={(e) => onSetEditedUseCase(e.target.value)} fullWidth size="small" />
                </Box>
              ) : (
                <>
                  <Box display="flex" alignItems="center" gap={1} mb={1}>
                    <Typography variant="h6">{persona.title}</Typography>
                    <Chip
                      label={persona.source === "generated" ? "AI" : "General"}
                      size="small"
                      color={persona.source === "generated" ? "primary" : "secondary"}
                      variant="outlined"
                    />
                  </Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>{persona.info}</Typography>
                  <Typography variant="body2" color="text.secondary"><strong>Style:</strong> {persona.style}</Typography>
                  <Typography variant="body2" color="text.secondary"><strong>Use Case:</strong> {persona.use_case}</Typography>
                </>
              )}
            </CardContent>
            <CardActions>
              {isEditing ? (
                <>
                  <Button size="small" color="primary" startIcon={<SaveIcon />} onClick={() => onSaveEdit(persona.id)} disabled={savingPersonaId === persona.id || !editedTitle.trim()}>
                    {savingPersonaId === persona.id ? <CircularProgress size={16} /> : "Save"}
                  </Button>
                  <Button size="small" onClick={onCancelEdit} disabled={savingPersonaId === persona.id}>Cancel</Button>
                </>
              ) : (
                <>
                  <Button size="small" color="primary" startIcon={<EditIcon />} onClick={() => onStartEdit(persona)} disabled={savingPersonaId !== null || disabled}>Edit</Button>
                  <Button size="small" color={isRejected ? "success" : "error"} onClick={() => onToggleReject(persona.id)} disabled={savingPersonaId !== null}>
                    {isRejected ? "Include" : "Reject"}
                  </Button>
                </>
              )}
            </CardActions>
          </Card>
        );
      })}
    </Box>
  );
}
