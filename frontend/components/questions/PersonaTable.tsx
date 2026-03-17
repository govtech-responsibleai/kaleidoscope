"use client";

import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  TextField,
  CircularProgress,
} from "@mui/material";
import {
  Edit as EditIcon,
  Save as SaveIcon,
  Close as CloseIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
} from "@mui/icons-material";
import { Typography } from "@mui/material";
import { personaApi } from "@/lib/api";
import { PersonaResponse } from "@/lib/types";
import { usePersonaEdit } from "@/hooks/usePersonaEdit";

interface PersonaTableProps {
  personas: PersonaResponse[];
  onPersonasChanged: () => void;
  onError?: (message: string) => void;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case "approved": return "success";
    case "rejected": return "error";
    case "edited": return "info";
    default: return "warning";
  }
};

const getSourceLabel = (source: string) => source === "generated" ? "AI" : "General";
const getSourceColor = (source: string) => source === "generated" ? "primary" : "secondary";

export default function PersonaTable({
  personas,
  onPersonasChanged,
  onError,
}: PersonaTableProps) {
  const personaEdit = usePersonaEdit({
    onSaved: () => onPersonasChanged(),
    onError: (msg) => onError?.(msg),
  });

  const handleApprove = async (personaId: number) => {
    try {
      await personaApi.approve(personaId);
      onPersonasChanged();
    } catch (err) {
      console.error("Failed to approve persona:", err);
    }
  };

  const handleReject = async (personaId: number) => {
    try {
      await personaApi.reject(personaId);
      onPersonasChanged();
    } catch (err) {
      console.error("Failed to reject persona:", err);
    }
  };

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table>
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 600 }}>Title</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Background</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Style</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Use Case</TableCell>
            <TableCell align="center" sx={{ fontWeight: 600, width: 80 }}>
              Source
            </TableCell>
            <TableCell align="center" sx={{ fontWeight: 600, width: 90 }}>
              Status
            </TableCell>
            <TableCell align="center" sx={{ fontWeight: 600, width: 120 }}>
              Actions
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {personas.map((persona) => {
            const isEditing = personaEdit.editingPersonaId === persona.id;
            return (
              <TableRow key={persona.id}>
                <TableCell sx={{ minWidth: 140 }}>
                  {isEditing ? (
                    <TextField
                      value={personaEdit.editedTitle}
                      onChange={(e) => personaEdit.setEditedTitle(e.target.value)}
                      size="small"
                      fullWidth
                      required
                    />
                  ) : (
                    <Typography variant="body2" fontWeight={600}>
                      {persona.title}
                    </Typography>
                  )}
                </TableCell>
                <TableCell sx={{ maxWidth: 250 }}>
                  {isEditing ? (
                    <TextField
                      value={personaEdit.editedInfo}
                      onChange={(e) => personaEdit.setEditedInfo(e.target.value)}
                      size="small"
                      fullWidth
                      multiline
                      rows={2}
                    />
                  ) : (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        display: "-webkit-box",
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {persona.info || "-"}
                    </Typography>
                  )}
                </TableCell>
                <TableCell sx={{ maxWidth: 180 }}>
                  {isEditing ? (
                    <TextField
                      value={personaEdit.editedStyle}
                      onChange={(e) => personaEdit.setEditedStyle(e.target.value)}
                      size="small"
                      fullWidth
                    />
                  ) : (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {persona.style || "-"}
                    </Typography>
                  )}
                </TableCell>
                <TableCell sx={{ maxWidth: 180 }}>
                  {isEditing ? (
                    <TextField
                      value={personaEdit.editedUseCase}
                      onChange={(e) => personaEdit.setEditedUseCase(e.target.value)}
                      size="small"
                      fullWidth
                    />
                  ) : (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {persona.use_case || "-"}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={getSourceLabel(persona.source)}
                    size="small"
                    color={getSourceColor(persona.source) as "primary" | "secondary"}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={persona.status}
                    size="small"
                    color={getStatusColor(persona.status) as "success" | "error" | "info" | "warning"}
                    variant="filled"
                  />
                </TableCell>
                <TableCell align="center">
                  {isEditing ? (
                    <Box display="flex" gap={0.5} justifyContent="center">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => personaEdit.saveEdit(persona.id, personas)}
                        disabled={personaEdit.savingPersonaId !== null || !personaEdit.editedTitle.trim()}
                      >
                        {personaEdit.savingPersonaId === persona.id ? (
                          <CircularProgress size={18} />
                        ) : (
                          <SaveIcon fontSize="small" />
                        )}
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={personaEdit.cancelEdit}
                        disabled={personaEdit.savingPersonaId !== null}
                      >
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  ) : (
                    <Box display="flex" gap={0.5} justifyContent="center">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => personaEdit.startEdit(persona)}
                        disabled={personaEdit.savingPersonaId !== null}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      {persona.status !== "approved" && (
                        <IconButton
                          size="small"
                          color="success"
                          onClick={() => handleApprove(persona.id)}
                        >
                          <CheckCircleIcon fontSize="small" />
                        </IconButton>
                      )}
                      {persona.status !== "rejected" && (
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleReject(persona.id)}
                        >
                          <CancelIcon fontSize="small" />
                        </IconButton>
                      )}
                    </Box>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
