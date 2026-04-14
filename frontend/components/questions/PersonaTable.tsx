"use client";

import { useState } from "react";
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Paper,
  Chip,
  IconButton,
  TextField,
  CircularProgress,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Select,
  Divider,
  Typography,
} from "@mui/material";
import {
  Save as SaveIcon,
  Close as CloseIcon,
  MoreHoriz as MoreHorizIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
} from "@mui/icons-material";
import { personaApi } from "@/lib/api";
import { PersonaResponse } from "@/lib/types";
import { getSourceChip } from "@/lib/theme";
import { usePersonaEdit } from "@/hooks/usePersonaEdit";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";

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



export default function PersonaTable({
  personas,
  onPersonasChanged,
  onError,
}: PersonaTableProps) {
  const personaEdit = usePersonaEdit({
    onSaved: () => onPersonasChanged(),
    onError: (msg) => onError?.(msg),
  });

  const [page, setPage] = useState(0);
  const rowsPerPage = 10;

  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [menuPersona, setMenuPersona] = useState<PersonaResponse | null>(null);
  const [personaToDelete, setPersonaToDelete] = useState<PersonaResponse | null>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, persona: PersonaResponse) => {
    setMenuAnchor(event.currentTarget);
    setMenuPersona(persona);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
    setMenuPersona(null);
  };

  const handleStatusChange = async (personaId: number, action: "approved" | "rejected") => {
    handleMenuClose();
    try {
      if (action === "approved") {
        await personaApi.approve(personaId);
      } else {
        await personaApi.reject(personaId);
      }
      onPersonasChanged();
    } catch (err) {
      console.error(`Failed to update persona status:`, err);
      onError?.("Failed to update persona status. Please try again.");
    }
  };

  const handleEditFromMenu = (persona: PersonaResponse) => {
    handleMenuClose();
    personaEdit.startEdit(persona);
  };

  const handleDeleteConfirm = async () => {
    if (!personaToDelete) return;
    try {
      await personaApi.delete(personaToDelete.id);
      onPersonasChanged();
    } catch (err) {
      console.error("Failed to delete persona:", err);
      onError?.("Failed to delete persona. Please try again.");
    }
  };

  const maxPage = Math.max(0, Math.ceil(personas.length / rowsPerPage) - 1);
  const currentPage = Math.min(page, maxPage);

  return (
    <>
      <>
      <TableContainer component={Paper} variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: "grey.50" }}>
              <TableCell sx={{ fontWeight: 700, fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase", color: "text.secondary", py: 1.5 }}>Title</TableCell>
              <TableCell sx={{ fontWeight: 700, fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase", color: "text.secondary", py: 1.5 }}>Background</TableCell>
              <TableCell sx={{ fontWeight: 700, fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase", color: "text.secondary", py: 1.5 }}>Style</TableCell>
              <TableCell sx={{ fontWeight: 700, fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase", color: "text.secondary", py: 1.5 }}>Use Case</TableCell>
              <TableCell align="center" sx={{ fontWeight: 700, fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase", color: "text.secondary", py: 1.5, width: 80 }}>Source</TableCell>
              <TableCell align="center" sx={{ fontWeight: 700, fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase", color: "text.secondary", py: 1.5, width: 90 }}>Status</TableCell>
              <TableCell align="center" sx={{ width: 50, py: 1.5 }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {personas.slice(currentPage * rowsPerPage, currentPage * rowsPerPage + rowsPerPage).map((persona) => {
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
                      label={getSourceChip(persona.source).label}
                      size="small"
                      variant="outlined"
                      sx={getSourceChip(persona.source)}
                    />
                  </TableCell>
                  <TableCell align="center">
                    {isEditing ? (
                      <Select
                        value={persona.status}
                        size="small"
                        onChange={(e) => handleStatusChange(persona.id, e.target.value as "approved" | "rejected")}
                        sx={{ minWidth: 100, fontSize: 12 }}
                      >
                        <MenuItem value="approved">Approved</MenuItem>
                        <MenuItem value="pending" disabled>Pending</MenuItem>
                        <MenuItem value="rejected">Rejected</MenuItem>
                      </Select>
                    ) : (
                      <Chip
                        label={persona.status}
                        size="small"
                        color={getStatusColor(persona.status) as "success" | "error" | "info" | "warning"}
                        variant="filled"
                      />
                    )}
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
                      <IconButton
                        size="small"
                        onClick={(e) => handleMenuOpen(e, persona)}
                        disabled={personaEdit.savingPersonaId !== null}
                        sx={{ opacity: 0.5, "&:hover": { opacity: 1 } }}
                      >
                        <MoreHorizIcon fontSize="small" />
                      </IconButton>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        rowsPerPageOptions={[rowsPerPage]}
        rowsPerPage={rowsPerPage}
        count={personas.length}
        page={currentPage}
        onPageChange={(_event, newPage) => setPage(newPage)}
      />
      </>

      <Menu
        anchorEl={menuAnchor}
        open={!!menuAnchor}
        onClose={handleMenuClose}
        transformOrigin={{ horizontal: "right", vertical: "top" }}
        anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
      >
        <MenuItem onClick={() => menuPersona && handleEditFromMenu(menuPersona)}>
          <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem
          onClick={() => {
            if (menuPersona) setPersonaToDelete(menuPersona);
            handleMenuClose();
          }}
          sx={{ color: "error.main" }}
        >
          <ListItemIcon><DeleteIcon fontSize="small" color="error" /></ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      <ConfirmDeleteDialog
        open={!!personaToDelete}
        onClose={() => setPersonaToDelete(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Persona"
        itemName={personaToDelete?.title}
        description="This will permanently delete this persona and all questions associated with it."
      />
    </>
  );
}
