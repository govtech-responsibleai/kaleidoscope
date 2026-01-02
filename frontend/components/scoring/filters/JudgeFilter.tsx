"use client";

import React from "react";
import {
  Button,
  Checkbox,
  ListItemText,
  Menu,
  MenuItem,
} from "@mui/material";
import { FilterList as FilterListIcon } from "@mui/icons-material";
import { JudgeConfig } from "@/lib/types";

interface JudgeFilterProps {
  reliableJudges: JudgeConfig[];
  selectedJudgeIds: Set<number>;
  onSelectionChange: (selectedIds: Set<number>) => void;
}

export default function JudgeFilter({
  reliableJudges,
  selectedJudgeIds,
  onSelectionChange,
}: JudgeFilterProps) {
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);

  const isFilterActive = selectedJudgeIds.size < reliableJudges.length;

  const handleToggle = (judgeId: number) => {
    const next = new Set(selectedJudgeIds);
    if (next.has(judgeId)) {
      next.delete(judgeId);
    } else {
      next.add(judgeId);
    }
    onSelectionChange(next);
  };

  return (
    <>
      <Button
        variant="outlined"
        endIcon={<FilterListIcon />}
        onClick={(e) => setAnchorEl(e.currentTarget)}
        color={isFilterActive ? "primary" : "inherit"}
        disableRipple
        size="small"
        sx={{ px: 1.5, height: "40px", fontWeight: 400, borderColor: "rgba(0, 0, 0, 0.2)", }}
      >
        Evaluators ({selectedJudgeIds.size}/{reliableJudges.length})
      </Button>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        {reliableJudges.map((judge) => (
          <MenuItem
            key={judge.id}
            selected={selectedJudgeIds.has(judge.id)}
            onClick={() => handleToggle(judge.id)}
          >
            <Checkbox checked={selectedJudgeIds.has(judge.id)} />
            <ListItemText primary={judge.name} />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
