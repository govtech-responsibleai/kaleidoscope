"use client";

import React from "react";
import {
  Box,
  Button,
  Checkbox,
  ListItemText,
  MenuItem,
  Popover,
  Select,
  Typography,
} from "@mui/material";
import { IconFilter2 } from "@tabler/icons-react";
import { actionIconProps } from "@/lib/styles";
import { QuestionType, QuestionScope } from "@/lib/types";

interface PersonaFilterOption {
  id: number;
  title: string;
}

interface QAFilterProps {
  selectedTypes: QuestionType[];
  selectedScopes: QuestionScope[];
  selectedPersonaIds: number[];
  personas: PersonaFilterOption[];
  onTypesChange: (types: QuestionType[]) => void;
  onScopesChange: (scopes: QuestionScope[]) => void;
  onPersonaIdsChange: (personaIds: number[]) => void;
}

const filterLabelSx = {
  mb: 0.5,
  display: "block",
  fontWeight: 600,
} as const;

export default function QAFilter({
  selectedTypes,
  selectedScopes,
  selectedPersonaIds,
  personas,
  onTypesChange,
  onScopesChange,
  onPersonaIdsChange,
}: QAFilterProps) {
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);

  const isFilterActive =
    selectedTypes.length < 2 ||
    selectedScopes.length < 2 ||
    (personas.length > 0 && selectedPersonaIds.length < personas.length);

  return (
    <>
      <Button
        variant="outlined"
        endIcon={<IconFilter2 {...actionIconProps} />}
        onClick={(e) => setAnchorEl(e.currentTarget)}
        color={isFilterActive ? "primary" : "inherit"}
        disableRipple
        size="small"
        sx={{ px: 1.5, height: "40px", fontWeight: 400, borderColor: "rgba(0, 0, 0, 0.2)" }}
      >
        Questions
      </Button>

      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "left",
        }}
      >
        <Box sx={{ p: 2, minWidth: 280 }}>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2 }}>
            Filter Questions
          </Typography>

          {/* Type Filter */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary" sx={filterLabelSx}>
              Type
            </Typography>
            <Select
              size="small"
              fullWidth
              multiple
              value={selectedTypes}
              onChange={(e) => onTypesChange(e.target.value as QuestionType[])}
              renderValue={(selected) =>
                selected.length === 2 ? "All Types" : selected.join(", ")
              }
            >
              <MenuItem value={QuestionType.TYPICAL}>
                <Checkbox checked={selectedTypes.includes(QuestionType.TYPICAL)} />
                <ListItemText primary="Typical" />
              </MenuItem>
              <MenuItem value={QuestionType.EDGE}>
                <Checkbox checked={selectedTypes.includes(QuestionType.EDGE)} />
                <ListItemText primary="Edge" />
              </MenuItem>
            </Select>
          </Box>

          {/* Scope Filter */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary" sx={filterLabelSx}>
              Scope
            </Typography>
            <Select
              size="small"
              fullWidth
              multiple
              value={selectedScopes}
              onChange={(e) => onScopesChange(e.target.value as QuestionScope[])}
              renderValue={(selected) =>
                selected.length === 2
                  ? "All Scopes"
                  : selected.map((s) => (s === QuestionScope.IN_KB ? "In KB" : "Out KB")).join(", ")
              }
            >
              <MenuItem value={QuestionScope.IN_KB}>
                <Checkbox checked={selectedScopes.includes(QuestionScope.IN_KB)} />
                <ListItemText primary="In KB" />
              </MenuItem>
              <MenuItem value={QuestionScope.OUT_KB}>
                <Checkbox checked={selectedScopes.includes(QuestionScope.OUT_KB)} />
                <ListItemText primary="Out KB" />
              </MenuItem>
            </Select>
          </Box>

          {/* Persona Filter */}
          <Box>
            <Typography variant="caption" color="text.secondary" sx={filterLabelSx}>
              Personas
            </Typography>
            <Select
              size="small"
              fullWidth
              multiple
              value={selectedPersonaIds}
              onChange={(e) => onPersonaIdsChange(e.target.value as number[])}
              renderValue={(selected) =>
                selected.length === personas.length
                  ? "All Personas"
                  : `${selected.length} selected`
              }
            >
              {personas.map((persona) => (
                <MenuItem key={persona.id} value={persona.id}>
                  <Checkbox checked={selectedPersonaIds.includes(persona.id)} />
                  <ListItemText primary={persona.title} />
                </MenuItem>
              ))}
            </Select>
          </Box>
        </Box>
      </Popover>
    </>
  );
}
