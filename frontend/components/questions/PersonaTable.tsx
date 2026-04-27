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
  Chip,
  IconButton,
  Typography,
} from "@mui/material";
import {
  IconCircleCheck,
  IconCircleX,
  IconLoader,
  IconPencil,
  IconTrash,
} from "@tabler/icons-react";
import { personaApi } from "@/lib/api";
import { PersonaResponse } from "@/lib/types";
import { getSourceChip } from "@/lib/theme";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import EditPersonaDialog from "@/components/questions/EditPersonaDialog";
import { compactActionIconProps } from "@/lib/styles";
import {
  compactChipSx,
  getTableBodyRowSx,
  subtleActionButtonSx,
  tableHeaderCellSx,
  tableHeaderRowSx,
} from "@/lib/styles";
import { useTheme } from "@mui/material";

interface PersonaTableProps {
  personas: PersonaResponse[];
  onPersonasChanged: () => void;
  onError?: (message: string) => void;
}

const StatusIcon = ({ status }: { status: string }) => {
  if (status === "approved") return <Box sx={{ color: "success.main", display: "flex" }}><IconCircleCheck {...compactActionIconProps} /></Box>;
  if (status === "pending") return <Box sx={{ color: "warning.main", display: "flex" }}><IconLoader {...compactActionIconProps} /></Box>;
  return <Box sx={{ color: "error.main", display: "flex" }}><IconCircleX {...compactActionIconProps} /></Box>;
};

export default function PersonaTable({
  personas,
  onPersonasChanged,
  onError,
}: PersonaTableProps) {
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const rowsPerPage = 10;

  const [personaToDelete, setPersonaToDelete] = useState<PersonaResponse | null>(null);
  const [editingPersona, setEditingPersona] = useState<PersonaResponse | null>(null);

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
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow sx={tableHeaderRowSx}>
              <TableCell sx={{ ...tableHeaderCellSx, width: 160 }}>Title</TableCell>
              <TableCell sx={tableHeaderCellSx}>Background</TableCell>
              <TableCell sx={tableHeaderCellSx}>Style</TableCell>
              <TableCell sx={tableHeaderCellSx}>Use Case</TableCell>
              <TableCell sx={{ ...tableHeaderCellSx, width: 80 }}>Source</TableCell>
              <TableCell sx={{ ...tableHeaderCellSx, width: 60 }}>Approved</TableCell>
              <TableCell sx={{ width: 80, py: 1.5 }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {personas.slice(currentPage * rowsPerPage, currentPage * rowsPerPage + rowsPerPage).map((persona) => (
              <TableRow key={persona.id} sx={getTableBodyRowSx(theme)}>
                <TableCell sx={{ minWidth: 140 }}>
                  <Typography variant="body2" fontWeight={600}>
                    {persona.title}
                  </Typography>
                </TableCell>
                <TableCell sx={{ maxWidth: 250 }}>
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
                </TableCell>
                <TableCell sx={{ maxWidth: 180 }}>
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
                </TableCell>
                <TableCell sx={{ maxWidth: 180 }}>
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
                </TableCell>
                <TableCell>
                  <Chip
                    label={getSourceChip(persona.source).label}
                    size="small"
                    variant="outlined"
                    sx={{ ...compactChipSx, ...getSourceChip(persona.source) }}
                  />
                </TableCell>
                <TableCell>
                  <StatusIcon status={persona.status} />
                </TableCell>
                <TableCell>
                  <Box display="flex" gap={0.5}>
                    <IconButton
                      size="small"
                      onClick={() => setEditingPersona(persona)}
                      sx={subtleActionButtonSx}
                    >
                      <IconPencil {...compactActionIconProps} />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => setPersonaToDelete(persona)}
                      sx={{ ...subtleActionButtonSx, "&:hover": { opacity: 1, bgcolor: "error.50", color: "error.main" } }}
                    >
                      <IconTrash {...compactActionIconProps} />
                    </IconButton>
                  </Box>
                </TableCell>
              </TableRow>
            ))}
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

      <ConfirmDeleteDialog
        open={!!personaToDelete}
        onClose={() => setPersonaToDelete(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Persona"
        itemName={personaToDelete?.title}
        description="This will permanently delete this persona and all questions associated with it."
      />

      <EditPersonaDialog
        open={!!editingPersona}
        persona={editingPersona}
        personas={personas}
        onClose={() => setEditingPersona(null)}
        onSaved={onPersonasChanged}
      />
    </>
  );
}
